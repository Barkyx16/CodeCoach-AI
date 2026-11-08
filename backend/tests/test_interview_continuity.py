"""Interview continuity across tabs and devices: the server decides, whatever the request timing.

- One interview in progress per user is a database rule (a partial unique index), so two Starts
  at once make one interview, and the AI is asked for one opening turn.
- A Start while one is live returns 409 with what's needed to recognize and resume it.
- One turn per position: two answers to the same question at once are stored once. A different
  answer from a stale tab is refused (409) so its text isn't silently lost.
- A coding message written against an older transcript is refused (409 interview_advanced). A
  resent message (same client_request_id) gets the current state, not a second AI reply.
- Closing is a compare-and-set: two Finishes at once evaluate once.
- Only the owner can read, resume or answer.

Deterministic races: a barrier holds both requests past the "is one live?" or "already answered?"
lookup before either writes, so the database's constraints have to decide (the same technique as
tests/test_answer_keys.py). Synthetic accounts only; runs on SQLite and on PostgreSQL."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.models import (
    AIInteraction,
    InterviewStatus,
    InterviewTurn,
    PracticeAnswer,
    PracticeSession,
    ProgressEvent,
    ProgressEventType,
    TurnRole,
)
from app.services.interviews import InterviewService
from app.services.question_rounds import QuestionRounds
from tests.conftest import auth_headers, register
from tests.test_storage import needs_admin, rehearsal, run  # noqa: F401  (rehearsal: a fixture)

ROUND_ANSWER = (
    "I would first check the patient's vital signs and airway, then escalate to the charge nurse "
    "and document what I observed, because patient safety comes first and the team needs to know."
)


def start_round(c, h):
    return c.post("/api/v1/interviews", headers=h, json={"kind": "questions", "track": "registered-nurse"})


def start_coding(c, h):
    return c.post("/api/v1/interviews", headers=h, json={"problem_slug": "two-sum"})


def answer(c, h, iv_id, index, text=ROUND_ANSWER):
    return c.post(
        f"/api/v1/interviews/{iv_id}/answers", headers=h, json={"question_index": index, "answer": text}
    )


def live_count(c) -> int:
    with c.app.state.session_factory() as db:
        return db.scalar(
            select(func.count())
            .select_from(PracticeSession)
            .where(PracticeSession.status == InterviewStatus.IN_PROGRESS, PracticeSession.mode != "practice")
        )


def ai_calls(c) -> int:
    with c.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(AIInteraction)) or 0


def both_past(monkeypatch, cls, name):
    """Hold two requests inside `cls.name` until both have arrived, then let them race."""
    barrier = threading.Barrier(2, timeout=15)
    real = getattr(cls, name)

    def held(self, *args, **kwargs):
        barrier.wait()
        return real(self, *args, **kwargs)

    monkeypatch.setattr(cls, name, held)


def test_two_round_starts_at_once_make_one_interview_and_the_other_gets_a_resume_card(
    make_client, monkeypatch
):
    c = make_client()
    h = auth_headers(register(c))
    both_past(monkeypatch, QuestionRounds, "start")  # both past the "is one live?" lookup
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: start_round(c, h), range(2)))
    assert sorted(r.status_code for r in replies) == [201, 409]
    won = next(r for r in replies if r.status_code == 201).json()
    lost = next(r for r in replies if r.status_code == 409).json()["error"]
    assert lost["code"] == "interview_in_progress" and lost["details"]["interview_id"] == won["id"]
    card = lost["details"]["interview"]  # enough to recognize and resume it
    assert (
        card["kind"] == "questions"
        and card["career_title"]
        and card["progress_total"] == len(won["questions"])
    )
    assert card["progress_done"] == 0 and 0 < card["seconds_remaining"] <= won["duration_seconds"]
    assert card["last_activity_at"]
    assert live_count(c) == 1


def test_two_coding_starts_at_once_make_one_interview_and_ask_the_ai_once(make_client, monkeypatch):
    c = make_client()
    h = auth_headers(register(c))
    both_past(monkeypatch, InterviewService, "_pick_problem")
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: start_coding(c, h), range(2)))
    assert sorted(r.status_code for r in replies) == [201, 409]
    assert next(r for r in replies if r.status_code == 409).json()["error"]["code"] == "interview_in_progress"
    assert live_count(c) == 1
    assert ai_calls(c) == 1  # one opening turn: the loser never reached the AI


def test_a_start_after_a_lost_response_finds_the_interview_it_made(client):
    h = auth_headers(register(client))
    first = start_round(client, h)
    again = start_round(client, h)  # the first response never arrived; the learner clicks again
    assert again.status_code == 409 and again.json()["error"]["details"]["interview_id"] == first.json()["id"]
    assert live_count(client) == 1


def test_the_resume_card_in_the_list_shows_progress_time_and_activity(client):
    h = auth_headers(register(client))
    iv = start_round(client, h).json()
    answer(client, h, iv["id"], 0)
    [item] = client.get("/api/v1/interviews", headers=h).json()["items"]
    assert item["status"] == "in_progress" and item["progress_done"] >= 1
    assert item["progress_total"] == len(iv["questions"]) and item["seconds_remaining"] > 0
    assert item["last_activity_at"] >= iv["started_at"]


def test_two_answers_to_one_question_at_once_are_stored_once(make_client, monkeypatch):
    c = make_client()
    h = auth_headers(register(c))
    iv = start_round(c, h).json()
    import app.services.question_rounds as rounds

    barrier = threading.Barrier(2, timeout=15)
    real = rounds.graded_answer

    def graded_after_both_arrive(*args, **kwargs):  # both are past "already answered?"
        barrier.wait()
        return real(*args, **kwargs)

    monkeypatch.setattr(rounds, "graded_answer", graded_after_both_arrive)
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: answer(c, h, iv["id"], 0), range(2)))
    assert [r.status_code for r in replies] == [200, 200]  # the same text twice: a retry
    with c.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PracticeAnswer)) == 1
        replies_to_0 = db.scalar(
            select(func.count())
            .select_from(InterviewTurn)
            .where(InterviewTurn.role == TurnRole.CANDIDATE, InterviewTurn.question_index == 0)
        )
        assert replies_to_0 == 1


def test_a_different_answer_racing_the_first_is_refused_and_not_stored(make_client, monkeypatch):
    c = make_client()
    h = auth_headers(register(c))
    iv = start_round(c, h).json()
    import app.services.question_rounds as rounds

    barrier = threading.Barrier(2, timeout=15)
    real = rounds.graded_answer

    def graded_after_both_arrive(*args, **kwargs):
        barrier.wait()
        return real(*args, **kwargs)

    monkeypatch.setattr(rounds, "graded_answer", graded_after_both_arrive)
    texts = [ROUND_ANSWER, ROUND_ANSWER + " And I would follow up with the family afterwards."]
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda t: answer(c, h, iv["id"], 0, t), texts))
    assert sorted(r.status_code for r in replies) == [200, 409]
    refused = next(r for r in replies if r.status_code == 409).json()["error"]
    assert refused["code"] == "question_answered_elsewhere" and refused["details"]["question_index"] == 0
    with c.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PracticeAnswer)) == 1


def test_a_stale_coding_message_is_refused_and_a_resent_one_is_reconciled(client):
    h = auth_headers(register(client))
    iv = start_coding(client, h).json()
    url = f"/api/v1/interviews/{iv['id']}/messages"
    seen = len(iv["turns"])
    body = {
        "message": "Can the array be empty?",
        "after_seq": seen,
        "client_request_id": "tab-a-msg-00000001",
    }
    first = client.post(url, headers=h, json=body)
    assert first.status_code == 200
    calls = ai_calls(client)
    # The response was lost and the same message is sent again: the current state, no second reply.
    again = client.post(url, headers=h, json=body)
    assert again.status_code == 200 and len(again.json()["turns"]) == len(first.json()["turns"])
    assert ai_calls(client) == calls
    # Another tab, still showing the old transcript, sends its own message: refused, not appended.
    stale = client.post(
        url,
        headers=h,
        json={"message": "What about duplicates?", "after_seq": seen, "client_request_id": "tab-b-msg-1"},
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "interview_advanced"
    assert stale.json()["error"]["details"]["turns"] == len(first.json()["turns"])
    assert len(client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["turns"]) == len(
        first.json()["turns"]
    )
    assert ai_calls(client) == calls
    # Without after_seq (an older client) a message is still taken as before.
    assert client.post(url, headers=h, json={"message": "Can I use a hash map?"}).status_code == 200


def test_two_finishes_at_once_evaluate_once(make_client, monkeypatch):
    c = make_client()
    h = auth_headers(register(c))
    iv = start_coding(c, h).json()
    calls = ai_calls(c)
    both_past(monkeypatch, InterviewService, "_claim_close")  # both are past "still in progress?"
    url = f"/api/v1/interviews/{iv['id']}/finish"
    with ThreadPoolExecutor(2) as pool:
        replies = list(
            pool.map(lambda _: c.post(url, headers=h, json={"code": "class Solution {}"}), range(2))
        )
    assert [r.status_code for r in replies] == [200, 200]
    assert replies[0].json()["evaluation"] == replies[1].json()["evaluation"] is not None
    assert ai_calls(c) == calls + 1  # one evaluation
    with c.app.state.session_factory() as db:
        done = db.scalar(
            select(func.count())
            .select_from(ProgressEvent)
            .where(ProgressEvent.event_type == ProgressEventType.INTERVIEW_COMPLETED)
        )
        assert done == 1


def test_an_expired_interview_offers_results_not_a_dead_form(client):
    h = auth_headers(register(client))
    iv = start_round(client, h).json()
    with client.app.state.session_factory() as db:
        db.execute(
            update(PracticeSession)
            .where(PracticeSession.id == iv["id"])
            .values(deadline_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        db.commit()
    late = answer(client, h, iv["id"], 0)
    assert late.status_code == 409 and late.json()["error"]["code"] == "interview_closed"
    shown = client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()
    assert shown["status"] == "expired" and shown["seconds_remaining"] == 0
    [item] = client.get("/api/v1/interviews", headers=h).json()["items"]
    assert item["status"] == "expired" and item["seconds_remaining"] is None  # no resume card
    assert start_round(client, h).status_code == 201  # a new one can start


def test_only_the_owner_can_read_resume_or_answer(client):
    owner = auth_headers(register(client, email="owner@example.com"))
    other = auth_headers(register(client, email="other@example.com"))
    iv = start_round(client, owner).json()
    assert client.get(f"/api/v1/interviews/{iv['id']}", headers=other).status_code == 404
    assert answer(client, other, iv["id"], 0).status_code == 404
    assert client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=other).status_code == 404
    # The other account's Start isn't blocked by, and never learns about, the owner's interview.
    mine = start_round(client, other)
    assert mine.status_code == 201 and mine.json()["id"] != iv["id"]


def test_the_database_itself_refuses_a_second_live_interview_and_a_repeated_turn(client):
    h = auth_headers(register(client))
    iv = start_round(client, h).json()
    with client.app.state.session_factory() as db:
        live = db.get(PracticeSession, iv["id"])
        twin = PracticeSession(user_id=live.user_id, mode=live.mode, status=InterviewStatus.IN_PROGRESS)
        db.add(twin)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        db.add(InterviewTurn(session_id=iv["id"], seq=0, role=TurnRole.CANDIDATE, content="again"))
        with pytest.raises(IntegrityError):
            db.flush()


@needs_admin
def test_the_migration_repairs_duplicates_from_before_and_deletes_nothing(rehearsal):  # noqa: F811
    """PostgreSQL only: the repository's migrations build a schema from scratch on PostgreSQL
    (SQLite development databases are made from the models)."""
    url = rehearsal.admin
    run(["alembic", "upgrade", "4e5f6a7b8c9d"], url)
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id, email, auth_provider_id, is_guest, is_admin, token_version, created_at,"
                " career_track) VALUES ('u1', 'race@example.com', 'password:u1', false, false, 0,"
                " '2026-11-01 10:00:00+00', 'software-engineer')"
            )
        )
        for sid, started in (("old", "2026-11-01 10:00:00+00"), ("new", "2026-11-01 10:00:01+00")):
            db.execute(
                text(
                    "INSERT INTO practice_sessions (id, user_id, mode, status, started_at, track)"
                    " VALUES (:i, 'u1', 'questions', 'in_progress', :t, 'registered-nurse')"
                ),
                {"i": sid, "t": started},
            )
        for seq, role, content in (
            (0, "interviewer", "question 0"),
            (1, "candidate", "answer from tab A"),
            (1, "candidate", "answer from tab B"),
        ):  # B raced A to position 1
            db.execute(
                text(
                    "INSERT INTO interview_turns (session_id, seq, role, content, created_at)"
                    " VALUES ('new', :s, :r, :c, '2026-11-01 10:00:02+00')"
                ),
                {"s": seq, "r": role, "c": content},
            )
    run(["alembic", "upgrade", "head"], url)
    with engine.connect() as db:
        statuses = dict(db.execute(text("SELECT id, status FROM practice_sessions")).all())
        assert statuses == {"new": "in_progress", "old": "abandoned"}  # the newest stays live
        assert db.scalar(text("SELECT ended_at FROM practice_sessions WHERE id = 'old'")) is not None
        turns = db.execute(text("SELECT seq, content FROM interview_turns ORDER BY seq")).all()
        assert [tuple(t) for t in turns] == [
            (0, "question 0"),
            (1, "answer from tab A"),
            (2, "answer from tab B"),
        ]
    engine.dispose()
    run(["alembic", "downgrade", "4e5f6a7b8c9d"], url)  # and back: the constraints go, the data stays
