"""Rubric v9 (Durable Saves briefs 11–13): denials and reported advice aren't evidence.

Development checks only (the cases they come from are exposed development data, not an
independent measurement). Each rule has controls that must keep their credit.
"""

from __future__ import annotations

import json

import pytest

from app.careers.grading import RUBRIC_VERSION, _denied_spans, grade
from app.careers.questions import get_question, questions_for
from evals.meta import EVAL_DIR


def denied(text: str) -> list[str]:
    return [text[a:b] for a, b in _denied_spans(text)]


def test_the_version():
    assert RUBRIC_VERSION in {"v9", "v10"}  # v10 keeps every v9 rule (tests/test_rubric_v10.py)


@pytest.mark.parametrize(
    ("text", "spans"),
    [
        (
            "I would not ring any customers or ask any agents anything; I'd change things straight away.",
            # v10: the whole clause, which ends at ";" within 30 words (v9 stopped at ten words)
            ["I would not ring any customers or ask any agents anything"],
        ),
        (
            "I wouldn't tell the customer or my team lead anything.",
            ["I wouldn't tell the customer or my team lead anything"],
        ),
        ("We never checked the second line.", ["We never checked the second line"]),
        ("I jump in to correct them instead of hearing them out.", ["instead of hearing them out"]),
        # The clause ends: what comes next still counts.
        ("I didn't wait, I called the doctor.", ["I didn't wait"]),
        ("I did not panic - I raised the bed and called for help.", ["I did not panic"]),
        (
            "i would not lecture and i would explain what high glucose does",
            ["i would not lecture"],
        ),  # dictated
        ("I didn't argue but I listened to the end.", ["I didn't argue"]),
    ],
)
def test_denials_cover_their_own_clause_only(text, spans):
    assert denied(text) == spans


@pytest.mark.parametrize(
    "text",
    [
        "I couldn't reach the doctor, so I called the registrar.",  # inability, not a refusal
        "I could not do both well, so I chose the assessment first.",  # names a trade-off
        "I have not yet had the chance to lead a team.",  # missing opportunity
        "I listened without interrupting.",  # "without" can describe good practice
        "I acted without delay.",
        "Not only did I call the doctor, I also updated the family.",
        "I didn't just tell him to wait; I explained why.",
        "The doctor didn't answer, so I paged her again.",  # someone else's negation
        "He would not take his tablets until I explained why.",
    ],
)
def test_these_are_not_denials(text):
    assert not any(
        s for s in denied(text) if "I explained" in s or "I called" in s or "I paged" in s or "I chose" in s
    )
    assert all(
        not s.lower().startswith(
            (
                "i couldn",
                "i could not",
                "i have not",
                "without",
                "not only",
                "i didn't just",
                "the doctor",
                "he would",
            )
        )
        for s in denied(text)
    )


def test_reported_advice_isnt_the_learners_account():
    text = (
        "Advice I was given: 1) Specific beats generic every time, so use your own words. 2) Show the interviewer the "
        "real parts of the work. 3) One short real example is what makes an answer believable. Remember all four. "
        "Then I told the customer what I could do."
    )
    spans = denied(text)
    assert (
        len(spans) == 1
        and spans[0].startswith("Advice I was given:")
        and "I told the customer" not in spans[0]
    )
    # Without a colon the frame covers its clause only.
    assert denied("I was told to escalate early, so I called the doctor.") == ["I was told to escalate early"]


def _case(set_file: str, case_id: str) -> tuple[dict, dict]:
    data = json.loads((EVAL_DIR / set_file).read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in data["cases"]}
    return data, cases[case_id]


def test_a_refused_action_no_longer_earns_the_point_its_typed_pair_earns():
    data, changed = _case("career_csr_families_dev.json", "cd-6-B-meaning_changed")
    typed = next(c for c in data["cases"] if c["id"] == changed["pair_of"])
    q = get_question(data["track"], changed["question_id"], changed["question_version"])
    label = "Gathers information before acting"
    assert {p.label: p.covered for p in grade(q, typed["answer"]).points}[label] is True
    assert {p.label: p.covered for p in grade(q, changed["answer"]).points}[label] is False


@pytest.mark.parametrize(
    ("form", "middle", "conflicts"),
    [
        ("full stop", "I called the doctor straight away. I didn't call the doctor.", 1),
        ("comma splice", "I called the doctor straight away, I didn't call the doctor.", 1),
        ("dictated run-on", "so I called the doctor straight away and then I didn't call the doctor", 1),
        ("never vs did", "I never called the doctor. Then I called the doctor using SBAR.", 1),
        ("self-correction", "I called the doctor, sorry, I mean I called the registrar first.", 0),
        ("later action", "At first I didn't call the doctor. An hour later I called the doctor.", 0),
        (
            "quoted speech",
            'The relative said "you didn\'t call the doctor", but I had called the doctor at 2 am.',
            0,
        ),
        ("unrelated negation", "I called the doctor straight away. I didn't wake the other patients.", 0),
    ],
)
def test_explicit_contradictions_in_every_written_form_and_their_controls(form, middle, conflicts):
    q = next(x for x in questions_for("registered-nurse") if x.kind == "behavioral")
    text = (
        "Last winter on a busy night shift a patient on my ward became breathless and I was the nurse responsible "
        f"for him. I checked his observations and sat him upright. {middle} Within the hour his oxygen was back to "
        "96% and I learned to escalate earlier."
    )
    assert len([c for c in grade(q, text).conflicts if c.status == "conflict"]) == conflicts, form
