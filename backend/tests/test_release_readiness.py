"""Release Readiness briefs 04, 10 and 12: replay across upgrades, deletion and revision links,
and what a key does and doesn't promise. Synthetic accounts and answers only."""

from __future__ import annotations

import dataclasses

from app.careers.questions import get_question, questions_for
from app.models import PracticeAnswer
from tests.conftest import auth_headers, register

TRACK = "registered-nurse"
TEXT = (
    "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his "
    "observations again, raised the bed, started oxygen as prescribed and called the doctor using SBAR. Within "
    "the hour his saturation was back to 96%, and I learned to escalate early rather than wait to be certain."
)


def _qid() -> str:
    return questions_for(TRACK)[0].id


def _url() -> str:
    return f"/api/v1/careers/{TRACK}/questions/{_qid()}/answers"


def _rows(c) -> list[PracticeAnswer]:
    db = c.app.state.session_factory()
    try:
        return list(db.query(PracticeAnswer).order_by(PracticeAnswer.created_at).all())
    finally:
        db.close()


# --- brief 04: replay across upgrades ------------------------------------------------------------


def test_a_replay_after_the_question_changed_returns_the_answer_as_it_was_graded(client, monkeypatch):
    h = auth_headers(register(client))
    body = {"answer": TEXT, "client_request_id": "op-upgrade-0001"}
    first = client.post(_url(), headers=h, json=body).json()
    real = get_question(TRACK, _qid())
    changed = dataclasses.replace(real, version=real.version + 1)  # a content correction since
    monkeypatch.setattr("app.api.routes.careers.get_question", lambda *a, **k: changed)
    again = client.post(_url(), headers=h, json=body)
    assert again.status_code == 200 and again.headers["Idempotent-Replayed"] == "true"
    kept = again.json()
    assert kept["id"] == first["id"] and kept["content_version"] == real.version
    assert (kept["score"], kept["rubric_version"], kept["points"]) == (
        first["score"],
        first["rubric_version"],
        first["points"],
    )
    # A new try is graded against the changed question: the patch above was in effect.
    assert client.post(_url(), headers=h, json={"answer": TEXT}).json()["content_version"] == real.version + 1
    assert len(_rows(client)) == 2


def test_the_answer_text_is_compared_exactly_and_never_normalised(client):
    h = auth_headers(register(client))
    key = "op-exact-text-01"
    assert client.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": key}).status_code == 201
    for other in (TEXT + " ", TEXT.replace("ward I", "ward  I"), TEXT.replace("doctor", "Doctor")):
        r = client.post(_url(), headers=h, json={"answer": other, "client_request_id": key})
        assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"
    assert len(_rows(client)) == 1


def test_a_keyed_answer_without_a_fingerprint_is_never_taken_for_a_match(client):
    """A row with a key but no fingerprint can't be compared: refused, not treated as new."""
    h = auth_headers(register(client))
    body = {"answer": TEXT, "client_request_id": "op-no-fingerprint"}
    client.post(_url(), headers=h, json=body)
    db = client.app.state.session_factory()
    row = db.query(PracticeAnswer).one()
    row.request_fingerprint = None
    db.commit()
    db.close()
    r = client.post(_url(), headers=h, json=body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_unverifiable"
    assert len(_rows(client)) == 1


# --- brief 10: deletion and revision links --------------------------------------------------------


def test_deleting_a_revision_leaves_the_answer_it_revised(client):
    h = auth_headers(register(client))
    first = client.post(_url(), headers=h, json={"answer": TEXT}).json()
    rev = client.post(
        _url(), headers=h, json={"answer": TEXT + " Then I documented it.", "revises_answer_id": first["id"]}
    ).json()
    db = client.app.state.session_factory()
    db.delete(db.get(PracticeAnswer, rev["id"]))
    db.commit()
    db.close()
    assert [(a["id"], a["revises_answer_id"]) for a in client.get(_url(), headers=h).json()] == [
        (first["id"], None)
    ]


def test_deleting_an_account_removes_its_answers_and_links_and_nobody_elses(client):
    alice = auth_headers(register(client, email="alice@example.com"))
    bob = auth_headers(register(client, email="bob@example.com"))
    a1 = client.post(
        _url(), headers=alice, json={"answer": TEXT, "client_request_id": "op-shared-key-1"}
    ).json()
    client.post(_url(), headers=alice, json={"answer": TEXT, "revises_answer_id": a1["id"]})
    b1 = client.post(_url(), headers=bob, json={"answer": TEXT, "client_request_id": "op-shared-key-1"})
    assert b1.status_code == 201  # the same key string, another account: a different key
    r = client.request(
        "DELETE", "/api/v1/auth/me", headers=alice, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert r.status_code == 204
    left = _rows(client)
    assert [(x.id, x.client_request_id) for x in left] == [(b1.json()["id"], "op-shared-key-1")]
    # Bob's resend still replays his own answer.
    again = client.post(_url(), headers=bob, json={"answer": TEXT, "client_request_id": "op-shared-key-1"})
    assert again.status_code == 200 and again.json()["id"] == b1.json()["id"]


# --- brief 12: what a key promises -----------------------------------------------------------------


def test_a_key_is_kept_as_long_as_its_answer_and_a_new_key_is_a_new_answer(client):
    """No expiry: a resend any time later replays. A new key after an uncertain outcome is a new
    request; the client checks the saved answers first (QuestionPage), the server can't tell."""
    h = auth_headers(register(client))
    first = client.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": "op-kept-0001"})
    second = client.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": "op-kept-0002"})
    assert first.status_code == 201 and second.status_code == 201
    assert (
        client.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": "op-kept-0001"}).status_code
        == 200
    )
    assert len(_rows(client)) == 2
