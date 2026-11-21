"""Career boundaries for written-answer feedback (Volume 4 prompt 10): which careers' feedback has
been measured, honest notes for the rest, no grading with another career's rules, and a career
change that keeps earlier answers exactly as they were."""

import pytest

from app.careers import CATALOG
from app.careers.questions import get_question, questions_for
from app.careers.support import MEASURED, evaluation_for, scope_note
from tests.conftest import auth_headers, register

NURSE, CSR, UNMEASURED, CODING = (
    "registered-nurse",
    "customer-service-representative",
    "electrician",
    "software-engineer",
)

CSR_ANSWER = (
    "Last spring on the phone support team, a customer called about being charged twice for one order and was "
    "very angry. I was the representative on the call, so it was mine to resolve. I listened without interrupting, "
    "apologised, checked the billing history and saw the duplicate charge. I raised a refund with the billing team "
    "while the customer was still on the line and sent a written confirmation by email. The refund arrived within "
    "two days and the customer rated the call five out of five. I learned to confirm the fix in writing."
)


def post(client, h, track, qid, text):
    r = client.post(f"/api/v1/careers/{track}/questions/{qid}/answers", headers=h, json={"answer": text})
    assert r.status_code == 201, r.text
    return r.json()


def behavioral(track):
    return next(q for q in questions_for(track) if q.kind == "behavioral" and q.difficulty == "easy")


def test_the_catalog_says_which_careers_feedback_has_been_measured(client):
    by_slug = {c["slug"]: c["answer_feedback"] for c in client.get("/api/v1/careers").json()}
    assert by_slug[NURSE] == by_slug[CSR] == "measured"
    assert by_slug[UNMEASURED] == by_slug[CODING] == "not_measured"
    assert {s for s, v in by_slug.items() if v == "measured"} == set(MEASURED)
    assert all(s in CATALOG for s in MEASURED)


def test_a_new_careers_answer_is_graded_by_its_own_questions_rubric(client):
    h = auth_headers(register(client, email="csr@example.com", career_track=CSR))
    q = behavioral(CSR)
    out = post(client, h, CSR, q.id, CSR_ANSWER)
    assert [p["label"] for p in out["points"]] == [r.label for r in get_question(CSR, q.id).rubric]
    assert out["track"] == CSR and out["evaluation_status"] == "measured"
    assert all(p["evidence_status"] == "verified" for p in out["points"] if p["evidence"])
    nurse_only = {r.label for qq in questions_for(NURSE) for r in qq.rubric} - {
        r.label for qq in questions_for(CSR) for r in qq.rubric
    }
    assert not nurse_only & {p["label"] for p in out["points"]}  # no nursing criterion leaks in


def test_an_unmeasured_career_still_gets_feedback_with_an_honest_note(client):
    h = auth_headers(register(client, email="sparks@example.com", career_track=UNMEASURED))
    q = behavioral(UNMEASURED)
    out = post(client, h, UNMEASURED, q.id, CSR_ANSWER.replace("phone support team", "site"))
    assert out["evaluation_status"] == "not_measured"
    assert CATALOG[UNMEASURED].title in out["evaluation_note"] and "structure" in out["evaluation_note"]
    assert out["score"] > 0  # not penalised for the career lacking evaluation content


def test_a_point_that_sounds_like_a_correctness_judgement_says_what_it_checks():
    metric_q = next(q for q in questions_for(CSR) if any(r.label.endswith(" correctly") for r in q.rubric))
    labels = [r.label for r in metric_q.rubric]
    notes = {label: scope_note(label) for label in labels}
    assert any(n for n in notes.values()) and all(
        (n is not None) == (label.startswith("Explains ") and label.endswith(" correctly"))
        for label, n in notes.items()
    )


def test_changing_career_keeps_earlier_answers_as_they_were_and_progress_apart(client):
    tokens = register(client, email="switch@example.com", career_track=NURSE)
    h = auth_headers(tokens)
    nq = behavioral(NURSE)
    nurse_answer = post(
        client,
        h,
        NURSE,
        nq.id,
        "Last winter on a night shift I was responsible for five patients. I checked a patient's observations, "
        "called the rapid response team and documented everything. He was stable within 30 minutes. I learned to "
        "escalate early.",
    )
    me = client.patch("/api/v1/auth/me", headers=h, json={"career_track": CSR})
    assert me.status_code == 200 and me.json()["career_track"] == CSR
    post(client, h, CSR, behavioral(CSR).id, CSR_ANSWER)
    # The nursing answer: still listed under its own question, with the grade and rubric it got.
    listed = client.get(f"/api/v1/careers/{NURSE}/questions/{nq.id}/answers", headers=h).json()
    again = next(a for a in listed if a["id"] == nurse_answer["id"])
    for key in ("score", "rating", "rubric_version", "points", "track"):
        assert again[key] == nurse_answer[key], key
    # Progress per career, never mixed.
    nurse_progress = client.get(f"/api/v1/careers/{NURSE}/progress", headers=h).json()
    csr_progress = client.get(f"/api/v1/careers/{CSR}/progress", headers=h).json()
    assert nurse_progress["answered"] == 1 and csr_progress["answered"] == 1
    assert client.get(f"/api/v1/careers/{UNMEASURED}/progress", headers=h).json()["answered"] == 0


@pytest.mark.parametrize("track", [NURSE, CSR, UNMEASURED])
def test_an_answer_to_another_careers_question_is_graded_by_that_question(client, track):
    """A nurse may practise any career's questions; each answer is graded by the question it
    answers (its URL), never by the learner's own career."""
    h = auth_headers(register(client, email=f"any-{track}@example.com", career_track=NURSE))
    q = behavioral(track)
    out = post(client, h, track, q.id, CSR_ANSWER)
    assert out["track"] == track and [p["label"] for p in out["points"]] == [r.label for r in q.rubric]
    assert out["evaluation_status"] == evaluation_for(track).status


def test_the_coding_career_keeps_its_judge_and_its_written_answers_are_not_measured(client):
    assert CATALOG[CODING].has_coding and evaluation_for(CODING).status == "not_measured"
    problems = client.get("/api/v1/problems", params={"page_size": 1})
    assert problems.status_code == 200  # the coding problems (and their judge) are a separate path
