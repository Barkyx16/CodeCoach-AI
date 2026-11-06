"""Which careers' written-answer feedback has been measured, and what that means (Volume 4 prompt 10).

Every career in the catalog gets written-answer feedback from the same built-in coach: checks on
answer structure (a situation, actions, a result, reflection), plus the career profile's own
vocabulary (its skills, tools, people and metrics). That is general interview-structure feedback.
For two careers it has also been measured against labelled examples written for that career;
for every other career it hasn't, and the feedback says so rather than implying it has.

Nothing here judges domain correctness. Points worded "Explains <metric> correctly" are met when
the answer discusses that metric; whether what it says is right needs someone who knows the work,
and the feedback says that too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.careers import CATALOG

Status = Literal["measured", "not_measured"]


@dataclass(frozen=True)
class CareerEvaluation:
    status: Status
    note: str  # one line for learners
    owner: str = "CodeCoach's built-in rubric (app/careers/questions.py)"
    source: str = "generated from the product's question templates and the career profile"
    review: str = "not reviewed by a practitioner of this career"
    rubric_version: str | None = None  # the rubric it was last measured with
    formats: tuple[str, ...] = ()  # the question kinds the measurement covers
    sets: tuple[str, ...] = ()  # evaluation sets (backend/evals/datasets.json)


_KINDS = ("knowledge", "behavioral", "situational", "leadership", "motivation")
_MEASURED_NOTE = (
    "This career's feedback has been checked against example answers written for it, including once "
    "on a separate set kept back for that purpose; the examples were labelled by an AI and not "
    "reviewed by a person, so treat the feedback as a guide to structure."
)

MEASURED: dict[str, CareerEvaluation] = {
    "registered-nurse": CareerEvaluation(
        "measured",
        _MEASURED_NOTE,
        rubric_version="v8",
        formats=_KINDS,
        sets=(
            "career-rn-dev",
            "career-rn-holdout",
            "career-rn-families-dev",
            "career-rn-contradiction-pairs",
            "career-rn-injection-challenges",
            "career-rn-action-wording",
            "career-rn-sealed (graded once, 2026-11-04)",
        ),
    ),
    "customer-service-representative": CareerEvaluation(
        "measured",
        _MEASURED_NOTE,
        rubric_version="v8",
        formats=_KINDS,
        sets=("career-csr-families-dev", "career-csr-sealed (graded once, 2026-11-04)"),
    ),
}


def evaluation_for(track: str) -> CareerEvaluation:
    """How far a career's written-answer feedback has been checked. Unknown or unmeasured careers
    still get feedback: general structure checks, labelled as not measured for that career."""
    if track in MEASURED:
        return MEASURED[track]
    title = CATALOG[track].title if track in CATALOG else "this career's"
    return CareerEvaluation(
        "not_measured",
        f"These are general interview-structure checks; they haven't been measured on {title} answers, "
        "so treat them as a guide to structure only.",
    )


_DOMAIN = re.compile(r"^Explains .+ correctly$")
DOMAIN_NOTE = "Checks that you discuss it, not whether what you say is right."


def scope_note(label: str) -> str | None:
    """A note for a point whose wording suggests a judgement of domain correctness the rubric can't
    make (it only checks that the answer discusses the subject)."""
    return DOMAIN_NOTE if _DOMAIN.match(label) else None
