"""Private application tracker: real applications as the learner records them."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel

Stage = Literal["saved", "applied", "interviewing", "offer", "closed", "withdrawn"]
STAGES: tuple[Stage, ...] = ("saved", "applied", "interviewing", "offer", "closed", "withdrawn")
EventKind = Literal["phone_screen", "interview", "assessment", "other"]


def _http_link(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip()
    if not (v.lower().startswith("https://") or v.lower().startswith("http://")) or any(
        c.isspace() for c in v
    ):
        raise ValueError("Links must start with https:// or http:// (they're never opened by CodeCoach).")
    return v


class ApplicationFields(APIModel):
    employer: str | None = Field(default=None, min_length=1, max_length=120)
    role_title: str | None = Field(default=None, min_length=1, max_length=120)
    link: str | None = Field(default=None, max_length=500)
    applied_on: date | None = None
    next_action: str | None = Field(default=None, max_length=300)
    next_action_due: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    target_id: str | None = Field(default=None, max_length=36)
    story_ids: list[str] | None = Field(default=None, max_length=20)

    @field_validator("link")
    @classmethod
    def _check_link(cls, v: str | None) -> str | None:
        return _http_link(v)


class ApplicationCreate(ApplicationFields):
    employer: str = Field(min_length=1, max_length=120)
    role_title: str = Field(min_length=1, max_length=120)
    stage: Stage = "saved"
    client_request_id: str | None = Field(
        default=None,
        max_length=64,
        description="Repeat the same id to retry safely: one application is created",
    )


class ApplicationUpdate(ApplicationFields):
    clear: list[Literal["link", "applied_on", "next_action_due", "target_id"]] = Field(
        default_factory=list, description="Fields to empty (a date or link that turned out to be wrong)"
    )


class ApplicationStageIn(APIModel):
    stage: Stage
    note: str = Field(default="", max_length=300)
    correction: bool = Field(default=False, description="true: fixing a mistake, not a new development")


class ApplicationStageChangeOut(APIModel):
    from_stage: Stage | None
    to_stage: Stage
    correction: bool
    note: str
    role_title: str = Field(description="As it was when the stage changed")
    employer: str = Field(description="As it was when the stage changed")
    changed_at: datetime


class ApplicationEventIn(APIModel):
    kind: EventKind = "interview"
    title: str = Field(min_length=1, max_length=120)
    on_date: date | None = Field(default=None, description="Unknown is fine")
    local_time: str | None = Field(default=None, description="24-hour HH:MM, in `timezone`")
    timezone: str | None = Field(default=None, max_length=64, description="IANA name, e.g. America/Chicago")
    fold: int | None = Field(
        default=None, ge=0, le=1, description="For a time that happens twice: 0 first, 1 second"
    )
    notes: str = Field(default="", max_length=2000)
    client_request_id: str | None = Field(default=None, max_length=64)


class ApplicationEventOut(APIModel):
    id: str
    kind: EventKind
    title: str
    on_date: date | None
    local_time: str | None
    timezone: str | None
    starts_at: datetime | None = Field(
        description="Exact instant (UTC), only when date, time and zone are known"
    )
    notes: str
    created_at: datetime


class ApplicationTargetLink(APIModel):
    id: str
    title: str


class ApplicationStoryLink(APIModel):
    id: str
    title: str


class ApplicationSummary(APIModel):
    id: str
    employer: str
    role_title: str
    stage: Stage
    applied_on: date | None
    next_action: str
    next_action_due: date | None
    target: ApplicationTargetLink | None = Field(description="The linked job target")
    archived: bool
    next_event: ApplicationEventOut | None
    updated_at: datetime


class ApplicationOut(ApplicationSummary):
    link: str | None
    notes: str
    stories: list[ApplicationStoryLink]
    events: list[ApplicationEventOut]
    history: list[ApplicationStageChangeOut]
    created_at: datetime
