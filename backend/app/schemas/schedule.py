"""Scheduling existing activities on a calendar the learner controls."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

ScheduleKind = Literal["plan_item", "review_item", "question", "problem", "application_event"]


class ScheduleSettingsOut(APIModel):
    timezone: str | None = Field(description="The schedule's IANA time zone; null until one is chosen")
    reminders: bool = Field(description="In-app reminders, shown only while CodeCoach is open in a tab")
    reminder_minutes: int
    quiet_start: str | None
    quiet_end: str | None


class ScheduleSettingsIn(APIModel):
    timezone: str | None = Field(default=None, max_length=64)
    reminders: bool | None = None
    reminder_minutes: int | None = Field(default=None, ge=0, le=240)
    quiet_start: str | None = Field(default=None, description="HH:MM, or empty to turn quiet hours off")
    quiet_end: str | None = None


class EntryIn(APIModel):
    kind: ScheduleKind
    ref: str = Field(
        min_length=1, max_length=200, description="The activity's id (question: 'track/question_id')"
    )
    on_date: date
    all_day: bool = False
    local_time: str | None = Field(default=None, description="HH:MM in `timezone`; required unless all-day")
    timezone: str | None = Field(default=None, max_length=64)
    fold: int | None = Field(
        default=None, ge=0, le=1, description="For a time that happens twice: 0 first, 1 second"
    )
    duration_min: int = Field(default=30, ge=5, le=480)
    notes: str = Field(default="", max_length=500)
    client_request_id: str | None = Field(default=None, max_length=64)


class EntryMove(APIModel):
    on_date: date
    all_day: bool = False
    local_time: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    fold: int | None = Field(default=None, ge=0, le=1)
    duration_min: int | None = Field(default=None, ge=5, le=480)
    notes: str | None = Field(default=None, max_length=500)


class EntryOut(APIModel):
    id: str
    uid: str
    kind: ScheduleKind
    ref: str
    title: str
    href: str | None = Field(description="Where to do the activity")
    all_day: bool
    on_date: date
    local_time: str | None
    timezone: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    duration_min: int
    status: Literal["scheduled", "cancelled"]
    done_at: datetime | None = Field(description="When the activity was actually done, by its own rules")
    available: bool = Field(description="False if the activity is gone or retired")
    conflicts: list[str] = Field(description="Ids of other timed entries that overlap this one")
    sequence: int
    notes: str
    created_at: datetime


class SchedulableOut(APIModel):
    """Something you could put on the schedule, from your plan, review queue or applications."""

    kind: ScheduleKind
    ref: str
    title: str
    detail: str
    minutes: int | None
