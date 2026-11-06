"""The personal practice notebook."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

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


class NotePatch(APIModel):
    base_revision: int | None = Field(
        default=None, ge=1, description="Required when changing text: the revision this edit started from"
    )
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


class NoteOut(NoteSummary):
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
