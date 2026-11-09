"""The story bank: a learner's own experiences, written in STAR form, for behavioral interviews."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey

Competency = Literal[
    "teamwork",
    "conflict",
    "leadership",
    "prioritization",
    "mistakes",
    "communication",
    "problem_solving",
    "adaptability",
    "care",
    "initiative",
]
StoryContext = Literal["work", "study", "volunteering", "personal", "other"]
Section = Literal["situation", "task", "action", "result", "reflection"]
SECTIONS: tuple[Section, ...] = ("situation", "task", "action", "result", "reflection")
# Situation, Task, Action and Result make a complete story; reflection is optional.
REQUIRED_SECTIONS: tuple[Section, ...] = ("situation", "task", "action", "result")

MAX_SECTION = 4000
MAX_VERSION = 3000


class StoryFields(APIModel):
    """Everything a learner writes. All optional on update; omitted fields are left alone."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    track: str | None = Field(default=None, max_length=64, description="Career context (a career slug)")
    context: StoryContext | None = None
    situation: str | None = Field(default=None, max_length=MAX_SECTION)
    task: str | None = Field(default=None, max_length=MAX_SECTION)
    action: str | None = Field(default=None, max_length=MAX_SECTION)
    result: str | None = Field(default=None, max_length=MAX_SECTION)
    reflection: str | None = Field(default=None, max_length=MAX_SECTION)
    notes: str | None = Field(default=None, max_length=MAX_SECTION, description="Private supporting notes")
    evidence: str | None = Field(
        default=None, max_length=2000, description="Optional evidence of the outcome"
    )
    competencies: list[Competency] | None = Field(default=None, max_length=10)
    tags: list[str] | None = Field(default=None, max_length=12)
    short_version: str | None = Field(default=None, max_length=MAX_VERSION)
    long_version: str | None = Field(default=None, max_length=MAX_VERSION)
    target_id: str | None = Field(default=None, max_length=36, description="Link to one of your job targets")
    question_refs: list[str] | None = Field(
        default=None, max_length=20, description="'track/question_id' links"
    )


class StoryCreate(StoryFields):
    title: str = Field(min_length=1, max_length=120)
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="One key per new story: sending the same create again (its response was lost) "
        "returns the story it made",
    )


class StoryUpdate(StoryFields):
    expected_revision: int = Field(ge=1, description="The revision you edited; a newer one is a 409")
    reason: Literal["edited", "assisted"] = "edited"
    clear_target: bool = False


class StoryQuestionLink(APIModel):
    ref: str
    title: str
    href: str
    available: bool


class StoryTargetLink(APIModel):
    id: str
    title: str


class StoryPractice(APIModel):
    answer_id: str
    question_title: str
    href: str
    score: int = Field(description="The stored score (capped when the answer was too short to score)")
    too_short: bool = Field(
        default=False, description="The answer was too short to score: `score` isn't a measurement"
    )
    created_at: datetime


class StorySummary(APIModel):
    id: str
    title: str
    track: str | None
    context: StoryContext | None
    competencies: list[Competency]
    tags: list[str]
    missing: list[Section] = Field(description="Required sections not written yet")
    target: StoryTargetLink | None
    revision: int
    archived: bool
    practice_count: int
    preview: str = Field(description="The start of the situation, for the list")
    updated_at: datetime


class StoryOut(StorySummary):
    situation: str
    task: str
    action: str
    result: str
    reflection: str
    notes: str
    evidence: str
    short_version: str
    long_version: str
    questions: list[StoryQuestionLink]
    practice: list[StoryPractice]
    privacy_hints: list[str] = Field(description="Possible identifying details, for the learner to review")
    created_at: datetime


class StoryRevisionOut(APIModel):
    revision: int
    reason: Literal["created", "edited", "assisted", "restored"]
    created_at: datetime
    fields: dict


class StoryRestoreIn(APIModel):
    expected_revision: int = Field(ge=1)


class StoryAssistIn(APIModel):
    action: Literal["check", "shorten", "clarity"]
    # The text in the editor right now (unsaved edits included); defaults to the saved story.
    situation: str | None = Field(default=None, max_length=MAX_SECTION)
    task: str | None = Field(default=None, max_length=MAX_SECTION)
    action_text: str | None = Field(default=None, max_length=MAX_SECTION)
    result: str | None = Field(default=None, max_length=MAX_SECTION)
    reflection: str | None = Field(default=None, max_length=MAX_SECTION)


class StoryProposal(APIModel):
    field: Section
    original: str
    proposed: str
    changes: list[str] = Field(description="What the proposal changes, in plain words")


class StoryAssistOut(APIModel):
    action: Literal["check", "shorten", "clarity"]
    method: str = Field(description="How the suggestions were made")
    proposals: list[StoryProposal] = Field(
        description="Edits to review; nothing is changed until you accept one"
    )
    questions: list[str] = Field(description="Things only you can answer; nothing is guessed for you")
