"""Conditions for interview-round answers (Volume 13, prompt 3; docs/ATTEMPT_CONDITIONS.md): what
in-app help was in play is recorded when a round's answer is saved, with the round's format (timed,
the interviewer's follow-up asked or skipped, ended early), and shown on the results, the question
page and the retry comparison; the comparison names the condition that differed. Synthetic data."""

from sqlalchemy import delete, select

from app.models import InterviewTurn, PracticeAnswer, TurnRole
from tests.conftest import auth_headers, register
from tests.test_attempt_conditions import read_lesson
from tests.test_formats import FULL, VAGUE, followup, start
from tests.test_roadmap import STRONG

TRACK = "registered-nurse"
PREPARED = "e-steps-7"  # the lesson rn-sbar-handoff prepares for it
OTHER = "e-accuracy-0"  # no lesson prepares for it


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=TRACK))


def targeted(client, h, ids=(PREPARED, OTHER), minutes=15):
    r = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "questions", "question_ids": list(ids), "duration_minutes": minutes},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def answer(client, h, iv, index, text=STRONG):
    r = client.post(
        f"/api/v1/interviews/{iv}/answers",
        headers=h,
        json={"question_index": index, "answer": text, "source": "typed"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def round_answers(client, h, iv):
    return {q["id"]: q for q in client.get(f"/api/v1/interviews/{iv}", headers=h).json()["questions"]}


def answer_conditions(client, h, qid):
    rows = client.get(f"/api/v1/careers/{TRACK}/questions/{qid}/answers", headers=h).json()
    return [r["conditions"] for r in rows]


def test_a_lesson_read_before_a_round_marks_only_the_answer_it_prepares(client):
    h = nurse(client)
    read_lesson(client, h)
    iv = targeted(client, h)
    answer(client, h, iv["id"], 0)
    answer(client, h, iv["id"], 1)
    qs = round_answers(client, h, iv["id"])
    prepared, other = qs[PREPARED]["answer"]["conditions"], qs[OTHER]["answer"]["conditions"]
    assert prepared["labels"] == ["Hint shown"]
    assert prepared["help"][0]["detail"].startswith("Lesson “")
    assert other["labels"] == ["No in-app help recorded"]
    for c in (prepared, other):
        assert c["round"] == {
            "recorded": True,
            "timed_minutes": 15,
            "follow_up": None,
            "ended_early": False,
            "text": "A 15-minute timed mock interview; no follow-up.",
        }
    # The same on the question page's past answers and in the replay.
    assert answer_conditions(client, h, PREPARED) == [prepared]
    review = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h).json()
    item = next(i for i in review["items"] if i["question_id"] == PREPARED)
    assert item["feedback"]["conditions"] == prepared


def test_the_recorded_conditions_are_kept_whatever_happens_later(client):
    """Read a lesson, answer the question on its own (that answer takes the read), then answer it in a
    round: no help before the round's answer. Deleting the earlier answer would now give the read
    to the round's answer if it were worked out again; it's recorded, so it isn't."""
    h = nurse(client)
    read_lesson(client, h)
    single = client.post(
        f"/api/v1/careers/{TRACK}/questions/{PREPARED}/answers", headers=h, json={"answer": STRONG}
    )
    assert single.json()["conditions"]["labels"] == ["Hint shown"]
    iv = targeted(client, h, ids=(PREPARED,))
    answer(client, h, iv["id"], 0)
    read_lesson(client, h)  # after the round: belongs to the next answer, never to this one
    with client.app.state.session_factory() as db:
        db.execute(delete(PracticeAnswer).where(PracticeAnswer.id == single.json()["id"]))
        db.commit()
    [kept] = answer_conditions(client, h, PREPARED)
    assert kept["labels"] == ["No in-app help recorded"] and kept["round"]["recorded"] is True


def test_a_round_from_before_recording_says_not_recorded_never_none(client):
    h = nurse(client)
    iv = targeted(client, h, ids=(OTHER,))
    answer(client, h, iv["id"], 0)
    with client.app.state.session_factory() as db:  # as a round saved before recording began
        turn = db.scalar(select(InterviewTurn).where(InterviewTurn.answer_id.is_not(None)))
        turn.meta = {k: v for k, v in (turn.meta or {}).items() if k != "conditions"}
        db.commit()
    [c] = answer_conditions(client, h, OTHER)
    assert c["labels"] == ["Not recorded"] and c["help"] == []
    assert c["recorded_from"] == "2026-11-15"
    assert (
        c["round"]["recorded"] is False and c["round"]["timed_minutes"] == 15
    )  # the format is the round's own


def test_another_accounts_lesson_reads_never_count(client):
    other = nurse(client, email="bea@example.com")
    read_lesson(client, other)
    h = nurse(client)
    iv = targeted(client, h, ids=(PREPARED,))
    answer(client, h, iv["id"], 0)
    assert round_answers(client, h, iv["id"])[PREPARED]["answer"]["conditions"]["labels"] == [
        "No in-app help recorded"
    ]


def test_a_follow_up_is_part_of_the_format_not_help(client):
    h = nurse(client)
    iv = start(client, h, "behavioral").json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers=h,
        json={"question_index": 0, "answer": VAGUE, "source": "typed"},
    ).json()
    assert r["round_format"]["pending_followup"] is not None
    followup(client, h, iv["id"], FULL)
    q0 = client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["questions"][0]
    c = q0["answer"]["conditions"]
    assert c["labels"] == ["No in-app help recorded"]
    assert c["round"]["follow_up"] == "answered"
    assert (
        c["round"]["text"]
        == "A 30-minute timed mock interview; the interviewer asked a follow-up, which you answered."
    )


def test_an_ended_early_round_says_so_and_records_nothing_for_what_it_never_reached(client):
    h = nurse(client)
    iv = targeted(client, h)
    answer(client, h, iv["id"], 0)
    assert client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h).status_code == 200
    qs = round_answers(client, h, iv["id"])
    answered, missed = qs[PREPARED], qs[OTHER]
    assert answered["answer"]["conditions"]["round"]["ended_early"] is True
    assert answered["answer"]["conditions"]["round"]["text"].endswith("; the round ended early.")
    assert answered["conditions_note"] is None
    assert missed["answer"] is None
    assert missed["conditions_note"] == "The round ended before this question: nothing was recorded for it."
    review = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h).json()
    item = next(i for i in review["items"] if i["question_id"] == OTHER)
    assert item["status"] == "not_reached" and item["conditions_note"] == missed["conditions_note"]
    with client.app.state.session_factory() as db:
        assert (
            db.scalar(
                select(InterviewTurn).where(
                    InterviewTurn.role == TurnRole.CANDIDATE, InterviewTurn.question_index == 1
                )
            )
            is None
        )


def test_a_retry_after_a_round_names_the_condition_that_differed(client):
    h = nurse(client)
    iv = targeted(client, h, ids=(OTHER,))
    first = answer(client, h, iv["id"], 0)
    score = first["questions"][0]["answer"]["score"]
    r = client.post(f"/api/v1/interviews/{iv['id']}/questions/0/retries", headers=h, json={"answer": STRONG})
    assert r.status_code in (200, 201), r.text
    c = r.json()
    assert c["classification"]["outcome"] == "partially_comparable"  # rules v1's verdict, as before
    assert (
        "the earlier one was timed (answered in a 15-minute mock interview); this one wasn't "
        "(answered as a retry after a mock interview)"
    ) in c["comparability_note"]
    # Conditions change no score.
    assert round_answers(client, h, iv["id"])[OTHER]["answer"]["score"] == score
