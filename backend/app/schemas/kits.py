"""The interview-day kit for a recorded interview event."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.applications import _http_link
from app.schemas.common import APIModel

KitFormat = Literal["remote", "in_person", "phone", "unknown"]
QuestionGroup = Literal["role", "team", "training", "workflow", "next_steps", "other"]


class Interviewer(APIModel):
    name: str = Field(default="", max_length=80, description="As you know it; unknown is fine")
    role: str = Field(default="", max_length=80)


class ChecklistItem(APIModel):
    id: str = Field(max_length=40)
    text: str = Field(min_length=1, max_length=200)
    origin: Literal["suggested", "yours"]
    done: bool = False
    hidden: bool = False


class AskQuestion(APIModel):
    id: str = Field(max_length=40)
    text: str = Field(min_length=1, max_length=300)
    group: QuestionGroup = "other"
    origin: Literal["suggested", "yours"]
    excluded: bool = False
    note: str | None = Field(default=None, max_length=200, description="Why it was suggested, or a caution")


class KitUpdate(APIModel):
    """Replace whichever parts you send. Lists are saved in the order given (that's the priority)."""

    format: KitFormat | None = None
    location: str | None = Field(default=None, max_length=500)
    meeting_link: str | None = Field(default=None, max_length=500)
    clear_meeting_link: bool = False
    interviewers: list[Interviewer] | None = Field(default=None, max_length=10)
    notes: str | None = Field(default=None, max_length=4000)
    checklist: list[ChecklistItem] | None = Field(default=None, max_length=40)
    questions: list[AskQuestion] | None = Field(default=None, max_length=40)
    story_ids: list[str] | None = Field(default=None, max_length=10)

    @field_validator("meeting_link")
    @classmethod
    def _check_link(cls, v: str | None) -> str | None:
        return _http_link(v)


class KitStory(APIModel):
    id: str
    title: str
    short_version: str


class KitOut(APIModel):
    event_id: str
    application_id: str
    role_title: str
    employer: str
    event_title: str
    event_kind: str
    on_date: date | None
    local_time: str | None
    timezone: str | None
    starts_at: datetime | None
    format: KitFormat
    location: str
    meeting_link: str | None
    interviewers: list[Interviewer]
    notes: str
    checklist: list[ChecklistItem]
    questions: list[AskQuestion]
    stories: list[KitStory]
    target_title: str | None
    saved: bool = Field(description="False until you change something: the suggestions aren't stored yet")
