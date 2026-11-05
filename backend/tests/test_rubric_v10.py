"""Rubric v10 (Verification briefs 12 and 13): what didn't happen isn't evidence.

New development pairs, written by the tuning session (development data, not an independent
measurement). One sentence changes inside an answer that otherwise lacks the point; each rule has
controls that must keep their credit. Two residuals are pinned as strict expected failures, so a
later fix is noticed: a colleague's action and an imagined one still earn the point.
"""

from __future__ import annotations

import json

import pytest

from app.careers.grading import RUBRIC_VERSION, _denied_spans, grade
from app.careers.questions import get_question
from evals.meta import EVAL_DIR

BASE = (
    "Last spring a double charge showed up on an account, and it mattered because the account holder was "
    "about to cancel. {X} In the end the charge was reversed within a day. I learned to slow down before "
    "promising anything."
)


@pytest.fixture(scope="module")
def question():
    data = json.loads((EVAL_DIR / "career_csr_families_dev.json").read_text(encoding="utf-8"))
    case = next(c for c in data["cases"] if c["id"] == "cd-6-A-typed")
    return get_question(data["track"], case["question_id"], case["question_version"])


def covered(question, sentence: str, point: str) -> bool:
    return {p.label: p.covered for p in grade(question, BASE.format(X=sentence)).points}[point]


GATHERS = "Gathers information before acting"
TELLS = "Communicates with the right people"


def test_the_version():
    assert RUBRIC_VERSION == "v10"


def test_the_base_lacks_both_points(question):
    assert not covered(question, "The queue was long.", GATHERS)
    assert not covered(question, "The queue was long.", TELLS)


@pytest.mark.parametrize(
    "sentence",
    [
        "I asked for the order number and checked the payment history before changing anything.",
        "We asked for the order number and checked the payment history before changing anything.",  # team
        "i asked for the order number and checked the payment history before changing anything",  # dictated
        "First I'd ask for the order number and check the payment history before changing anything.",  # a plan
        "I would have to ask for the order number and check the payment history first.",  # obligation, a plan
    ],
)
def test_controls_keep_their_credit(question, sentence):
    assert covered(question, sentence, GATHERS)


@pytest.mark.parametrize(
    "sentence",
    [
        "I was going to ask for the order number and check the payment history, but I didn't get to.",
        "I meant to ask for the order number and check the payment history before changing anything.",
        "I thought about asking for the order number and checking the payment history.",
        "I should have asked for the order number and checked the payment history first.",
        "We'd have asked for the order number and checked the payment history if there had been time.",
    ],
)
def test_actions_that_did_not_happen_earn_nothing(question, sentence):
    assert not covered(question, sentence, GATHERS)


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("I escalated nothing and I told no one about it.", False),  # the object denied
        (
            "I did not reply to the email or ring the account holder back or ever tell my lead about it.",
            False,
        ),
        ("I escalated it and I told my lead about it.", True),  # control
        ("I would have a quick talk with my lead about it.", True),  # plan language, not a regret
    ],
)
def test_denied_objects_and_long_listed_denials(question, sentence, expected):
    assert covered(question, sentence, TELLS) is expected


def test_a_long_unpunctuated_run_on_is_still_bounded():
    """Without a clause end the denial stops at ten words after its frame: a dictated run-on keeps
    the rest of what it says."""
    text = (
        "i would not ring the account holder or the lead or the duty manager or anyone at all on the floor "
        "that whole afternoon so the refund went through"
    )
    [span] = [text[a:b] for a, b in _denied_spans(text)]
    assert span.startswith("i would not ring") and "refund went through" not in span


@pytest.mark.xfail(strict=True, reason="residual: a colleague's action is credited (needs who did it)")
def test_residual_a_colleagues_action(question):
    assert not covered(
        question, "My colleague asked for the order number and checked the payment history.", GATHERS
    )


@pytest.mark.xfail(strict=True, reason="residual: an imagined action is credited")
def test_residual_an_imagined_action(question):
    assert not covered(
        question, "I imagined asking for the order number and checking the payment history.", GATHERS
    )
