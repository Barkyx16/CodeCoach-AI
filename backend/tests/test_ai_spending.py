"""What the AI coach can spend (docs/SECURITY.md, "AI spending"): a ceiling on paid calls for the
whole deployment, shared by every replica and the worker, past which the built-in coach answers
without the paid provider being called; a smaller daily allowance for guests and accounts whose
email isn't verified (anyone can make one), lifted by verifying; and a daily cap on the guest
sessions one address can start. Synthetic accounts; the paid provider is a stand-in that counts
its calls, so nothing is ever sent anywhere."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.jobs import close_interviews
from app.models import RateLimitCounter, User
from app.services.ai.offline import OfflineCoach
from app.services.ai.spend_cap import KEY, SpendCappedProvider, capped
from tests.conftest import auth_headers, register

SLUGS = ["two-sum", "valid-palindrome", "contains-duplicate", "valid-parentheses"]


class Paid:
    """A paid provider's stand-in: answers as the offline coach would, and counts each call."""

    name, model = "anthropic", "stand-in"

    def __init__(self):
        self.calls = 0
        self._offline = OfflineCoach()

    def __getattr__(self, item):
        method = getattr(self._offline, item)

        def counted(ctx):
            self.calls += 1
            return replace(method(ctx), provider=self.name, model=self.model)

        return counted


def hint(client, headers, slug):
    return client.post(
        "/api/v1/ai/hint", headers=headers, json={"problem_slug": slug, "level": 1, "source_code": ""}
    )


def verify(client, token_response):
    with client.app.state.session_factory() as db:
        db.get(User, token_response["user"]["id"]).email_verified_at = datetime.now(UTC)
        db.commit()


def counted(client) -> int:
    with client.app.state.session_factory() as db:
        return int(
            db.scalar(
                select(func.coalesce(func.sum(RateLimitCounter.count), 0)).where(RateLimitCounter.key == KEY)
            )
        )


@pytest.fixture
def paid_app(make_client):
    def make(limit: int, **overrides):
        c = make_client(ai_app_daily_paid_call_limit=limit, **overrides)
        stand_in = Paid()
        c.app.state.ai_provider = capped(stand_in, c.app.state.settings, c.app.state.session_factory)
        return c, stand_in

    return make


def test_past_the_app_ceiling_the_built_in_coach_answers_and_the_paid_provider_is_not_called(paid_app):
    c, stand_in = paid_app(2)
    token = register(c)
    verify(c, token)
    h = auth_headers(token)
    answered = [hint(c, h, slug) for slug in SLUGS]
    assert [r.status_code for r in answered] == [200, 200, 200, 200]
    assert [r.json()["provider"] for r in answered] == [
        "anthropic",
        "anthropic",
        "offline (fallback)",
        "offline (fallback)",
    ]
    assert stand_in.calls == 2  # the refused ones never reached it
    assert counted(c) == 2  # and weren't counted, so the ceiling frees up on its own


def test_the_ceiling_is_one_for_the_whole_deployment(paid_app):
    """Two accounts, and a second provider built from the same database (another API replica, or the
    worker): one counter between them."""
    c, stand_in = paid_app(2)
    a, b = register(c, email="ada@example.com"), register(c, email="bea@example.com")
    for t in (a, b):
        verify(c, t)
    assert hint(c, auth_headers(a), SLUGS[0]).json()["provider"] == "anthropic"
    replica_stand_in = Paid()
    replica_stand_in.hint = lambda ctx: setattr(replica_stand_in, "calls", replica_stand_in.calls + 1)
    replica = capped(replica_stand_in, c.app.state.settings, c.app.state.session_factory)
    replica.hint(None)  # the other replica's call takes the second
    assert replica_stand_in.calls == 1
    assert hint(c, auth_headers(b), SLUGS[0]).json()["provider"] == "offline (fallback)"
    assert stand_in.calls == 1


def test_a_ceiling_of_zero_means_no_paid_calls_at_all(paid_app):
    c, stand_in = paid_app(0)
    token = register(c)
    verify(c, token)
    assert hint(c, auth_headers(token), SLUGS[0]).json()["provider"] == "offline (fallback)"
    assert stand_in.calls == 0


def test_the_offline_coach_is_left_as_it_is_and_the_api_and_worker_wrap_a_paid_one(make_client, monkeypatch):
    c = make_client()
    offline = OfflineCoach()
    assert capped(offline, c.app.state.settings, c.app.state.session_factory) is offline
    # The worker's housekeeping builds its own provider: it gets the same ceiling.
    seen = {}

    def fake_close(factory, settings, provider):
        seen["provider"] = provider
        return 0

    monkeypatch.setattr("app.services.interviews.close_overdue", fake_close)
    monkeypatch.setattr("app.services.ai.service.build_provider", lambda settings: Paid())
    close_interviews(c.app.state.session_factory, c.app.state.settings)
    assert isinstance(seen["provider"], SpendCappedProvider)


def test_an_unverified_account_gets_the_smaller_allowance_until_it_verifies(make_client):
    c = make_client(ai_daily_request_limit=5, ai_unverified_daily_request_limit=2)
    token = register(c)
    h = auth_headers(token)
    assert c.get("/api/v1/ai/usage", headers=h).json()["daily_limit"] == 2
    assert [hint(c, h, s).status_code for s in SLUGS[:2]] == [200, 200]
    refused = hint(c, h, SLUGS[2])
    assert refused.status_code == 429
    assert "Verify your email address" in refused.json()["error"]["message"]
    verify(c, token)
    usage = c.get("/api/v1/ai/usage", headers=h).json()
    assert (usage["daily_limit"], usage["remaining_today"]) == (5, 3)
    assert hint(c, h, SLUGS[2]).status_code == 200


def test_a_guest_gets_the_smaller_allowance(make_client):
    c = make_client(ai_daily_request_limit=5, ai_unverified_daily_request_limit=1)
    h = auth_headers(c.post("/api/v1/auth/guest").json())
    assert c.get("/api/v1/ai/usage", headers=h).json()["daily_limit"] == 1
    assert hint(c, h, SLUGS[0]).status_code == 200
    refused = hint(c, h, SLUGS[1])
    assert refused.status_code == 429 and "guest session" in refused.json()["error"]["message"]


def test_the_smaller_allowance_never_raises_the_full_one(make_client):
    c = make_client(ai_daily_request_limit=3, ai_unverified_daily_request_limit=10)
    h = auth_headers(register(c))
    assert c.get("/api/v1/ai/usage", headers=h).json()["daily_limit"] == 3


def test_one_address_starts_only_so_many_guest_sessions_a_day(make_client):
    c = make_client(guest_sessions_per_day=2)
    assert [c.post("/api/v1/auth/guest").status_code for _ in range(2)] == [201, 201]
    refused = c.post("/api/v1/auth/guest")
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "guest_sessions_limited"
    assert int(refused.headers["Retry-After"]) >= 1
    # Signing in or registering is still open.
    assert (
        c.post(
            "/api/v1/auth/register", json={"email": "ada@example.com", "password": "CorrectHorse42"}
        ).status_code
        == 201
    )


def test_a_guest_start_sent_again_resumes_and_isnt_counted_again(make_client):
    c = make_client(guest_sessions_per_day=1)
    assert c.post("/api/v1/auth/create-anchor").status_code in (200, 201, 204)
    first = c.post("/api/v1/auth/guest")
    assert first.status_code == 201
    again = c.post("/api/v1/auth/guest")  # the reply was lost; the same browser sends it again
    assert again.status_code == 200 and again.headers.get("X-Account-Resumed") == "guest"
    assert again.json()["user"]["id"] == first.json()["user"]["id"]
