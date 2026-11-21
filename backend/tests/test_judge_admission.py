"""Judge admission states and honest retry timing (Volume 8, prompt 7; docs/RECOVERY.md).

- A full queue (503 judge_busy) carries a wait only when the server can justify one: the average
  gap between the judge's recent completions, bounded 5..120 s. Nothing finished recently (the
  judge may be down): no Retry-After, rather than an invented countdown.
- "Still being judged" (429 submission_pending) names the caller's own pending submission, so the
  page leads back to it; it gives no wait, since how long judging takes isn't known.
- A rejected request is not a job: nothing is saved, and its key isn't used up.
- Run while the judge is unavailable, and anything when it isn't configured: 503 without a wait.
- Two tabs pressing at once are admitted one at a time (PostgreSQL)."""

from __future__ import annotations

import contextlib
import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import Problem, Submission, SubmissionStatus
from app.services.judge import backends
from tests.conftest import TEST_DATABASE_URL, auth_headers, register
from tests.judge_fakes import submit

OK = lambda f, n: ("ok", "", {})  # noqa: E731


def keyed(c, h, key, code="class Solution { /* a */ }", mode="submit"):
    return c.post(
        "/api/v1/submissions",
        headers=h,
        json={"problem_slug": "two-sum", "source_code": code, "client_request_id": key, "mode": mode},
    )


def judged_recently(c, count: int) -> None:
    """`count` submissions (someone else's) finished a minute ago."""
    user_id = register(c, email=f"judged{count}@example.com")["user"]["id"]
    with c.app.state.session_factory() as db:
        problem_id = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        at = datetime.now(UTC) - timedelta(minutes=1)
        db.add_all(
            Submission(
                user_id=user_id,
                problem_id=problem_id,
                source_code="class Solution {}",
                status=SubmissionStatus.PASSED,
                judged_at=at,
            )
            for _ in range(count)
        )
        db.commit()


def fill_queue(c) -> None:
    filler = auth_headers(register(c, email="filler@example.com"))
    assert submit(c, filler, code="class Solution { /* filler */ }").status_code == 202


def saved(c) -> int:
    with c.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(Submission)) or 0


def test_a_full_queue_gives_a_measured_bounded_wait(judged):
    c, _, _, h = judged(OK, max_queue_depth=1)
    judged_recently(c, 10)  # one every 30 s over the last 5 minutes
    fill_queue(c)
    before = saved(c)
    busy = submit(c, h)
    assert busy.status_code == 503 and busy.json()["error"]["code"] == "judge_busy"
    assert (
        busy.headers["Retry-After"] == "30" and busy.json()["error"]["details"]["retry_after_seconds"] == 30
    )
    assert "Nothing was saved" in busy.json()["error"]["message"] and saved(c) == before


@pytest.mark.parametrize(("finished", "wait"), [(1, "120"), (200, "5")])
def test_the_busy_wait_is_bounded_both_ways(judged, finished, wait):
    c, _, _, h = judged(OK, max_queue_depth=1)
    judged_recently(c, finished)
    fill_queue(c)
    assert submit(c, h).headers["Retry-After"] == wait


def test_a_full_queue_with_nothing_finished_recently_gives_no_wait(judged):
    c, _, _, h = judged(OK, max_queue_depth=1)
    fill_queue(c)
    busy = submit(c, h)
    assert busy.status_code == 503 and busy.json()["error"]["code"] == "judge_busy"
    assert "Retry-After" not in busy.headers and busy.json()["error"]["details"] is None


def test_still_being_judged_leads_back_to_the_callers_own_submission(judged):
    c, _, _, h = judged(OK, max_pending_per_user=1)
    first = submit(c, h).json()
    # Someone else's pending submission is never named.
    other = auth_headers(register(c, email="someone@example.com"))
    submit(c, other)
    again = submit(c, h, code="class Solution { /* changed */ }")
    assert again.status_code == 429 and "Retry-After" not in again.headers
    details = again.json()["error"]["details"]
    assert details == {
        "max_pending": 1,
        "pending_submission_id": first["id"],
        "problem_slug": "two-sum",
        "mode": "submit",
    }


def test_a_rejected_request_is_not_a_job_and_its_key_is_not_used_up(judged):
    c, _, worker, h = judged(OK, max_queue_depth=1)
    fill_queue(c)
    before = saved(c)
    assert keyed(c, h, "busy-key-0001").status_code == 503
    assert saved(c) == before
    worker.process_one()  # the queue moves
    retry = keyed(c, h, "busy-key-0001")
    assert retry.status_code == 202 and saved(c) == before + 1


def test_the_same_key_after_an_unknown_outcome_finds_the_job_even_when_admission_is_full(judged):
    c, _, _, h = judged(OK, max_pending_per_user=1, max_queue_depth=1)
    first = keyed(c, h, "lost-reply-001")
    assert first.status_code == 202  # ...and suppose its reply was lost
    again = keyed(c, h, "lost-reply-001")
    assert again.status_code == 202 and again.json()["id"] == first.json()["id"]
    assert saved(c) == 1


def test_run_while_unavailable_or_not_configured_gives_no_wait(judged, make_client):
    c, _, _, h = judged(OK)
    c.app.state.execution_health.probe = lambda: False
    c.app.state.execution_health.forget()
    down = keyed(c, h, "run-down-0001", mode="run")
    assert down.status_code == 503 and down.json()["error"]["code"] == "judge_unavailable"
    assert "Retry-After" not in down.headers
    off_client = make_client()  # EXECUTION_ENABLED false
    off_headers = auth_headers(register(off_client, email="nojudge@example.com"))
    off = keyed(off_client, off_headers, "run-off-0001", mode="run")
    assert off.status_code == 503 and off.json()["error"]["code"] == "execution_disabled"
    assert "Retry-After" not in off.headers


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="concurrent writers: PostgreSQL")
def test_two_tabs_pressing_at_once_are_admitted_one_at_a_time(judged, monkeypatch):
    c, _, _, h = judged(OK, max_pending_per_user=1)
    # Both requests reach the admission checks together unless the account's lock makes the
    # second wait for the first to commit (the barrier then times out, and it goes on alone).
    meet = threading.Barrier(2)
    real = backends._check_rate

    def rendezvous(db, user, limit):
        with contextlib.suppress(threading.BrokenBarrierError):
            meet.wait(1.5)
        real(db, user, limit)

    monkeypatch.setattr(backends, "_check_rate", rendezvous)
    out: list = []

    def press(code):
        out.append(submit(c, h, code=code))

    tabs = [
        threading.Thread(target=press, args=(f"class Solution {{ /* tab {i} */ }}",), daemon=True)
        for i in (1, 2)
    ]
    for t in tabs:
        t.start()
    for t in tabs:
        t.join(15)
    assert sorted(r.status_code for r in out) == [202, 429], [r.text for r in out]
    assert saved(c) == 1
