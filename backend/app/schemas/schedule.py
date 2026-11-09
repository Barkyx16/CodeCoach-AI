"""Scheduling existing activities on a calendar the learner controls."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey

ScheduleKind = Literal["plan_item", "review_item", "question", "problem", "application_event", "drill"]


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
    client_request_id: OptionalKey = Field(default=None, max_length=64)


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
    follows_interview: bool = Field(
        default=False,
        description="Interview preparation the learner chose to keep relative to its interview. It still "
        "never moves by itself: a reschedule offers a preview, and only selected entries move.",
    )


class SchedulableOut(APIModel):
    """Something you could put on the schedule, from your plan, review queue or applications."""

    kind: ScheduleKind
    ref: str
    title: str
    detail: str
    minutes: int | None


class FollowInterviewIn(APIModel):
    follows: bool = Field(
        description="True: keep this preparation relative to its interview; false: a fixed time"
    )
    expected_sequence: int = Field(ge=0, description="The entry's sequence you loaded; a newer one is a 409")


class PrepTime(APIModel):
    on_date: date
    local_time: str | None
    timezone: str | None
    starts_at: datetime | None
    all_day: bool = False


PrepStatus = Literal[
    "can_move",  # follows the interview, which has moved: a new time is proposed
    "aligned",  # follows the interview and already matches its current time
    "fixed",  # a fixed time (the default): it stays where it is
    "untimed",  # an all-day entry: there's no exact time to keep relative
    "interview_time_unknown",  # the interview has no exact time now (date only, or none)
    "past",  # this preparation time has passed: it isn't moved
    "would_be_past",  # the new time would already have passed: choose one yourself
]


class PrepEntryOut(APIModel):
    id: str
    title: str
    sequence: int
    follows_interview: bool
    current: PrepTime
    status: PrepStatus
    proposal: PrepTime | None = Field(description="Where it would move to (in its own time zone), if it can")
    note: str = Field(description="What happens to it, in plain words")


class PrepShiftOut(APIModel):
    event_id: str
    event_title: str
    event_starts_at: datetime | None = Field(
        description="The interview's exact start now; send it back when applying, so a newer change is caught"
    )
    event_on_date: date | None
    event_local_time: str | None
    event_timezone: str | None
    entries: list[PrepEntryOut]


class PrepShiftEntryIn(APIModel):
    id: str = Field(max_length=36)
    sequence: int = Field(ge=0, description="The sequence the preview showed")


class PrepShiftIn(APIModel):
    event_starts_at: datetime | None = Field(description="The interview start the preview showed")
    entries: list[PrepShiftEntryIn] = Field(
        min_length=1, max_length=50, description="Only the entries you chose"
    )


class PrepShiftResult(APIModel):
    moved: list[str] = Field(description="Entries moved now")
    already_aligned: list[str] = Field(
        description="Chosen entries that already match the interview's current time (moved earlier, by a resend or "
        "by hand); not moved now"
    )
    preview: PrepShiftOut
