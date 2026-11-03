"""Rubric transparency and self-review: criteria before answering (no hidden patterns), quoted
evidence, an insufficient-evidence state instead of a precise score, optional self-review that
never changes the result, private flags, re-evaluation only when it could differ (with the
original kept), and privacy."""

import json

from sqlalchemy import select

from app.careers import grading
from app.careers.questions import questions_for
from app.models import AnswerEvaluation, AnswerFlag, AnswerSelfReview, PracticeAnswer
from tests.conftest import auth_headers, register

TRACK = "registered-nurse"
Q = next(q for q in questions_for(TRACK) if q.kind == "behavioral")
ANSWER = (
    "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. patient assessment. "
    "I was responsible for five patients, so I had to move fast. I checked his vital signs again and started "
    "oxygen per protocol. I called the rapid response team and asked the charge nurse to cover my other "
    "patients. I updated the doctor and documented everything. As a result, he was stable within 30 minutes, "
    "and I learned to escalate early instead of waiting to be sure."
)


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=TRACK))


def answer(client, h, text=ANSWER):
    r = client.post(f"/api/v1/careers/{TRACK}/questions/{Q.id}/answers", headers=h, json={"answer": text})
    assert r.status_code == 201, r.text
    return r.json()


def test_criteria_are_shown_before_answering_without_hidden_patterns(client):
    r = client.get(f"/api/v1/careers/{TRACK}/questions/{Q.id}/criteria")
    assert r.status_code == 200
    c = r.json()
    assert [x["label"] for x in c["criteria"]] == [p.label for p in Q.rubric]
    assert all(x["levels"][0]["text"].startswith("Not yet:") for x in c["criteria"])
    assert (
        all(ch["kind"] == "deterministic" for ch in c["checks"])
        and "not an employer's rubric" in c["disclaimer"]
    )
    text = json.dumps(c)
    assert (
        "patterns" not in text and "\\b" not in text and "min_hits" not in text
    )  # the matching rules stay private
    assert client.get(f"/api/v1/careers/{TRACK}/questions/nope/criteria").status_code == 404


def test_feedback_quotes_the_answer_and_short_answers_are_insufficient(client):
    h = nurse(client)
    a = answer(client, h)
    assert a["evidence_level"] == "sufficient" and a["rubric_version"] == grading.RUBRIC_VERSION
    covered = [p for p in a["points"] if p["covered"]]
    assert covered and all(p["evidence"] and p["evidence"] in ANSWER for p in covered)
    assert all(p["evidence"] is None for p in a["points"] if not p["covered"])
    short = answer(client, h, "I called the rapid response team and stayed with him.")
    assert short["evidence_level"] == "insufficient"


def test_self_review_is_optional_and_never_changes_the_result(client):
    h = nurse(client)
    a = answer(client, h)
    url = f"/api/v1/me/answers/{a['id']}"
    first = client.get(f"{url}/review", headers=h).json()
    assert first["self_review"] is None and all(p["yours"] is None for p in first["perspectives"])
    label = a["points"][0]["label"]
    r = client.put(
        f"{url}/self-review",
        headers=h,
        json={"went_well": "Clear actions", "improve": "Say the result sooner", "ratings": {label: "partly"}},
    )
    assert r.status_code == 200
    review = r.json()
    assert review["self_review"]["before_feedback"] is True
    assert review["perspectives"][0] == {
        "criterion": label,
        "yours": "partly",
        "coach": a["points"][0]["covered"],
    }
    assert review["answer"]["score"] == a["score"] and review["answer"]["points"] == a["points"]
    assert (
        client.put(f"{url}/self-review", headers=h, json={"ratings": {"Made up": "yes"}}).status_code == 400
    )
    # Edited after reading the feedback: no longer "before".
    after = client.put(
        f"{url}/self-review", headers=h, json={"went_well": "x", "before_feedback": False}
    ).json()
    assert after["self_review"]["before_feedback"] is False
    skipped = client.put(
        f"{url}/self-review", headers=h, json={"skipped": True, "went_well": "ignored"}
    ).json()
    assert skipped["self_review"]["skipped"] is True and skipped["self_review"]["went_well"] == ""
    with client.app.state.session_factory() as db:
        row = db.get(PracticeAnswer, a["id"])
        assert row.score == a["score"] and row.answer == ANSWER


def test_flags_are_private_notes_on_a_real_criterion(client):
    h = nurse(client)
    a = answer(client, h)
    url = f"/api/v1/me/answers/{a['id']}/flags"
    label = a["points"][1]["label"]
    r = client.post(
        url, headers=h, json={"criterion": label, "kind": "disagree", "note": "I did give a result."}
    )
    assert r.status_code == 200 and r.json()["flags"][0]["kind"] == "disagree"
    again = client.post(url, headers=h, json={"criterion": label, "kind": "unclear", "note": ""}).json()
    assert len(again["flags"]) == 1 and again["flags"][0]["kind"] == "unclear"  # one flag per criterion
    assert (
        client.post(url, headers=h, json={"criterion": "Something else", "kind": "unclear"}).status_code
        == 400
    )
    assert client.post(url, headers=h, json={"criterion": "Overall", "kind": "unclear"}).status_code == 200
    fid = again["flags"][0]["id"]
    assert len(client.delete(f"{url}/{fid}", headers=h).json()["flags"]) == 1


def test_reevaluation_only_when_it_could_differ_and_the_original_is_kept(client, monkeypatch):
    h = nurse(client)
    a = answer(client, h)
    url = f"/api/v1/me/answers/{a['id']}"
    review = client.get(f"{url}/review", headers=h).json()
    assert review["can_reevaluate"] is False and "same result" in review["reevaluate_note"]
    same = client.post(f"{url}/evaluations", headers=h, json={"reason": "please"})
    assert same.status_code == 409 and same.json()["error"]["code"] == "no_reevaluation"
    monkeypatch.setattr(grading, "RUBRIC_VERSION", "v2")  # as if the rules changed since
    r = client.post(f"{url}/evaluations", headers=h, json={"reason": "The rubric changed."})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (
        out["evaluations"][0]["rubric_version"] == "v2"
        and out["evaluations"][0]["reason"] == "The rubric changed."
    )
    assert (
        out["answer"]["rubric_version"] == "v1" and out["answer"]["score"] == a["score"]
    )  # the original stays
    assert (
        client.post(f"{url}/evaluations", headers=h, json={}).status_code == 409
    )  # nothing changed since the last one


def test_repeated_areas_are_neutral_counts(client):
    h = nurse(client)
    vague = "I always try my best with patients and I think communication matters a lot in nursing. " * 3
    for _ in range(2):
        last = answer(client, h, vague)
    rep = client.get(f"/api/v1/me/answers/{last['id']}/review", headers=h).json()["repeated"]
    assert rep and all(r["times"] >= 2 and r["of"] == 2 for r in rep)


def test_owner_only_export_and_deletion(client):
    a_h = nurse(client)
    b_h = nurse(client, email="bea@example.com")
    a = answer(client, a_h)
    url = f"/api/v1/me/answers/{a['id']}"
    client.put(f"{url}/self-review", headers=a_h, json={"went_well": "Calm", "ratings": {}})
    client.post(f"{url}/flags", headers=a_h, json={"criterion": "Overall", "kind": "unclear", "note": "n"})
    for call in (
        lambda: client.get(f"{url}/review", headers=b_h),
        lambda: client.put(f"{url}/self-review", headers=b_h, json={}),
        lambda: client.post(f"{url}/flags", headers=b_h, json={"criterion": "Overall", "kind": "unclear"}),
        lambda: client.post(f"{url}/evaluations", headers=b_h, json={}),
    ):
        assert call().status_code == 404
    assert client.get(f"{url}/review").status_code == 401
    exported = client.get("/api/v1/me/export", headers=a_h).json()["answer_reviews"]
    assert exported["self_reviews"][0]["went_well"] == "Calm" and exported["flags"][0]["note"] == "n"
    client.request(
        "DELETE", "/api/v1/auth/me", headers=a_h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert db.scalars(select(AnswerSelfReview)).all() == [] and db.scalars(select(AnswerFlag)).all() == []
        assert db.scalars(select(AnswerEvaluation)).all() == []
