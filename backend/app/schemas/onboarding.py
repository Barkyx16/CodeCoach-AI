"""The optional first-session introduction: where a learner is in it and what to start with."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

TourStatus = Literal["not_started", "in_progress", "paused", "completed", "skipped"]
TourKind = Literal["written", "coding"]
StartChoice = Literal["practice", "intro", "library", "later"]
TourAction = Literal["start", "step", "pause", "complete", "skip"]
Dismissible = Literal["welcome", "resume_tour"]


class StarterActivity(APIModel):
    """A real, short activity from the learner's own career: never a sample or a demo record."""

    kind: Literal["question", "problem"]
    track: str
    ref: str = Field(description="Question id or problem slug")
    title: str
    difficulty: str
    href: str
    minutes: int = Field(description="A rough estimate of how long it takes, for planning only")


class CareerIntro(APIModel):
    """Offered once after a career change: how practice works for the new career's format."""

    track: str
    title: str
    kind: TourKind


class OnboardingOut(APIModel):
    tour_status: TourStatus
    tour_kind: TourKind | None
    tour_step: int
    tour_steps: int = Field(description="How many steps the tour for tour_kind has")
    start_choice: StartChoice | None
    welcome_due: bool = Field(description="Hasn't chosen how to start and hasn't practised yet")
    resume_due: bool = Field(description="Left the tour part-way and hasn't dismissed the reminder")
    career_intro: CareerIntro | None
    first_activity_at: datetime | None = Field(
        description="When the learner first answered a question or submitted code (from their real "
        "activity; the tour never counts)"
    )
    starter: StarterActivity | None
    format: TourKind = Field(description="The current career's practice format")


class OnboardingUpdate(APIModel):
    """One change at a time is typical; every field is optional and each is idempotent."""

    start_choice: StartChoice | None = None
    tour: TourAction | None = None
    tour_kind: TourKind | None = Field(
        default=None, description="With tour=start; defaults to the career's format"
    )
    tour_step: int | None = Field(default=None, ge=0, le=20, description="With tour=start or tour=step")
    dismiss: Dismissible | None = None
    career_intro_seen: bool | None = Field(
        default=None, description="true: don't offer the current career's format introduction again"
    )
