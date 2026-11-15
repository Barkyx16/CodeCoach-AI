"""The personal practice notebook."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey, SaveReplay, save_replay_field, update_key_field
from app.schemas.freshness import FieldChange

SourceType = Literal["question", "problem", "lesson", "interview"]
NoteStatus = Literal["active", "archived", "all"]

MAX_TITLE = 200
MAX_BODY = 20_000
MAX_REFLECTION = 5_000
MAX_EXCERPT = 4_000
MAX_TAGS = 12
MAX_TAG = 32


class SourceIn(APIModel):
    type: SourceType
    id: str = Field(
        min_length=1, max_length=120, description="Question id, problem slug, unit id or interview id"
    )
    track: str | None = Field(default=None, max_length=64, description="Career, for questions")
    question_index: int | None = Field(default=None, ge=0, le=20, description="Interviews: which question")


class NoteIn(APIModel):
    title: str = Field(default="", max_length=MAX_TITLE)
    body: str = Field(default="", max_length=MAX_BODY, description="Plain text or Markdown (rendered safely)")
    reflection: str = Field(default="", max_length=MAX_REFLECTION)
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)
    source: SourceIn | None = None
    excerpt: str | None = Field(
        default=None, max_length=MAX_EXCERPT, description="A snapshot, not a live reference"
    )
    excerpt_kind: Literal["quote", "code"] | None = None
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="One key per new note: sending the same create again returns the note it made",
    )
    copy_of: str | None = Field(
        default=None,
        max_length=36,
        description="Keep both after a conflict (Volume 8, prompt 4): the note this is a copy of. Requires "
        "`client_request_id` (one per decision). The same key returns the copy it made; a copy made and "
        "then deleted is 410 `copy_deleted`, not made again. The question or problem your own note is "
        "about comes along; another account's note id is treated as missing. The source isn't changed.",
    )


class NotePatch(APIModel):
    base_revision: int | None = Field(
        default=None, ge=1, description="Required when changing text: the revision this edit started from"
    )
    client_request_id: OptionalKey = update_key_field()
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    body: str | None = Field(default=None, max_length=MAX_BODY)
    reflection: str | None = Field(default=None, max_length=MAX_REFLECTION)
    tags: list[str] | None = Field(default=None, max_length=MAX_TAGS)
    key_points: list[str] | None = Field(
        default=None, max_length=12, description="Accepted key points; [] clears"
    )
    pinned: bool | None = None
    archived: bool | None = None


class SourceOut(APIModel):
    type: SourceType
    id: str
    track: str | None
    version: str | None
    title: str | None = Field(description="The source's title when the note was captured")
    href: str | None
    available: bool = Field(description="False when the source left the library; the note is kept")
    career_title: str | None


class NoteReview(APIModel):
    from_version: int | None = Field(description="The version you'd seen before (captured or last reviewed)")
    to_version: int = Field(description="The version you were shown when you marked it reviewed")
    at: datetime
    text: str


class NoteFreshness(APIModel):
    """Whether the note's source changed since it was captured (docs/STORY_FRESHNESS.md, "Notes").
    The note itself never changes."""

    state: Literal["current", "needs_review", "unknown", "retired", "unavailable"] = Field(
        description="current (nothing to review), needs_review (a newer version that matters), unknown "
        "(captured before versions were recorded), retired, unavailable (it left the library)"
    )
    text: str
    kind: Literal["question", "lesson", "problem"]
    captured_version: int | None = Field(description="The source's version when the note was captured")
    reviewed_version: int | None = Field(description="The latest version you marked reviewed")
    current_version: int | None
    changes: list[FieldChange] = Field(
        default_factory=list, description="What changed, as captured and now (questions keep both)"
    )
    change_notes: list[str] = Field(
        default_factory=list, description="What the content says changed in each newer version"
    )
    comparable: bool = Field(
        default=False, description="The content keeps its earlier wording, so the change can be shown"
    )
    reviews: list[NoteReview] = Field(default_factory=list, description="Your reviews, newest first")


class NoteSourceReviewIn(APIModel):
    reviewed_version: int = Field(
        ge=1,
        description="The source's version you were shown. A newer one since isn't reviewed silently: the "
        "notice stays for it.",
    )


class NoteSummary(APIModel):
    id: str
    title: str
    snippet: str
    tags: list[str]
    source: SourceOut | None
    pinned: bool
    archived: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    source_updated: bool = Field(
        default=False, description="Its source has a newer version that matters, not yet reviewed"
    )


class NoteOut(NoteSummary):
    save_replay: SaveReplay | None = save_replay_field()
    freshness: NoteFreshness | None = Field(
        default=None, description="Its source's version now, against the one captured (versioned sources)"
    )
    body: str
    reflection: str
    excerpt: str | None
    excerpt_kind: Literal["quote", "code"] | None
    key_points: list[str] | None


class TagCount(APIModel):
    tag: str
    count: int


class NotePage(APIModel):
    items: list[NoteSummary]
    total: int
    page: int
    page_size: int
    tags: list[TagCount]
    careers: list[TagCount] = Field(description="Careers your notes come from, with counts")
    pinned_limit: int


class DeletedOut(APIModel):
    id: str
    restorable_until: datetime


class KeyPoints(APIModel):
    points: list[str]
    method: str = Field(description="How the points were found (no AI model is used)")
