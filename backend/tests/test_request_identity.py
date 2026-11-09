"""A request key stands for one account's one intent (Volume 8, prompt 2; docs/RECOVERY.md).

- Sent again unchanged (its reply was lost), a keyed request gets the first result back: nothing
  is done or charged twice.
- The same key with a different intent (other code, level, problem, submission, words, target) is
  refused with 409 `idempotency_key_reused`: never answered with the old result, never executed,
  never charged. That's a different refusal from an editor's revision conflict.
- Two copies at once are admitted once: one provider call (PostgreSQL), one row, one budget use.
- While a coaching request is still being answered, the lookup says so instead of "no record".
- A key is the caller's own: another account's identical key, or another reviewer's on a shared
  link, finds nothing of the first and reveals nothing about it.
- A blank key is no key.
Synthetic accounts, the offline coach or a synthetic provider; nothing is sent anywhere."""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.db import rls
from app.models import (
    AIInteraction,
    Application,
    DrillAttempt,
    ExperienceEntry,
    ScheduleEntry,
    ShareFeedback,
)
from app.services.ai.base import ProviderResult
from app.services.ai.offline import OfflineCoach
from tests.conftest import TEST_DATABASE_URL, auth_headers, register
from tests.test_interview_continuity import ai_calls, start_coding
from tests.test_shares import answer_question, feedback, nurse, share

CODE = "class Solution { public int[] twoSum(int[] nums, int target) { return new int[0]; } }"
OTHER_CODE = CODE.replace("new int[0]", "new int[] {0, 1}")
PG = bool(TEST_DATABASE_URL)


@pytest.fixture
def calls(monkeypatch) -> dict[str, int]:
    counted = {"hint": 0, "review": 0}
    for name in counted:
        original = getattr(OfflineCoach, name)

        def wrapper(self, ctx, _original=original, _name=name):
            counted[_name] += 1
            return _original(self, ctx)

        monkeypatch.setattr(OfflineCoach, name, wrapper)
    return counted


def hint(c, h, level=1, key=None, code=CODE, slug="two-sum"):
    body = {"problem_slug": slug, "level": level, "source_code": code}
    if key is not None:
        body["client_request_id"] = key
    return c.post("/api/v1/ai/hint", headers=h, json=body)


def review(c, h, key=None, code=CODE, submission_id=None):
    body = {"problem_slug": "two-sum", "source_code": code, "submission_id": submission_id}
    if key is not None:
        body["client_request_id"] = key
    return c.post("/api/v1/ai/review", headers=h, json=body)


def rows(c, model) -> int:
    with c.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(model)) or 0


def used(c, h) -> int:
    return c.get("/api/v1/ai/usage", headers=h).json()["used_today"]


def refused(r) -> bool:
    return r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"


# --- coaching: the key covers the code, level, problem and submission ----------------------------


def test_a_hint_key_resent_with_other_code_or_level_is_refused_and_not_charged(client, user_headers, calls):
    h = user_headers
    first = hint(client, h, key="hint-key-0001")
    assert first.status_code == 200 and calls["hint"] == 1 and used(client, h) == 1
    assert hint(client, h, key="hint-key-0001").json() == first.json()  # the same request: replayed
    for r in (
        hint(client, h, key="hint-key-0001", code=OTHER_CODE),  # changed code
        hint(client, h, key="hint-key-0001", level=2),  # another level
        hint(client, h, key="hint-key-0001", slug="valid-parentheses"),  # another problem
        review(client, h, key="hint-key-0001"),  # another action
    ):
        assert refused(r), r.text
        assert "hint" not in r.text.lower().replace("request key", "")  # nothing about what it made
    assert calls == {"hint": 1, "review": 0} and used(client, h) == 1 and rows(client, AIInteraction) == 1


def test_a_review_key_is_bound_to_its_code_and_submission(client, user_headers, calls):
    h = user_headers
    sub = client.post(
        "/api/v1/submissions",
        headers=h,
        json={"problem_slug": "two-sum", "language": "java", "source_code": CODE},
    )
    assert sub.status_code == 202, sub.text
    sid = sub.json()["id"]
    first = review(client, h, key="review-key-01", submission_id=sid)
    assert first.status_code == 200
    assert (
        review(client, h, key="review-key-01", submission_id=sid).json()["review"] == first.json()["review"]
    )
    assert refused(review(client, h, key="review-key-01"))  # the same code, but not about that submission
    assert refused(review(client, h, key="review-key-01", code=OTHER_CODE, submission_id=sid))
    assert calls["review"] == 1 and rows(client, AIInteraction) == 1


def test_older_rows_without_a_fingerprint_are_matched_as_before(client, user_headers, calls):
    """Rows saved before this release carry no fingerprint: they're matched on action, problem and
    level, as they always were, so a resend from an older page still gets its answer."""
    h = user_headers
    first = hint(client, h, key="legacy-key-01")
    with client.app.state.session_factory() as db:
        db.execute(update(AIInteraction).values(request_fingerprint=None))
        db.commit()
    assert hint(client, h, key="legacy-key-01", code=OTHER_CODE).json() == first.json()
    assert refused(hint(client, h, key="legacy-key-01", level=2))
    assert calls["hint"] == 1


def test_the_fingerprint_is_kept_as_a_digest_and_never_shown(client, user_headers):
    h = user_headers
    hint(client, h, key="digest-key-01", code=CODE + " // PRIVATE-MARKER")
    with client.app.state.session_factory() as db:
        stored = db.scalar(select(AIInteraction.request_fingerprint))
    assert stored and stored.startswith("v1:") and len(stored) == 67 and "PRIVATE" not in stored
    history = client.get("/api/v1/me/ai-history", headers=h).text
    outcome = client.get("/api/v1/me/requests/digest-key-01", headers=h).text
    exported = client.get("/api/v1/me/export", headers=h).text
    for text in (history, outcome, exported):
        assert stored not in text and stored[3:] not in text


def test_the_same_key_raced_by_a_different_request_is_refused_not_returned(client, user_headers, monkeypatch):
    """The race path: between this request's check and its insert, another request with the same
    key and a different intent is saved. The unique key keeps that one, and this request is
    refused: it never returns the other's answer, and it isn't charged."""
    h = user_headers
    user_id = client.get("/api/v1/auth/me", headers=h).json()["id"]
    original = OfflineCoach.hint

    def plant_then_answer(self, ctx):
        with Session(client.app.state.engine) as other:
            rls.bind_user(other, user_id)
            planted = other.scalar(select(AIInteraction).limit(1))  # a template from the first hint
            assert planted is not None
            other.add(
                AIInteraction(
                    user_id=user_id,
                    problem_id=planted.problem_id,
                    action=planted.action,
                    hint_level=2,
                    provider="offline",
                    model="offline",
                    response=planted.response,
                    client_request_id="raced-key-001",
                    request_fingerprint="v1:" + "0" * 64,
                )
            )
            other.commit()
        return original(self, ctx)

    assert hint(client, h, level=1).status_code == 200  # level 1 unlocked, and a template row
    monkeypatch.setattr(OfflineCoach, "hint", plant_then_answer)
    r = hint(client, h, level=2, key="raced-key-001")
    assert refused(r), r.text
    assert rows(client, AIInteraction) == 2  # the first hint and the planted one; nothing of ours
    assert used(client, h) == 2


class GatedCoach:
    """A synthetic provider that waits until the test lets it answer, so two requests overlap
    for certain (synchronized, no sleeping)."""

    name, model = "synthetic", "gated"

    def __init__(self) -> None:
        self.entered = threading.Semaphore(0)
        self.release = threading.Event()
        self.calls = 0
        self._lock = threading.Lock()

    def hint(self, ctx):
        with self._lock:
            self.calls += 1
        self.entered.release()
        assert self.release.wait(10)
        result = OfflineCoach().hint(ctx)
        return ProviderResult(result.content, self.name, self.model)


def test_simultaneous_copies_of_one_request_are_admitted_once(make_client):
    c = make_client(ai_daily_request_limit=5)
    h = auth_headers(register(c))
    gate = GatedCoach()
    c.app.state.ai_provider = gate
    out: dict[str, object] = {}

    def send(name):
        out[name] = hint(c, h, key="twin-key-0001")

    threads = [threading.Thread(target=send, args=("first",), daemon=True)]
    threads[0].start()
    try:
        assert gate.entered.acquire(timeout=10)  # the first copy is inside the provider call
        if PG:
            # The per-user turn is held for the whole call: the second copy isn't admitted at all.
            second = hint(c, h, key="twin-key-0001")
            assert second.status_code == 429 and second.json()["error"]["code"] == "ai_request_in_progress"
            assert second.headers["Retry-After"]
            # A reloaded page asking what the key made is told it's still being answered, not "no
            # record".
            lookup = c.get("/api/v1/me/requests/twin-key-0001", headers=h)
            assert lookup.status_code == 429 and lookup.json()["error"]["code"] == "request_in_progress"
        else:
            # SQLite (local runs) has no such lock: the second copy runs too, and the unique key
            # keeps one answer, one row and one budget use. The provider may be called twice here.
            threads.append(threading.Thread(target=send, args=("second",), daemon=True))
            threads[1].start()
            assert gate.entered.acquire(timeout=10)
    finally:
        # Whatever happened above, let the gated calls finish, so a failure is reported as one
        # and never leaves a request waiting.
        gate.release.set()
        for t in threads:
            t.join(15)
    if not PG:
        second = out["second"]
        assert second.status_code == 200 and second.json() == out["first"].json()  # type: ignore[union-attr]
    answered = out["first"]
    assert answered.status_code == 200  # type: ignore[union-attr]
    again = hint(c, h, key="twin-key-0001")
    assert again.status_code == 200 and again.json() == answered.json()  # type: ignore[union-attr]
    assert rows(c, AIInteraction) == 1 and used(c, h) == 1
    assert gate.calls == (1 if PG else 2)
    assert c.get("/api/v1/me/requests/twin-key-0001", headers=h).json()["state"] == "done"


def test_a_failure_before_completion_records_nothing_and_charges_nothing(client, user_headers, monkeypatch):
    """Interrupted after the provider answered but before the answer was saved: the transaction
    is rolled back, so nothing is recorded or charged and the key is free for the same request.
    (A real provider may have run that first call: it's billed by them, but not counted here.)"""
    from app.services.ai.service import CoachService

    h = user_headers

    def crash(self, *args, **kwargs):
        raise RuntimeError("synthetic crash after the provider answered")

    monkeypatch.setattr(CoachService, "_event", crash)
    with pytest.raises(RuntimeError):
        hint(client, h, key="crash-key-0001")
    assert rows(client, AIInteraction) == 0 and used(client, h) == 0
    lookup = client.get("/api/v1/me/requests/crash-key-0001", headers=h)
    assert lookup.status_code == 404  # no lock left behind, and no record
    monkeypatch.undo()
    assert hint(client, h, key="crash-key-0001").status_code == 200
    assert rows(client, AIInteraction) == 1 and used(client, h) == 1


def test_a_provider_failure_is_answered_by_the_fallback_once(client, user_headers):
    from app.services.ai.base import ProviderError

    class Failing:
        name, model = "anthropic", "synthetic"

        def hint(self, ctx):
            raise ProviderError("synthetic timeout", reason="timeout")

    client.app.state.ai_provider = Failing()
    h = user_headers
    first = hint(client, h, key="fallback-key1")
    again = hint(client, h, key="fallback-key1")
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    assert first.json()["provider"] == "offline (fallback)"
    assert rows(client, AIInteraction) == 1 and used(client, h) == 1


def test_once_the_record_is_gone_the_key_finds_nothing_and_a_resend_is_new(client, user_headers, calls):
    """Replay lasts as long as the record it made (until the account, or a guest after its
    retention, is deleted); the browser asks for at most 24 hours. Once the record is gone the
    lookup says so, and sending again is a new request, charged once."""
    h = user_headers
    hint(client, h, key="expired-key-1")
    with client.app.state.session_factory() as db:
        db.execute(delete(AIInteraction))
        db.commit()
    assert client.get("/api/v1/me/requests/expired-key-1", headers=h).status_code == 404
    assert hint(client, h, key="expired-key-1").status_code == 200
    assert calls["hint"] == 2 and rows(client, AIInteraction) == 1


# --- other keyed creates ---------------------------------------------------------------------------


def test_a_story_key_resent_with_other_content_is_refused(client, user_headers):
    url, h = "/api/v1/me/stories", user_headers
    body = {
        "title": "Calmed a busy ward",
        "situation": "Two call lights at once.",
        "client_request_id": "story-key-01",
    }
    first = client.post(url, headers=h, json=body)
    assert client.post(url, headers=h, json=body).json()["id"] == first.json()["id"]
    assert refused(client.post(url, headers=h, json={**body, "situation": "Something else entirely."}))
    # Edited since, the story is still found by its create's key: replay compares with what the
    # create sent, not with the story as it is now.
    sid = first.json()["id"]
    client.patch(f"{url}/{sid}", headers=h, json={"title": "Calmed a very busy ward", "expected_revision": 1})
    assert client.post(url, headers=h, json=body).json()["id"] == sid
    assert rows(client, ExperienceEntry) == 1


def test_application_event_schedule_and_drill_keys_cover_their_content(client):
    h = nurse(client)
    url = "/api/v1/me/applications"
    app_body = {"employer": "Mercy General", "role_title": "Ward nurse", "client_request_id": "app-key-0001"}
    made = client.post(url, headers=h, json=app_body)
    assert made.status_code == 201 and client.post(url, headers=h, json=app_body).status_code == 200
    assert refused(client.post(url, headers=h, json={**app_body, "employer": "St. Anne's"}))
    assert rows(client, Application) == 1

    events = f"{url}/{made.json()['id']}/events"
    ev = {"title": "First interview", "on_date": "2026-11-10", "client_request_id": "event-key-01"}
    assert client.post(events, headers=h, json=ev).status_code in (200, 201)
    assert len(client.post(events, headers=h, json=ev).json()["events"]) == 1
    assert refused(client.post(events, headers=h, json={**ev, "on_date": "2026-11-12"}))

    sched = {
        "kind": "question",
        "ref": "registered-nurse/m-pressure-0",
        "on_date": "2026-11-10",
        "all_day": True,
        "client_request_id": "sched-key-01",
    }
    first = client.post("/api/v1/me/schedule", headers=h, json=sched)
    assert first.status_code == 201, first.text
    assert client.post("/api/v1/me/schedule", headers=h, json=sched).json()["id"] == first.json()["id"]
    assert refused(client.post("/api/v1/me/schedule", headers=h, json={**sched, "on_date": "2026-11-11"}))
    assert rows(client, ScheduleEntry) == 1

    drills = "/api/v1/me/drills"
    words = {
        "text": "I'm a nurse and I want this role because I like acute care.",
        "client_request_id": "drill-key-1",
    }
    assert client.post(f"{drills}/intro/attempts", headers=h, json=words).status_code == 201
    assert client.post(f"{drills}/intro/attempts", headers=h, json=words).status_code == 200
    assert refused(
        client.post(f"{drills}/intro/attempts", headers=h, json={**words, "text": words["text"] + " Also."})
    )
    other_drill = next(d["id"] for d in client.get(drills, headers=h).json() if d["id"] != "intro")
    assert refused(client.post(f"{drills}/{other_drill}/attempts", headers=h, json=words))
    assert rows(client, DrillAttempt) == 1


def test_two_simultaneous_events_with_one_key_make_one_event(client):
    """Before, the second copy's insert broke the unique key and came back as a 500."""
    h = nurse(client)
    app_id = client.post(
        "/api/v1/me/applications", headers=h, json={"employer": "Mercy", "role_title": "RN"}
    ).json()["id"]
    url = f"/api/v1/me/applications/{app_id}/events"
    body = {"title": "Phone screen", "on_date": "2026-11-10", "client_request_id": "twin-event-1"}
    start = threading.Barrier(2)
    out: list = []

    def send():
        start.wait(5)
        out.append(client.post(url, headers=h, json=body))

    threads = [threading.Thread(target=send) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert sorted(r.status_code for r in out) in ([200, 200], [200, 201], [201, 201]), [r.text for r in out]
    events = client.get(f"/api/v1/me/applications/{app_id}", headers=h).json()["events"]
    assert len([e for e in events if e["title"] == "Phone screen"]) == 1


def test_a_note_key_may_carry_newer_text_but_not_another_source(client, user_headers):
    """Autosave resends a lost create with the newer text, gets the note back, then saves the
    text as an update. So the text may change under one key; the thing it's a note on may not."""
    url, h = "/api/v1/me/notes", user_headers
    src = {"type": "problem", "id": "two-sum"}
    first = client.post(
        url, headers=h, json={"body": "first", "source": src, "client_request_id": "note-key-001"}
    )
    newer = client.post(
        url, headers=h, json={"body": "first, then more", "source": src, "client_request_id": "note-key-001"}
    )
    assert newer.json()["id"] == first.json()["id"]
    other = {"type": "problem", "id": "valid-parentheses"}
    assert refused(
        client.post(url, headers=h, json={"body": "x", "source": other, "client_request_id": "note-key-001"})
    )


def test_an_interview_message_key_with_other_words_is_refused(client):
    h = auth_headers(register(client))
    iv = start_coding(client, h).json()
    url = f"/api/v1/interviews/{iv['id']}/messages"
    body = {
        "message": "Can the array be empty?",
        "after_seq": len(iv["turns"]),
        "client_request_id": "msg-key-00001",
    }
    first = client.post(url, headers=h, json=body)
    assert first.status_code == 200
    spent = ai_calls(client)
    r = client.post(url, headers=h, json={**body, "message": "Can it have duplicates?"})
    # Not the editor's "the interview moved on" (interview_advanced): the key was reused.
    assert refused(r) and ai_calls(client) == spent
    assert len(client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["turns"]) == len(
        first.json()["turns"]
    )


def test_share_feedback_replays_only_for_the_same_reviewer_and_words(client):
    h = nurse(client)
    token = share(client, h, answer_question(client, h)["id"])["token"]
    client.cookies.clear()
    bea = nurse(client, email="bea@example.com", name="Bea")
    client.cookies.clear()
    cy = nurse(client, email="cy@example.com", name="Cy")
    mine = feedback(
        client, token, headers=bea, client_request_id="review-key-1", clear="Bea's private words."
    )
    assert mine.status_code == 201
    assert (
        feedback(
            client, token, headers=bea, client_request_id="review-key-1", clear="Bea's private words."
        ).status_code
        == 200
    )
    # Another reviewer with Bea's key (guessed, or copied) gets a refusal that shows nothing of hers.
    for r in (
        feedback(client, token, headers=cy, client_request_id="review-key-1", clear="Cy's words."),
        feedback(client, token, headers=cy, client_request_id="review-key-1", clear="Bea's private words."),
        feedback(client, token, client_request_id="review-key-1", clear="Bea's private words."),  # signed out
    ):
        assert refused(r), r.text
        assert "Bea" not in r.text and mine.json()["feedback"]["id"] not in r.text
    assert rows(client, ShareFeedback) == 1


def test_a_blank_key_is_no_key(client):
    """Stored as-is, "" was one shared key: a second, different entry came back as the first."""
    h = nurse(client)
    a = client.post(
        "/api/v1/me/applications",
        headers=h,
        json={"employer": "A", "role_title": "RN", "client_request_id": ""},
    )
    b = client.post(
        "/api/v1/me/applications",
        headers=h,
        json={"employer": "B", "role_title": "RN", "client_request_id": "  "},
    )
    assert a.status_code == b.status_code == 201 and a.json()["id"] != b.json()["id"]
    base = {
        "kind": "question",
        "ref": "registered-nurse/m-pressure-0",
        "all_day": True,
        "client_request_id": "",
    }
    s1 = client.post("/api/v1/me/schedule", headers=h, json={**base, "on_date": "2026-11-10"})
    s2 = client.post("/api/v1/me/schedule", headers=h, json={**base, "on_date": "2026-11-11"})
    assert s1.status_code == s2.status_code == 201 and s1.json()["id"] != s2.json()["id"]
    with client.app.state.session_factory() as db:
        assert db.scalars(select(Application.client_request_id)).all() == [None, None]
