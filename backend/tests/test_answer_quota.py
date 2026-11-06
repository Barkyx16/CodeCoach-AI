"""The hourly answer allowance around replays and failures (Verification brief 08).

What is charged, as implemented (and documented in docs/RELEASE_READINESS.md §11): every request
that reaches the limiter, which is after the replay lookup and the retirement check and before
grading. So a replay of a saved request and a key conflict are free, while a new answer, a save
that fails while grading, and each copy of a duplicate that got past the lookup at once are
charged. Each test checks the saved rows and the allowance left (by how many new answers are
still accepted), not only response codes. Synthetic data only."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.careers import answers as answers_module
from app.careers.questions import questions_for
from app.models import PracticeAnswer
from tests.conftest import auth_headers, register

TEXT = (
    "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his "
    "observations again, raised the bed, started oxygen as prescribed and called the doctor using SBAR. Within "
    "the hour his saturation was back to 96%, and I learned to escalate early rather than wait to be certain."
)
URL = f"/api/v1/careers/registered-nurse/questions/{questions_for('registered-nurse')[0].id}/answers"


def _rows(c) -> int:
    db = c.app.state.session_factory()
    try:
        return db.query(PracticeAnswer).count()
    finally:
        db.close()


def _left(c, h) -> int:
    """How many new answers are still accepted (each probe that's accepted uses one)."""
    n = 0
    while c.post(URL, headers=h, json={"answer": f"{TEXT} Probe {n}."}).status_code == 201:
        n += 1
    return n


def test_replays_and_conflicts_are_free_and_answered_after_the_allowance_is_used(make_client):
    c = make_client(practice_answers_per_hour=3)
    h = auth_headers(register(c))
    body = {"answer": TEXT, "client_request_id": "op-quota-0000001"}
    assert c.post(URL, headers=h, json=body).status_code == 201  # charged: 1
    for _ in range(5):
        assert c.post(URL, headers=h, json=body).status_code == 200  # replays: free
        assert c.post(URL, headers=h, json={**body, "answer": TEXT + " x"}).status_code == 409  # free
    assert _left(c, h) == 2 and _rows(c) == 3
    # The allowance is used up: a new answer is refused and saves nothing; the replay still works.
    r = c.post(URL, headers=h, json={"answer": TEXT + " New."})
    assert r.status_code == 429 and _rows(c) == 3
    assert c.post(URL, headers=h, json=body).status_code == 200


def test_a_save_that_fails_while_grading_is_charged(make_client, monkeypatch):
    """Current policy, not a bug fixed here: the limiter counts before grading, so a server-side
    failure uses one of the hour's answers. Changing that is a product decision (§11)."""
    c = make_client(practice_answers_per_hour=3)
    h = auth_headers(register(c))

    def fails(*a, **k):
        raise RuntimeError("grading failed")

    monkeypatch.setattr("app.api.routes.careers.graded_answer", fails)
    with pytest.raises(RuntimeError):
        c.post(URL, headers=h, json={"answer": TEXT, "client_request_id": "op-quota-fail-01"})
    monkeypatch.undo()
    assert _rows(c) == 0
    assert _left(c, h) == 2  # 3 - the failed attempt


def test_each_copy_of_a_duplicate_past_the_lookup_is_charged_but_one_row_is_saved(make_client, monkeypatch):
    c = make_client(practice_answers_per_hour=4)
    h = auth_headers(register(c))
    barrier = threading.Barrier(2, timeout=10)
    real = answers_module.graded_answer

    def graded_after_both_arrive(*args, **kwargs):
        barrier.wait()
        return real(*args, **kwargs)

    monkeypatch.setattr("app.api.routes.careers.graded_answer", graded_after_both_arrive)
    body = {"answer": TEXT, "client_request_id": "op-quota-race-001"}
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: c.post(URL, headers=h, json=body), range(2)))
    monkeypatch.undo()
    assert sorted(r.status_code for r in replies) == [200, 201] and _rows(c) == 1
    assert _left(c, h) == 2  # 4 - both copies
