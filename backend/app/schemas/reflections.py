"""Private reflections on real interviews, and the next steps the learner chooses from them."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import APIModel

Outcome = Literal["unknown", "awaiting", "another_round", "offer", "not_selected", "withdrawn"]
ActionTarget = Literal["notebook", "schedule", "saved"]
Line = Annotated[str, Field(max_length=300)]


class ReflectionObservation(APIModel):
    text: str = Field(min_length=1, max_length=500)
    kind: Literal["observed", "interpretation"] = Field(
        description='observed: what happened ("they asked for another example"); interpretation: what you think it meant'
    )


class ReflectionIn(APIModel):
    questions: list[Line] = Field(default_factory=list, max_length=30, description="Paraphrased, not copied")
    topics: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=20)
    clear: str = Field(default="", max_length=3000)
    difficult: str = Field(default="", max_length=3000)
    observations: list[ReflectionObservation] = Field(default_factory=list, max_length=30)
    follow_ups: str = Field(default="", max_length=2000)
    practice: list[Line] = Field(default_factory=list, max_length=20)
    story_ids: list[Annotated[str, Field(max_length=36)]] = Field(default_factory=list, max_length=10)
    expected_revision: int = Field(ge=0, description="0 for the first save")


class ReflectionOutcomeChange(APIModel):
    outcome: Outcome
    at: datetime
    applied_to_application: bool


class ReflectionActionOut(APIModel):
    id: str
    kind: Literal["practice", "note", "gap"]
    title: str
    detail: str
    ref: str | None
    href: str | None
    status: Literal["suggested", "accepted", "dismissed"]
    targets: list[ActionTarget] = Field(description="Where this can go")
    target: ActionTarget | None
    applied_ref: str | None


class ReflectionOut(APIModel):
    event_id: str
    application_id: str
    application_archived: bool
    role_title: str
    employer: str
    stage: str
    event_title: str
    event_on: date | None
    questions: list[str]
    topics: list[str]
    clear: str
    difficult: str
    observations: list[ReflectionObservation]
    follow_ups: str
    practice: list[str]
    story_ids: list[str]
    outcome: Outcome
    outcome_history: list[ReflectionOutcomeChange]
    revision: int
    saved: bool
    updated_at: datetime | None
    warnings: list[str] = Field(
        description="Things that look like contact details or identifiers; nothing is blocked"
    )
    actions: list[ReflectionActionOut]


class ReflectionSummary(APIModel):
    event_id: str
    application_id: str
    application_archived: bool
    role_title: str
    employer: str
    event_title: str
    event_on: date | None
    outcome: Outcome
    topics: list[str]
    open_actions: int
    updated_at: datetime


class ReflectionActionEdit(APIModel):
    status: Literal["suggested", "dismissed"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    detail: str | None = Field(default=None, max_length=2000)


class ReflectionActionAccept(APIModel):
    target: ActionTarget
    on_date: date | None = Field(default=None, description="For the schedule")
    timezone: str | None = Field(default=None, max_length=64)


class ReflectionOutcomeIn(APIModel):
    outcome: Outcome
    update_application: bool = Field(
        default=False, description="Also move the application to the matching stage"
    )
