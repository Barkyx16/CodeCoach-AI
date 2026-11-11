from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel
from app.services.workspace_search import FIELDS, KINDS, MAX_LIMIT, MAX_QUERY, words_of

SearchKind = Literal["notes", "stories", "kits", "applications"]
_ALL: list[SearchKind] = ["notes", "stories", "kits", "applications"]
assert tuple(_ALL) == KINDS

_FIELDS_DOC = "; ".join(f"{k}: {', '.join(v)}" for k, v in FIELDS.items())


class WorkspaceSearchIn(APIModel):
    q: str = Field(min_length=1, max_length=MAX_QUERY, description="Words to find; every word must appear")
    kinds: list[SearchKind] = Field(
        default_factory=lambda: list(_ALL), min_length=1, max_length=len(KINDS), description=_FIELDS_DOC
    )
    include_archived: bool = Field(
        default=False, description="Also search archived notes, stories and applications"
    )
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT)

    @field_validator("q")
    @classmethod
    def _enough(cls, v: str) -> str:
        if len("".join(words_of(v))) < 2:
            raise ValueError("Type at least 2 characters to search.")
        return v


class WorkspaceHit(APIModel):
    type: Literal["note", "story", "kit", "application"]
    id: str = Field(description="The record's id; for a kit, its event's id")
    parent_id: str | None = Field(default=None, description="For a kit: its application's id")
    title: str
    snippet: str | None = Field(
        default=None,
        description="Plain text around the first word found (or the start of the text): show as text",
    )
    matched: list[str] = Field(description="Where the words were found: title, text, tags, ...")
    state: Literal["archived", "pinned"] | None = None
    detail: str | None = Field(default=None, description="An application's stage; a kit's employer and date")
    tags: list[str] = Field(default_factory=list)
    at: datetime = Field(description="When it was last saved to your account")


class WorkspaceSearchOut(APIModel):
    items: list[WorkspaceHit]
    counts: dict[str, int] = Field(description="Matches of each kind searched, among your own records")
    capped: list[str] = Field(description="Kinds with more candidates than were looked at; refine the words")
    unavailable: list[str] = Field(description="Kinds that couldn't be searched just now; the rest were")
    words: list[str] = Field(description="The words matched, as folded for matching (for highlighting)")
