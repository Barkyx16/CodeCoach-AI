"""Rubric transparency and self-review for written answers."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.careers import AnswerOut
from app.schemas.common import APIModel

SelfRating = Literal["no", "partly", "yes"]


class CriterionLevel(APIModel):
    level: Literal["not_yet", "there"]
    text: str


class Criterion(APIModel):
    label: str = Field(description="What a strong answer does")
    description: str = Field(description="In plain words, what to include")
    levels: list[CriterionLevel]


class Check(APIModel):
    text: str
    kind: Literal["deterministic"] = "deterministic"


class CriteriaOut(APIModel):
    question_id: str
    content_version: int
    rubric_version: str
    coach: str
    criteria: list[Criterion] = Field(description="Qualitative points the coach looks for in your words")
    checks: list[Check] = Field(description="Fixed rules that apply to every answer (length, numbers)")
    disclaimer: str


class SelfReviewIn(APIModel):
    went_well: str = Field(default="", max_length=2000)
    improve: str = Field(default="", max_length=2000)
    ratings: dict[str, SelfRating] = Field(default_factory=dict, description="Criterion label → your rating")
    skipped: bool = False
    before_feedback: bool = Field(default=True, description="Written before reading the feedback")


class SelfReviewOut(APIModel):
    went_well: str
    improve: str
    ratings: dict[str, SelfRating]
    skipped: bool
    before_feedback: bool
    updated_at: datetime


class FlagIn(APIModel):
    criterion: str = Field(min_length=1, max_length=200)
    kind: Literal["unclear", "disagree"]
    note: str = Field(default="", max_length=1000)


class FlagOut(APIModel):
    id: int
    criterion: str
    kind: Literal["unclear", "disagree"]
    note: str
    created_at: datetime


class EvaluationOut(APIModel):
    id: int
    rubric_version: str
    content_version: int
    score: int
    rating: str
    summary: str
    evidence_level: Literal["sufficient", "insufficient"]
    points: list[dict]
    reason: str
    created_at: datetime


class AnswerPerspective(APIModel):
    criterion: str
    yours: SelfRating | None = Field(description="Your rating, if you gave one")
    coach: bool = Field(description="Whether the coach found it in your words")


class RepeatedArea(APIModel):
    criterion: str
    times: int = Field(description="How many of your recent answers on this career it wasn't found in")
    of: int


class AnswerReviewOut(APIModel):
    answer: AnswerOut
    self_review: SelfReviewOut | None
    perspectives: list[AnswerPerspective]
    repeated: list[RepeatedArea]
    flags: list[FlagOut]
    evaluations: list[EvaluationOut] = Field(
        description="Later evaluations; the original result is never replaced"
    )
    can_reevaluate: bool
    reevaluate_note: str
