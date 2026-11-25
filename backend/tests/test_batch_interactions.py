"""Where the Durable Saves pieces meet (brief 17): request keys, revision links and score
eligibility, in one learner's sequence. Each piece has its own tests; this checks they don't
disagree with each other. Synthetic data only."""

from __future__ import annotations

from app.careers.questions import questions_for
from app.models import PracticeAnswer
from tests.conftest import auth_headers, register

TRACK = "registered-nurse"
SHORT = "I would check the patient and call the doctor."
LONG = (
    "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his "
    "observations again, raised the bed, started oxygen as prescribed and called the doctor using SBAR. Within "
    "the hour his saturation was back to 96%, and I learned to escalate early rather than wait to be certain."
)


def _qid() -> str:
    return questions_for(TRACK)[0].id


def _url() -> str:
    return f"/api/v1/careers/{TRACK}/questions/{_qid()}/answers"


def _summary(c, h) -> dict:
    items = c.get(f"/api/v1/careers/{TRACK}/questions", headers=h, params={"page_size": 200}).json()["items"]
    return next(q for q in items if q["id"] == _qid())


def _progress(c, h) -> tuple[int, int, int]:
    p = c.get(f"/api/v1/careers/{TRACK}/progress", headers=h).json()
    return p["answered"], p["scored"], p["too_short"]


def test_a_keyed_too_short_answer_its_replay_and_a_keyed_revision_agree_everywhere(client):
    h = auth_headers(register(client))
    short = client.post(_url(), headers=h, json={"answer": SHORT, "client_request_id": "op-mix-short-1"})
    assert short.status_code == 201
    replay = client.post(_url(), headers=h, json={"answer": SHORT, "client_request_id": "op-mix-short-1"})
    assert replay.status_code == 200 and replay.headers.get("Idempotent-Replayed") == "true"
    assert replay.json()["id"] == short.json()["id"]
    # One answer, too short: answered, no score (the replay counted nothing twice).
    s = _summary(client, h)
    assert s["score_status"] == "too_short" and s["best_scored"] is None
    assert _progress(client, h) == (1, 0, 1)

    body = {"answer": LONG, "revises_answer_id": short.json()["id"], "client_request_id": "op-mix-rev-1"}
    rev = client.post(_url(), headers=h, json=body)
    assert rev.status_code == 201 and rev.json()["revises_answer_id"] == short.json()["id"]
    again = client.post(_url(), headers=h, json=body)
    assert again.status_code == 200 and again.json()["id"] == rev.json()["id"]
    # The revision is the scoreable best; the question counts once, now as scored.
    s = _summary(client, h)
    assert s["score_status"] == "scored" and s["best_scored"] == rev.json()["score"]
    assert _progress(client, h) == (1, 1, 0)
    listed = client.get(_url(), headers=h).json()
    assert [a["id"] for a in listed] == [rev.json()["id"], short.json()["id"]]  # two tries, no duplicate
    feed = client.get("/api/v1/me/activity", headers=h, params={"type": "written_answer"}).json()
    assert feed["total"] == 2


def test_deleting_the_revised_answer_keeps_the_revision_and_its_score(client):
    h = auth_headers(register(client))
    short = client.post(_url(), headers=h, json={"answer": SHORT}).json()
    rev = client.post(_url(), headers=h, json={"answer": LONG, "revises_answer_id": short["id"]}).json()
    db = client.app.state.session_factory()
    db.delete(db.get(PracticeAnswer, short["id"]))
    db.commit()
    db.close()
    listed = client.get(_url(), headers=h).json()
    assert [(a["id"], a["revises_answer_id"]) for a in listed] == [(rev["id"], None)]
    s = _summary(client, h)
    assert s["score_status"] == "scored" and s["best_scored"] == rev["score"]
    # A new revision of the deleted answer is refused, keyed or not, and nothing is saved.
    r = client.post(
        _url(),
        headers=h,
        json={"answer": LONG, "revises_answer_id": short["id"], "client_request_id": "op-gone-1"},
    )
    assert r.status_code == 404 and len(client.get(_url(), headers=h).json()) == 1
