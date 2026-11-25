"""Comparing authored sample answers: lessons, the learner's reading, and the explanation."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey
from app.schemas.conditions import AttemptConditions


class ComparisonSummary(APIModel):
    id: str
    title: str
    teaching_goal: str


class ComparisonSentence(APIModel):
    id: str
    text: str


class ComparisonSample(APIModel):
    id: str
    label: str
    sentences: list[ComparisonSentence]


class ComparisonRubricItem(APIModel):
    id: str
    label: str


class ComparisonLesson(APIModel):
    """The question and the samples, before any reveal: no explanation."""

    id: str
    version: int
    title: str
    teaching_goal: str
    question: str
    rubric: list[ComparisonRubricItem]
    kind: Literal["clear", "tradeoff"] = Field(
        description="tradeoff: no single best answer, so no choice is asked"
    )
    samples: list[ComparisonSample]
    next_step: dict[str, str]
    review_status: str


class ComparisonSelectionIn(APIModel):
    sample: str = Field(max_length=8)
    sentence: str = Field(max_length=16)
    kind: Literal["strength", "gap"]
    reason: str = Field(max_length=600)


class ComparisonAttemptIn(APIModel):
    selections: list[ComparisonSelectionIn] = Field(min_length=1, max_length=12)
    choice: str | None = Field(default=None, max_length=8)
    revealed_early: bool = Field(default=False, description="The explanation was opened before this was sent")


class ComparisonAttemptOut(APIModel):
    id: str
    lesson_id: str
    lesson_version: int
    current_version: int | None
    title: str
    question: str
    samples: list[ComparisonSample] = Field(description="As they were when this attempt was made")
    rubric: list[ComparisonRubricItem]
    selections: list[dict[str, Any]]
    choice: str | None
    feedback: dict[str, Any]
    explanation: dict[str, Any]
    revealed_early: bool
    created_at: datetime
    conditions: AttemptConditions | None = Field(
        default=None, description="The in-app help shown before this attempt (docs/ATTEMPT_CONDITIONS.md)"
    )


class ExplanationOpenIn(APIModel):
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="A key for this opening: sent again after a lost reply, it's the same opening",
    )


class ExplanationOpened(APIModel):
    """The explanation, opened on your account first (Volume 19, prompt 5)."""

    explanation: dict[str, Any]
    lesson_version: int
    opened_at: datetime = Field(
        description="The first opening at this version of the lesson: every reading sent after it at this "
        "version says the explanation was opened then. Opening it again doesn't move it."
    )
    source: Literal["opened", "with_result"] = Field(
        default="opened",
        description="How it was first seen at this version: opened on its own, or shown with an earlier "
        "reading's result (Volume 20, prompt 3), whose time `opened_at` then is",
    )


class ComparisonAttemptSummary(APIModel):
    id: str
    lesson_version: int
    selections: int
    matches: int
    revealed_early: bool
    created_at: datetime
    conditions: AttemptConditions | None = Field(
        default=None, description="The in-app help shown before this attempt (docs/ATTEMPT_CONDITIONS.md)"
    )
