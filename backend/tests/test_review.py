"""Interview review, single-question retries with comparison, and the spaced review queue."""

from datetime import UTC, datetime, timedelta

from app.models import PracticeAnswer, ReviewItem
from tests.conftest import auth_headers, register

STRONG = (
    "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. patient assessment. "
    "I was responsible for five patients, so I moved fast. I checked his vital signs again and started oxygen "
    "per protocol. I called the rapid response team and asked the charge nurse to cover my other patients. I "
    "updated the doctor and documented everything. As a result, he was stable within 30 minutes, and I learned to "
    "escalate early."
)
WEAK = "We handled it together as a team and it was fine in the end, we all did well."


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def round_with(client, h, answers):
    """Start a round; answers[i] is text, None (skip) or ... (stop before it)."""
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
    for i, a in enumerate(answers):
        if a is ...:
            client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h)
            break
        if a is None:
            client.post(f"/api/v1/interviews/{iv['id']}/skip", headers=h, json={"question_index": i})
        else:
            client.post(
                f"/api/v1/interviews/{iv['id']}/answers",
                headers=h,
                json={"question_index": i, "answer": a, "source": "voice" if i == 0 else "typed"},
            )
    return iv["id"]


def review(client, h, iv):
    r = client.get(f"/api/v1/interviews/{iv}/review", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_completed_round_review_with_dimensions_and_grounded_improvements(client):
    h = nurse(client)
    iv = round_with(client, h, [STRONG, WEAK, WEAK, None, STRONG])
    r = review(client, h, iv)
    assert r["completed"] and r["status_label"] == "Completed" and r["kind"] == "questions"
    assert r["career_title"] == "Registered Nurse" and r["elapsed_seconds"] is not None
    assert [i["status"] for i in r["items"]] == ["answered", "answered", "answered", "skipped", "answered"]
    first = r["items"][0]
    assert first["asked_at"] and first["answered_at"] and first["source"] == "voice"
    assert "speech recognition" in first["transcription_note"]
    names = {d["name"]: d for d in first["dimensions"]}
    assert names["Answer content"]["status"] == "evaluated"
    assert names["Structure and clarity"]["status"] == "evaluated"
    assert (
        names["Reasoning"]["status"] == "not_evaluated"
        and "qualified source" in names["Reasoning"]["summary"]
    )
    assert (
        names["Spoken delivery"]["status"] == "not_evaluated"
        and "accent" in names["Spoken delivery"]["summary"].lower()
    )
    assert any("skipped" in n for n in r["notices"]) and any("transcribed" in n for n in r["notices"])
    assert 1 <= len(r["improvements"]) <= 3
    top = r["improvements"][0]
    assert (
        top["evidence"] and top["evidence"][0]["item_key"].startswith("q") and top["evidence"][0]["excerpt"]
    )
    assert top["practice"]["retry_index"] is not None
    assert (
        "not whether it's correct" in r["disclaimer"]
        and "isn't professional or clinical guidance" in r["disclaimer"]
    )


def test_an_abandoned_round_never_reads_as_completed(client):
    h = nurse(client)
    iv = round_with(client, h, [STRONG, ...])
    r = review(client, h, iv)
    assert r["completed"] is False and r["status_label"] == "Ended early"
    assert r["notices"][0].startswith("Ended early: 1 of 5 questions answered")
    assert [i["status"] for i in r["items"]].count("not_reached") == 4
    assert any(i["title"] == "Answer the questions you didn't get to" for i in r["improvements"])


def test_a_round_with_no_answers_has_no_evaluation(client):
    h = nurse(client)
    iv = round_with(client, h, [...])
    r = review(client, h, iv)
    assert r["evaluation_available"] is False and r["overall"][0]["status"] == "not_evaluated"


def test_a_running_interview_has_no_review_yet(client):
    h = nurse(client)
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
    r = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "interview_in_progress"


def test_retry_keeps_the_original_and_compares_on_the_same_rubric(client):
    h = nurse(client)
    iv = round_with(client, h, [WEAK, None, None, None, None])
    original = review(client, h, iv)["items"][0]["feedback"]
    c = client.post(f"/api/v1/interviews/{iv}/questions/0/retries", headers=h, json={"answer": STRONG}).json()
    assert c["original"]["answer"] == WEAK and c["original"]["score"] == original["score"]  # untouched
    assert c["latest"]["answer"] == STRONG and len(c["retries"]) == 1
    # The interview answer was too short to score: what was written compares, the numbers don't
    # (docs/COMPARING_ATTEMPTS.md), and the timed interview is named as a different condition.
    assert c["classification"]["outcome"] == "partially_comparable"
    assert not c["comparable"] and c["score_change"] is None
    assert (
        "too short to score" in c["comparability_note"] and "timed mock interview" in c["comparability_note"]
    )
    assert c["improved"] and not set(c["improved"]) & set(c["still_missing"])
    again = review(client, h, iv)
    assert again["items"][0]["retries"] == 1 and again["items"][0]["feedback"]["answer"] == WEAK
    # A skipped question can be answered later too; there's nothing to compare it with.
    skipped = client.post(
        f"/api/v1/interviews/{iv}/questions/1/retries", headers=h, json={"answer": STRONG}
    ).json()
    assert skipped["original"] is None and "no original" in skipped["comparability_note"]


def test_a_scoreable_original_and_retry_compare_with_the_conditions_named(client):
    h = nurse(client)
    first = STRONG.rsplit(" As a result", 1)[0] + " I stayed with him until the team arrived and handed over."
    iv = round_with(client, h, [first, None, None, None, None])
    c = client.post(f"/api/v1/interviews/{iv}/questions/0/retries", headers=h, json={"answer": STRONG}).json()
    assert c["original"]["evidence_level"] == "sufficient" == c["latest"]["evidence_level"]
    cl = c["classification"]
    assert cl["outcome"] == "partially_comparable" and cl["scores_comparable"] and cl["contract_version"] == 1
    assert [r["rule"] for r in cl["reasons"]] == ["format"]
    assert c["comparable"] and c["score_change"] == c["latest"]["score"] - c["original"]["score"]
    assert "answered in a timed mock interview, the later one as a retry" in c["comparability_note"]


def test_a_changed_evaluator_is_disclosed_not_compared(client):
    h = nurse(client)
    iv = round_with(client, h, [WEAK, None, None, None, None])
    with client.app.state.session_factory() as db:
        a = db.query(PracticeAnswer).one()
        a.feedback = {**a.feedback, "rubric_version": "v0", "evaluator": "built-in (offline) · rubric v0"}
        db.commit()
    c = client.post(f"/api/v1/interviews/{iv}/questions/0/retries", headers=h, json={"answer": STRONG}).json()
    assert c["comparable"] is False and c["score_change"] is None
    assert "scored under different rubrics (v0 and " in c["comparability_note"]


def test_retries_are_only_for_finished_rounds(client):
    h = nurse(client)
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
    r = client.post(f"/api/v1/interviews/{iv['id']}/questions/0/retries", headers=h, json={"answer": STRONG})
    assert r.status_code == 409
    client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h)
    assert (
        client.post(
            f"/api/v1/interviews/{iv['id']}/questions/9/retries", headers=h, json={"answer": STRONG}
        ).status_code
        == 404
    )


def test_coding_review_links_feedback_to_turns_and_never_claims_correctness(client):
    h = auth_headers(register(client))
    iv = client.post("/api/v1/interviews", headers=h, json={"problem_slug": "two-sum"}).json()
    client.post(
        f"/api/v1/interviews/{iv['id']}/messages", headers=h, json={"message": "Can the array be empty?"}
    )
    client.post(
        f"/api/v1/interviews/{iv['id']}/finish", headers=h, json={"code": "class Solution {\n  int x;\n}"}
    )
    r = review(client, h, iv["id"])
    assert r["kind"] == "coding" and r["problem"]["slug"] == "two-sum" and r["evaluation_available"]
    assert r["items"][0]["role"] == "interviewer" and r["items"][1]["role"] == "candidate"
    assert all(i["asked_at"] for i in r["items"])  # real recorded times
    execution = next(d for d in r["overall"] if d["name"] == "Code execution")
    assert execution["status"] == "not_evaluated" and "no pass/fail" in execution["summary"]
    comm = next(d for d in r["overall"] if d["name"].endswith("Communication"))
    assert comm["evidence"][0]["item_key"] == "turn-1"
    assert any(e["label"] == "You didn't answer in this phase" for d in r["overall"] for e in d["evidence"])
    assert "Confidence describes the evaluator, not your answer" in r["disclaimer"]
    # Every message was typed: spoken delivery doesn't apply (it isn't "not measured").
    delivery = next(d for d in r["overall"] if d["name"] == "Spoken delivery")
    assert (delivery["status"], delivery["summary"]) == ("not_applicable", "Every message was typed.")
    assert (
        client.post(
            f"/api/v1/interviews/{iv['id']}/questions/0/retries", headers=h, json={"answer": "x"}
        ).status_code
        == 409
    )


def test_a_coding_review_with_a_spoken_message_says_delivery_isnt_measured(client):
    h = auth_headers(register(client))
    iv = client.post("/api/v1/interviews", headers=h, json={"problem_slug": "two-sum"}).json()
    client.post(
        f"/api/v1/interviews/{iv['id']}/messages",
        headers=h,
        json={"message": "Can the array be empty?", "source": "voice"},
    )
    client.post(f"/api/v1/interviews/{iv['id']}/finish", headers=h, json={"code": "class Solution {}"})
    delivery = next(d for d in review(client, h, iv["id"])["overall"] if d["name"] == "Spoken delivery")
    assert delivery["status"] == "not_evaluated" and "transcript only" in delivery["summary"]


def test_review_queue_schedule_snooze_and_remove(client):
    h = nurse(client)
    q = client.post(
        "/api/v1/me/reviews", headers=h, json={"track": "registered-nurse", "question_id": "e-good-0"}
    ).json()
    assert q["due"] == [] and len(q["upcoming"]) == 1 and q["ladder_days"] == [1, 3, 7, 14, 30]
    item = q["upcoming"][0]
    assert item["interval_days"] == 1 and "first review comes 1 day later" in item["why"]
    assert (
        client.post(
            "/api/v1/me/reviews", headers=h, json={"track": "registered-nurse", "question_id": "e-good-0"}
        ).json()["upcoming"][0]["id"]
        == item["id"]
    )
    with client.app.state.session_factory() as db:
        row = db.get(ReviewItem, item["id"])
        row.due_at = datetime.now(UTC) - timedelta(minutes=1)
        row.scheduled_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    due = client.get("/api/v1/me/reviews", headers=h).json()["due"][0]
    assert due["due"] and due["why"].startswith("Due now.")
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-good-0/answers", headers=h, json={"answer": WEAK}
    )
    after = client.get("/api/v1/me/reviews", headers=h).json()
    weak = after["upcoming"][0]
    assert weak["reviews"] == 1 and weak["interval_days"] == 1 and "(below 70)" in weak["why"]
    snoozed = client.post(f"/api/v1/me/reviews/{item['id']}/snooze", headers=h, json={"days": 3}).json()[
        "upcoming"
    ][0]
    assert snoozed["snoozed"] and "Snoozed until" in snoozed["why"]
    assert (
        client.post(f"/api/v1/me/reviews/{item['id']}/snooze", headers=h, json={"days": 2}).status_code == 422
    )
    assert client.delete(f"/api/v1/me/reviews/{item['id']}", headers=h).json()["upcoming"] == []


def test_a_strong_answer_spaces_the_review_out(client):
    h = nurse(client)
    item = client.post(
        "/api/v1/me/reviews", headers=h, json={"track": "registered-nurse", "question_id": "e-time-0"}
    ).json()["upcoming"][0]
    with client.app.state.session_factory() as db:
        row = db.get(ReviewItem, item["id"])
        row.scheduled_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-time-0/answers", headers=h, json={"answer": STRONG}
    )
    q = client.get("/api/v1/me/reviews", headers=h).json()["upcoming"][0]
    assert q["last_score"] >= 85 and q["interval_days"] == 3 and "the gap grew to 3 days" in q["why"]


def test_one_account_cannot_see_or_change_anothers_review_or_retries(client):
    owner = nurse(client)
    iv = round_with(client, owner, [STRONG, None, None, None, None])
    item = client.post(
        "/api/v1/me/reviews",
        headers=owner,
        json={"track": "registered-nurse", "question_id": "e-good-0", "session_id": iv},
    ).json()["upcoming"][0]
    other = nurse(client, email="other@example.com")
    assert client.get(f"/api/v1/interviews/{iv}/review", headers=other).status_code == 404
    assert (
        client.post(
            f"/api/v1/interviews/{iv}/questions/0/retries", headers=other, json={"answer": STRONG}
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/interviews/{iv}/questions/0/comparison", headers=other).status_code == 404
    assert client.get("/api/v1/me/reviews", headers=other).json()["upcoming"] == []
    assert (
        client.post(f"/api/v1/me/reviews/{item['id']}/snooze", headers=other, json={"days": 1}).status_code
        == 404
    )
    assert client.delete(f"/api/v1/me/reviews/{item['id']}", headers=other).status_code == 404
    assert (
        client.post(
            "/api/v1/me/reviews",
            headers=other,
            json={"track": "registered-nurse", "question_id": "e-good-0", "session_id": iv},
        ).status_code
        == 404
    )
    client.post(f"/api/v1/interviews/{iv}/questions/0/retries", headers=owner, json={"answer": STRONG})
    export = client.get("/api/v1/me/export", headers=owner).json()
    assert (
        export["interview_retries"][0]["question_index"] == 0
        and export["review_queue"][0]["question"] == "e-good-0"
    )
