"""The interview-day kit for a recorded interview event."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.applications import _http_link
from app.schemas.common import APIModel, OptionalKey, SaveReplay, save_replay_field, update_key_field

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
    expected_revision: int | None = Field(
        default=None,
        ge=0,
        description="The kit revision you loaded (0 if it was never saved). If the kit was saved since, "
        "nothing is changed and the answer is 409 stale_revision with the current revision and the saved "
        "kit (details.current), so both can be shown.",
    )
    client_request_id: OptionalKey = update_key_field()
    reviewed_story_ids: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Chosen examples you've reread since they changed: their recorded version becomes the "
        "current one. Others keep the version they had when you chose them.",
    )

    @field_validator("meeting_link")
    @classmethod
    def _check_link(cls, v: str | None) -> str | None:
        return _http_link(v)


class KitStory(APIModel):
    """A chosen example, as it is now (it's a live reference, not a copy)."""

    id: str
    title: str
    short_version: str
    archived: bool = False
    revision: int = Field(default=1, description="The story's current version")
    chosen_revision: int | None = Field(
        default=None,
        description="The story's version when it was chosen for this kit (or last marked as reread); "
        "null if that wasn't recorded (kits saved before this existed)",
    )


class KitWhen(APIModel):
    on_date: date | None
    local_time: str | None
    timezone: str | None


class KitOut(APIModel):
    save_replay: SaveReplay | None = save_replay_field()
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
    revision: int = Field(
        default=0, description="Send it back as expected_revision when saving; 0 until saved"
    )
    rescheduled_from: KitWhen | None = Field(
        default=None,
        description="When the interview was the last time this kit was saved, if it has moved since. Null if "
        "it hasn't moved, or if that isn't known (kits saved before this was recorded).",
    )
    missing_stories: int = Field(
        default=0, description="Examples chosen for this kit that were deleted since (they aren't shown)"
    )
