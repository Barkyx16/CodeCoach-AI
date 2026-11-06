"""Question rounds: mock interviews made of one career's questions, stored like coding interviews."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import PracticeAnswer, PracticeSession
from tests.conftest import auth_headers, register

NURSE_ANSWER = (
    "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. assessment. I was "
    "responsible for five patients, so I had to move fast. I checked his vital signs again and started oxygen "
    "per protocol. I called the rapid response team and asked the charge nurse to cover my other patients. I "
    "updated the doctor and documented everything. As a result, he was stable within 30 minutes. I learned to "
    "escalate early."
)


def nurse(client, email="nurse@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def start(client, headers, **body):
    return client.post("/api/v1/interviews", headers=headers, json={"kind": "questions", **body})


def answer(client, headers, iv, index, text=NURSE_ANSWER, source="typed"):
    return client.post(
        f"/api/v1/interviews/{iv}/answers",
        headers=headers,
        json={"question_index": index, "answer": text, "source": source},
    )


def test_a_round_uses_the_users_own_career_in_interview_order(client):
    h = nurse(client)
    r = start(client, h, duration_minutes=15)
    assert r.status_code == 201, r.text
    iv = r.json()
    assert iv["kind"] == "questions" and iv["track"] == "registered-nurse"
    assert iv["career_title"] == "Registered Nurse" and iv["problem"] is None
    kinds = [q["kind"] for q in iv["questions"]]
    # Easy questions are motivation, knowledge and behavioral; a round covers each, in interview order.
    order = ["motivation", "knowledge", "situational", "behavioral", "leadership"]
    assert len(kinds) == 5 and kinds == sorted(kinds, key=order.index)
    assert set(kinds) == {"motivation", "knowledge", "behavioral"} and kinds.count("motivation") == 1
    assert all(q["difficulty"] == "easy" for q in iv["questions"])
    assert [q["status"] for q in iv["questions"]] == ["current", "pending", "pending", "pending", "pending"]
    # The interviewer has asked the first question; nothing about Java or code.
    assert iv["turns"][0]["role"] == "interviewer" and iv["turns"][0]["question_index"] == 0
    assert iv["turns"][0]["content"] == iv["questions"][0]["prompt"]
    assert "java" not in str(iv["questions"]).lower()
    assert iv["seconds_remaining"] > 14 * 60


def test_answers_are_graded_saved_and_carry_engagement_and_source(client):
    h = nurse(client)
    iv = start(client, h).json()
    r = answer(client, h, iv["id"], 0, source="voice")
    assert r.status_code == 200, r.text
    body = r.json()
    q0 = body["questions"][0]
    assert q0["status"] == "answered" and q0["answer"]["score"] > 0
    assert body["questions"][1]["status"] == "current"
    reply = next(t for t in body["turns"] if t["role"] == "candidate")
    assert reply["source"] == "voice" and reply["engagement"]["state"] in {
        "following",
        "more_detail",
        "explore_further",
        "not_enough_evidence",
    }
    assert reply["engagement"]["reason"].startswith(reply["engagement"]["label"])
    # The answer is an ordinary practice answer too (progress, history, export).
    progress = client.get("/api/v1/careers/registered-nurse/progress", headers=h).json()
    assert progress["answered"] == 1


def test_repeated_submissions_never_grade_twice(client):
    h = nurse(client)
    iv = start(client, h).json()
    first = answer(client, h, iv["id"], 0)
    again = answer(
        client, h, iv["id"], 0, text="A completely different second attempt that should be ignored."
    )
    assert first.status_code == again.status_code == 200
    assert (
        again.json()["questions"][0]["answer"]["answer"] == first.json()["questions"][0]["answer"]["answer"]
    )
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PracticeAnswer)) == 1
    assert sum(t["role"] == "candidate" for t in again.json()["turns"]) == 1


def test_questions_must_be_answered_in_order(client):
    h = nurse(client)
    iv = start(client, h).json()
    r = answer(client, h, iv["id"], 2)
    assert r.status_code == 409 and r.json()["error"]["code"] == "question_not_current"
    assert r.json()["error"]["details"]["current_question_index"] == 0


def test_skips_are_recorded_as_skipped_not_answered_and_the_round_completes(client):
    h = nurse(client)
    iv = start(client, h).json()
    answer(client, h, iv["id"], 0)
    for i in range(1, 5):
        r = client.post(f"/api/v1/interviews/{iv['id']}/skip", headers=h, json={"question_index": i})
        assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "completed" and done["ended_at"]
    assert [q["status"] for q in done["questions"]] == ["answered"] + ["skipped"] * 4
    s = done["round_summary"]
    assert s["answered"] == 1 and s["skipped"] == 4 and s["unanswered"] == 0
    assert s["average_score"] == done["questions"][0]["answer"]["score"]
    skipped = [t for t in done["turns"] if t["skipped"]]
    assert len(skipped) == 4 and all(t["engagement"] is None for t in skipped)


def test_ending_early_is_abandoned_not_completed(client):
    h = nurse(client)
    iv = start(client, h).json()
    answer(client, h, iv["id"], 0)
    assert (
        client.post(f"/api/v1/interviews/{iv['id']}/finish", headers=h).json()["error"]["code"]
        == "questions_remaining"
    )
    r = client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h).json()
    assert r["status"] == "abandoned"
    assert r["round_summary"]["unanswered"] == 4
    assert answer(client, h, iv["id"], 1).json()["error"]["code"] == "interview_closed"


def test_deadline_expires_the_round_on_the_server(client):
    h = nurse(client)
    iv = start(client, h).json()
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv["id"])
        s.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    r = client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()
    assert r["status"] == "expired" and r["seconds_remaining"] == 0
    assert r["questions"][0]["status"] == "pending"
    assert answer(client, h, iv["id"], 0).status_code == 409


def test_one_interview_at_a_time_across_both_kinds(client):
    h = nurse(client)
    iv = start(client, h).json()
    r = client.post("/api/v1/interviews", headers=h, json={"problem_slug": "two-sum"})
    assert r.status_code == 409 and r.json()["error"]["details"]["interview_id"] == iv["id"]


def test_rounds_appear_in_interview_history_and_the_data_export(client):
    h = nurse(client)
    iv = start(client, h).json()
    answer(client, h, iv["id"], 0, source="voice")
    items = client.get("/api/v1/interviews", headers=h).json()["items"]
    assert items[0]["id"] == iv["id"] and items[0]["kind"] == "questions"
    assert items[0]["career_title"] == "Registered Nurse" and items[0]["problem"] is None
    export = client.get("/api/v1/me/export", headers=h).json()
    exported = next(i for i in export["interviews"] if i["id"] == iv["id"])
    assert exported["kind"] == "questions" and exported["track"] == "registered-nurse"
    assert exported["transcript"][1]["meta"]["source"] == "voice"


def test_another_user_cannot_see_or_answer_a_round(client):
    owner = nurse(client)
    iv = start(client, owner).json()
    other = nurse(client, email="other@example.com")
    assert client.get(f"/api/v1/interviews/{iv['id']}", headers=other).status_code == 404
    assert answer(client, other, iv["id"], 0).status_code == 404
    assert (
        client.post(
            f"/api/v1/interviews/{iv['id']}/skip", headers=other, json={"question_index": 0}
        ).status_code
        == 404
    )


def test_answer_endpoints_do_not_apply_to_coding_interviews(client):
    h = auth_headers(register(client))
    iv = client.post("/api/v1/interviews", headers=h, json={"problem_slug": "two-sum"}).json()
    assert iv["kind"] == "coding" and iv["questions"] == [] and iv["round_summary"] is None
    r = answer(client, h, iv["id"], 0)
    assert r.status_code == 409 and r.json()["error"]["code"] == "wrong_interview_kind"


def test_coding_messages_get_engagement_from_their_content(client):
    h = auth_headers(register(client))
    iv = client.post("/api/v1/interviews", headers=h, json={"problem_slug": "two-sum"}).json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/messages",
        headers=h,
        json={"message": "Can the array contain duplicates or be empty?", "source": "voice"},
    ).json()
    turn = next(t for t in r["turns"] if t["role"] == "candidate")
    assert turn["source"] == "voice"
    assert turn["engagement"]["state"] == "following"
    assert "duplicates" in turn["engagement"]["reason"] or "?" in turn["engagement"]["reason"]


def test_unknown_career_and_other_difficulties(client):
    h = nurse(client)
    assert start(client, h, track="astronaut").status_code == 404
    iv = start(client, h, track="barista", difficulty="hard").json()
    assert iv["track"] == "barista" and {q["difficulty"] for q in iv["questions"]} == {"hard"}
    assert {q["kind"] for q in iv["questions"]} == {"situational", "behavioral", "leadership"}


def test_rounds_prefer_questions_not_answered_yet():
    import random

    from app.careers.questions import questions_for
    from app.services.question_rounds import pick_round

    pool = [q for q in questions_for("registered-nurse") if q.difficulty == "easy"]
    motivation = [q for q in pool if q.kind == "motivation"]
    answered = {q.id for q in motivation[:-1]}  # every motivation question but one
    for seed in range(10):
        picked = pick_round(pool, answered, random.Random(seed))
        assert picked[0].kind == "motivation" and picked[0].id not in answered
