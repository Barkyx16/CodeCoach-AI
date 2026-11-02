"""Practice goals, the adaptive plan, today's session and the baseline assessment."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

Experience = Literal["new", "early", "mid", "senior"]
Format = Literal["written", "voice", "coding"]
ItemKind = Literal["assessment", "question", "retry", "review", "voice", "mock", "coding"]
ItemStatus = Literal["pending", "done", "skipped", "replaced"]


class GoalsIn(APIModel):
    track: str | None = Field(default=None, max_length=64, description="Default: your current career")
    specialty: str | None = Field(default=None, max_length=120)
    experience: Experience | None = None
    target_date: date | None = Field(default=None, description="Your interview date, if you know it")
    weekly_minutes: int | None = Field(default=None, ge=10, le=1200)
    focus_areas: list[str] = Field(default_factory=list, max_length=8, description="Skills of this career")
    formats: list[Format] = Field(default_factory=list, max_length=3)
    confidence: dict[str, int] = Field(
        default_factory=dict,
        description="Self-reported confidence per skill, 1-5 (never blended with scores)",
    )
    setup_skipped: bool = False


class GoalsOut(GoalsIn):
    track: str
    career_title: str
    has_coding: bool
    skills: list[str] = Field(
        description="Skills this career's questions practise (for focus and confidence)"
    )
    saved: bool = Field(description="False until goals are saved or setup is skipped")


class RoundStart(APIModel):
    """How to start the round an activity needs (POST /interviews with these fields)."""

    track: str
    difficulty: str | None = None
    question_ids: list[str] | None = None
    purpose: Literal["practice", "baseline"] = "practice"
    duration_minutes: int


class PlanItemOut(APIModel):
    id: str
    position: int
    kind: ItemKind
    skill: str
    title: str
    reason: str = Field(description="Why this activity was chosen")
    completion: str = Field(description="What counts as done")
    minutes: int = Field(description="Estimated duration")
    status: ItemStatus
    evidence: str | None = Field(description="What completed it, e.g. 'Answered, scored 72/100'")
    href: str | None = Field(description="Where to do it, when it's a page")
    round: RoundStart | None = Field(description="When it's a mock-interview round to start")
    can_mark_reviewed: bool
    can_replace: bool
    created_at: datetime
    resolved_at: datetime | None


class TodayOut(APIModel):
    minutes_available: int
    primary: PlanItemOut | None
    follow_up: PlanItemOut | None
    session_minutes: int
    note: str | None = Field(description="Explains the choice when nothing fits exactly")


class SelfRating(APIModel):
    skill: str
    rating: int


class EvaluatedSkill(APIModel):
    skill: str
    questions: int
    answers: int
    average_best_score: int


class CodingEvidence(APIModel):
    judge_available: bool
    judged_attempts: int
    passed: int
    saved_not_judged: int


class AssessmentOut(APIModel):
    state: Literal["building_baseline", "baseline_ready"]
    note: str
    self_reported: list[SelfRating] = Field(description="What you said; not a measurement")
    evaluated: list[EvaluatedSkill] = Field(description="Rubric scores of your answers; not correctness")
    coding: CodingEvidence | None = Field(description="Judge results only; null for careers without coding")


class PlanProgress(APIModel):
    done_this_week: int
    minutes_this_week: int = Field(description="Estimated minutes of activities completed in the last 7 days")
    weekly_minutes: int = Field(description="Your weekly practice time (default 60)")
    done_in_plan: int
    open_in_plan: int


class PlanOut(APIModel):
    track: str
    career_title: str
    version: int
    created_at: datetime
    changes: list[str] = Field(description="Why this version differs from the last one")
    items: list[PlanItemOut]
    progress: PlanProgress
    today: TodayOut
    assessment: AssessmentOut
    goals_saved: bool
    target_date: date | None
    days_to_interview: int | None
