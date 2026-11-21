"""Whether a piece of preparation is still based on its source as it is now (docs/STORY_FRESHNESS.md)."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

FreshnessState = Literal["current", "needs_review", "kept", "unknown", "unavailable"]


class FieldChange(APIModel):
    field: str = Field(description="Which part of the story, as the story page names it")
    before: str | None = Field(description="As prepared; null if that version isn't kept any more")
    after: str = Field(description="As it is now")


class LineageEntry(APIModel):
    decision: Literal["refreshed", "kept"]
    from_revision: int | None
    to_revision: int = Field(description="The revision the learner reviewed")
    at: datetime
    text: str


class Freshness(APIModel):
    state: FreshnessState = Field(
        description="current (nothing it relies on changed), needs_review, kept (the learner chose to keep "
        "it as prepared, until the story changes again), unknown (prepared before versions were "
        "recorded), unavailable (the story was deleted)"
    )
    text: str
    prepared_revision: int | None = Field(description="The story's version this was prepared from")
    current_revision: int | None = Field(description="The story's version now; null if it's gone")
    changes: list[FieldChange] = Field(
        default_factory=list, description="What changed that this relies on, earlier and now"
    )
    lineage: list[LineageEntry] = Field(
        default_factory=list, description="The learner's decisions about it, newest first"
    )


class SourceReviewIn(APIModel):
    reviewed_revision: int = Field(
        ge=1,
        description="The story's revision you reviewed. If it changed since, 409 source_changed and nothing "
        "changes: a newer revision is said, never used silently.",
    )
    decision: Literal["refresh", "keep"] = Field(
        description="refresh: use the reviewed revision from now on; keep: keep it as prepared (recorded; "
        "asked again only if the story changes again)"
    )
