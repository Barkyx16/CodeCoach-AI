"""Sending a request again after its response was lost (Volume 7, prompt 6).

A timeout or dropped connection isn't a definite failure: the server may have done the work. The
learner presses the button again, and the browser sends the same request key:
- a hint or code review gets the first answer back: no second provider call, no second use of
  the daily budget, even when that budget has run out since;
- a new story comes back as the story the first request made, not a duplicate;
- the same key for a different request is refused, never silently answered with the wrong thing;
- a rate limit says how long to wait, in the body and in Retry-After.
Synthetic accounts, the offline coach; no provider is called."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import AIInteraction, ExperienceEntry
from app.services.ai.offline import OfflineCoach
from tests.conftest import auth_headers, register

CODE = "class Solution { public int[] twoSum(int[] nums, int target) { return new int[0]; } }"


@pytest.fixture
def calls(monkeypatch) -> dict[str, int]:
    """Counts what reaches the coach (the offline one here, the provider in production)."""
    counted = {"hint": 0, "review": 0}
    for name in counted:
        original = getattr(OfflineCoach, name)

        def wrapper(self, ctx, _original=original, _name=name):
            counted[_name] += 1
            return _original(self, ctx)

        monkeypatch.setattr(OfflineCoach, name, wrapper)
    return counted


def hint(c, h, level, key=None):
    body = {"problem_slug": "two-sum", "level": level, "source_code": CODE}
    if key:
        body["client_request_id"] = key
    return c.post("/api/v1/ai/hint", headers=h, json=body)


def review(c, h, key=None, slug="two-sum"):
    body = {"problem_slug": slug, "source_code": CODE}
    if key:
        body["client_request_id"] = key
    return c.post("/api/v1/ai/review", headers=h, json=body)


def interactions(c) -> int:
    with c.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(AIInteraction)) or 0


def used(c, h) -> int:
    return c.get("/api/v1/ai/usage", headers=h).json()["used_today"]


def test_a_hint_sent_again_gets_the_first_answer_without_a_second_call(make_client, calls):
    c = make_client(ai_daily_request_limit=1)
    h = auth_headers(register(c))
    first = hint(c, h, 1, key="hint-key-0001")
    assert first.status_code == 200 and calls["hint"] == 1 and used(c, h) == 1
    # The response was lost; the learner presses the button again. The budget is spent by now,
    # and the answer still comes back, because it was already paid for.
    again = hint(c, h, 1, key="hint-key-0001")
    assert again.status_code == 200 and again.json() == first.json()
    assert calls["hint"] == 1 and used(c, h) == 1 and interactions(c) == 1
    # A genuinely new request is still limited.
    assert hint(c, h, 2, key="hint-key-0002").status_code == 429


def test_a_review_sent_again_gets_the_first_answer_without_a_second_call(client, user_headers, calls):
    first = review(client, user_headers, key="review-key-01")
    again = review(client, user_headers, key="review-key-01")
    assert first.status_code == again.status_code == 200
    assert (
        again.json()["review"] == first.json()["review"]
        and again.json()["provider"] == first.json()["provider"]
    )
    assert calls["review"] == 1 and interactions(client) == 1
    # Without a key (an older client), each request is a new review, as before.
    review(client, user_headers)
    review(client, user_headers)
    assert calls["review"] == 3 and interactions(client) == 3


def test_a_key_used_for_something_else_is_refused(client, user_headers, calls):
    assert hint(client, user_headers, 1, key="shared-key-1").status_code == 200
    for r in (
        review(client, user_headers, key="shared-key-1"),  # another action
        hint(client, user_headers, 2, key="shared-key-1"),  # another level
    ):
        assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"
    assert calls == {"hint": 1, "review": 0}


def test_keys_belong_to_their_account(client, calls):
    ada = auth_headers(register(client, email="ada@example.com"))
    client.cookies.clear()
    bob = auth_headers(register(client, email="bob@example.com"))
    assert review(client, ada, key="same-key-0001").status_code == 200
    # Bob's request with the same key is Bob's own: a new review, not Ada's answer.
    assert review(client, bob, key="same-key-0001").status_code == 200
    assert calls["review"] == 2


def test_a_story_created_again_is_the_same_story(client, user_headers):
    body = {
        "title": "Calmed a busy ward",
        "situation": "Two call lights at once.",
        "client_request_id": "story-key-01",
    }
    first = client.post("/api/v1/me/stories", headers=user_headers, json=body)
    again = client.post("/api/v1/me/stories", headers=user_headers, json=body)
    assert first.status_code in (200, 201) and again.status_code == first.status_code
    assert again.json()["id"] == first.json()["id"]
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ExperienceEntry)) == 1
    # Without a key, each create is a new story, as before.
    plain = {k: v for k, v in body.items() if k != "client_request_id"}
    client.post("/api/v1/me/stories", headers=user_headers, json=plain)
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ExperienceEntry)) == 2


def test_rate_limits_say_how_long_to_wait(make_client):
    c = make_client(ai_daily_request_limit=1)
    h = auth_headers(register(c))
    hint(c, h, 1)
    r = hint(c, h, 2)
    assert r.status_code == 429
    seconds = r.json()["error"]["details"]["retry_after_seconds"]
    assert 0 < seconds <= 24 * 3600 and int(r.headers["Retry-After"]) == pytest.approx(seconds, abs=1)


def test_the_browser_may_read_retry_after(make_client):
    """The app runs on another origin than the API in development: without this, the page can't
    read Retry-After and can't say how long to wait."""
    c = make_client(ai_daily_request_limit=1, cors_origins=["http://localhost:5173"])
    h = {**auth_headers(register(c)), "Origin": "http://localhost:5173"}
    hint(c, h, 1)
    r = hint(c, h, 2)
    assert r.status_code == 429
    exposed = {v.strip().lower() for v in r.headers["Access-Control-Expose-Headers"].split(",")}
    assert "retry-after" in exposed
