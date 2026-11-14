"""Accepted improvements (Volume 12, prompt 1; docs/ACCEPTED_ACTIONS.md): one action per accepted
suggestion, shown by the plan page, the schedule and an interview kit's checklist by its id."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey, SaveReplay, save_replay_field, update_key_field

Recurrence = Literal["once", "weekly"]
MAX_WEEKS = 8


class ActionSourceIn(APIModel):
    kind: Literal["interview_improvement"] = "interview_improvement"
    interview_id: str = Field(max_length=36)
    key: str = Field(
        min_length=1, max_length=200, description="The improvement's `key` in the interview review"
    )


class ActionAccept(APIModel):
    """Accept one suggested improvement. The suggestion is the identity: accepting it again (a double
    click, another tab, a resend after a lost reply) returns the action it made, never a second one."""

    source: ActionSourceIn
    recurrence: Recurrence = "once"


class ActionVersion(APIModel):
    question: str
    version: int = Field(description="The question's version in the answer the feedback came from")


class ActionSource(APIModel):
    kind: Literal["interview_improvement"]
    interview_id: str
    key: str
    label: str = Field(description="The improvement as it was titled when you accepted it")
    why: str = Field(description="The feedback it came from, as it read when you accepted it")
    interview_title: str
    interview_date: datetime | None
    versions: list[ActionVersion] = Field(default_factory=list)
    available: bool = Field(description="False when the interview it came from no longer exists")


class OccurrenceOut(APIModel):
    id: str = Field(description="The schedule entry's id")
    on_date: date
    all_day: bool
    local_time: str | None
    timezone: str | None
    starts_at: datetime | None
    status: Literal["scheduled", "cancelled"]
    sequence: int
    completed_at: datetime | None = Field(
        description="When you said this occurrence was done (a one-off: when the action was done)"
    )


class ActionOut(APIModel):
    id: str
    title: str
    notes: str
    practice_href: str | None
    practice_label: str | None
    recurrence: Recurrence
    status: Literal["open", "done"] = Field(
        description="A one-off is done when you say so; a weekly action stays open (each occurrence is done or not)"
    )
    done_at: datetime | None
    source: ActionSource
    occurrences: list[OccurrenceOut]
    attempts_since: int | None = Field(
        description="Practice of its target since you accepted it (null when that can't be counted)"
    )
    revision: int
    save_replay: SaveReplay | None = save_replay_field()
    created_at: datetime
    updated_at: datetime


class ActionUpdate(APIModel):
    """Rename it or change its notes, against the revision you loaded (409 stale_revision with the
    saved action in details.current if it changed since)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    recurrence: Recurrence | None = Field(
        default=None,
        description="Once or weekly: only while nothing is on the schedule for it and it isn't marked done",
    )
    expected_revision: int = Field(ge=1)
    client_request_id: OptionalKey = update_key_field()


class OccurrencesIn(APIModel):
    """Put it on the schedule: one occurrence for a one-off, or one a week for `weeks` weeks for a
    weekly action. Moving an occurrence later is the schedule's own move: same entry, same id."""

    on_date: date
    all_day: bool = True
    local_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    timezone: str | None = Field(default=None, max_length=64)
    fold: int | None = Field(default=None, ge=0, le=1)
    duration_min: int = Field(default=30, ge=5, le=480)
    weeks: int = Field(default=1, ge=1, le=MAX_WEEKS)
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=60,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Sending the same request again (its reply was lost) returns the occurrences it made",
    )
