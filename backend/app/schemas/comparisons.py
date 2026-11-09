"""Comparing authored sample answers: lessons, the learner's reading, and the explanation."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import APIModel


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


class ComparisonAttemptSummary(APIModel):
    id: str
    lesson_version: int
    selections: int
    matches: int
    revealed_early: bool
    created_at: datetime
