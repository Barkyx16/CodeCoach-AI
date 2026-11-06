"""Simulated interviewer engagement: every state comes from evidence in the answer text."""

import re

import pytest

from app.careers.grading import grade
from app.careers.questions import questions_for
from app.models import InterviewPhase
from app.services.engagement import for_career_answer, for_coding_message

NURSE = questions_for("registered-nurse")


def q(kind: str, difficulty: str = "easy"):
    return next(x for x in NURSE if x.kind == kind and x.difficulty == difficulty)


def read(question, text):
    return for_career_answer(question, text, grade(question, text))


STRONG = (
    "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. patient assessment. "
    "I was responsible for five patients, so I had to move fast. I checked his vital signs again and started "
    "oxygen per protocol. I called the rapid response team and asked the charge nurse to cover my other "
    "patients. I updated the doctor and documented everything. As a result, he was stable within 30 minutes, "
    "and I learned to escalate early instead of waiting to be sure."
)


def test_too_short_is_not_enough_evidence():
    r = read(q("behavioral"), "I am good at this and I care a lot.")
    assert r.state == "not_enough_evidence"
    assert "10 words" in r.reason


def test_off_topic_answer_names_the_missing_topic():
    question = q("knowledge")
    topic = question.tags[0]
    text = (
        "I really enjoy working with people and I always try my best to be friendly, helpful and calm every day "
        "at work with everyone. I think a positive attitude matters more than anything else in a busy team."
    )
    r = read(question, text)
    assert r.state == "more_detail" and topic in r.reason


def test_we_without_i_asks_for_personal_contribution():
    question = q("behavioral")
    topic = question.tags[0]
    text = (
        f"On our ward we had a hard week with {topic}. We worked together, we stayed late, we checked every "
        "patient twice and we kept the family updated. In the end we got through it and we were proud of it."
    )
    r = read(question, text)
    assert r.state == "more_detail"
    assert "personally" in r.reason and any("“we”" in e for e in r.evidence)


def test_specific_well_covered_answer_is_ready_to_explore_and_quotes_the_detail():
    question = q("behavioral")
    text = STRONG.replace("patient assessment", question.tags[0])
    r = read(question, text)
    assert r.state in ("explore_further", "following")
    assert any(e.startswith("Specific detail:") for e in r.evidence)
    if r.state == "explore_further":
        assert re.search(r"“.*\d.*”", r.reason)


@pytest.mark.parametrize("text", [STRONG, STRONG.upper()])
def test_reasons_refer_to_the_answer_never_to_feelings_or_hiring(text):
    for question in NURSE[::25]:
        r = read(question, text)
        words = r.reason.lower()
        for banned in (
            "like you",
            "likes you",
            "hire",
            "hired",
            "feel",
            "mood",
            "impressed",
            "bored",
            "personality",
        ):
            assert banned not in words, (question.id, r.reason)
        assert r.reason.startswith(r.label)


def test_voice_or_typed_makes_no_difference():
    # The function never receives the source: identical text gives identical reads.
    question = q("situational", "medium")
    assert read(question, STRONG) == read(question, STRONG)


@pytest.mark.parametrize(
    ("phase", "message", "state"),
    [
        (InterviewPhase.CLARIFY, "Can the array be empty or contain duplicates?", "following"),
        (InterviewPhase.CLARIFY, "Okay I will start coding the solution now then.", "more_detail"),
        (
            InterviewPhase.APPROACH,
            "I would use a hash map from value to index in one pass.",
            "explore_further",
        ),
        (InterviewPhase.APPROACH, "I'd check every pair with a nested loop.", "more_detail"),
        (InterviewPhase.COMPLEXITY, "It runs in O(n) time and O(n) space.", "explore_further"),
        (InterviewPhase.COMPLEXITY, "It is pretty fast I think overall.", "more_detail"),
        (InterviewPhase.WRAP_UP, "Let me trace the empty input and a duplicate pair.", "following"),
        (InterviewPhase.CLARIFY, "ok", "not_enough_evidence"),
    ],
)
def test_coding_messages(phase, message, state):
    r = for_coding_message(phase, message, "O(n)")
    assert r.state == state, r.reason
    assert r.reason.startswith(r.label) and r.evidence


def test_a_repeated_complexity_is_one_piece_of_evidence():
    r = for_coding_message(
        InterviewPhase.COMPLEXITY, "It runs in O(n) time and O(n) space, or O(1) space with sorting.", "O(n)"
    )
    assert r.evidence == ["Stated: O(n)", "Stated: O(1)"]
