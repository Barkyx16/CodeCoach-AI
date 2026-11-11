"""Practice explorer (search, filters, sorts, counts), bookmarks and private collections."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import APIModel

ItemType = Literal["question", "problem", "drill"]
ExploreSort = Literal["relevance", "library", "last_practiced", "lowest_score"]
ExploreStatus = Literal["attempted", "unattempted", "bookmarked"]


class ExploreItem(APIModel):
    """Public description of a question: no personal data."""

    id: str
    title: str
    prompt: str
    difficulty: str
    kind: str
    skills: list[str]
    tags: list[str]
    estimated_minutes: int | None = Field(
        description="Null: the bank doesn't estimate this question's length"
    )


class ItemStatus(APIModel):
    """Private practice status for one question (signed-in explorer only)."""

    best_score: int | None = Field(description="Highest stored score, including answers too short to score")
    best_scored: int | None = Field(
        default=None, description="Best score among answers long enough to score; None when there's none"
    )
    score_status: Literal["scored", "too_short", "unknown"] | None = Field(
        default=None, description="None: not answered. Otherwise as in QuestionSummary.score_status"
    )
    attempts: int
    last_practiced_at: datetime | None
    bookmarked: bool
    collection_ids: list[str]


class Facet(APIModel):
    value: str
    label: str
    count: int


class ExploreFacets(APIModel):
    difficulty: list[Facet]
    kind: list[Facet]
    skill: list[Facet]


class ExploreResult(APIModel):
    track: str
    career_title: str
    items: list[ExploreItem]
    total: int
    page: int
    page_size: int
    facets: ExploreFacets = Field(description="Counts for each option, given the other active filters")
    explanation: list[str] = Field(description="The active filters, in words")
    suggestions: list[str] = Field(description="Ways to widen a search that found nothing")
    sorts: list[ExploreSort] = Field(description="Sorts available here (personal ones need sign-in)")


class MyExploreResult(ExploreResult):
    status: dict[str, ItemStatus] = Field(description="Your practice status, keyed by question id")


class BookmarkOut(APIModel):
    item_type: ItemType
    track: str
    ref_id: str
    title: str
    href: str | None
    available: bool
    unavailable_reason: str | None = Field(default=None, description="e.g. 'Retired: …' (still readable)")
    content_version: int | None = Field(default=None, description="Questions: the version when it was saved")
    created_at: datetime


class CollectionIn(APIModel):
    name: str = Field(min_length=1, max_length=80)


class CollectionItemIn(APIModel):
    item_type: ItemType
    track: str = Field(default="", max_length=64)
    ref_id: str = Field(min_length=1, max_length=80)


BATCH_LIMIT = 50


class CollectionBatchIn(APIModel):
    """Add several items to a collection, or remove several, in one request (docs/BULK_ACTIONS.md).
    Exactly one of `add` and `remove` is given."""

    add: list[CollectionItemIn] = Field(default_factory=list, max_length=BATCH_LIMIT)
    remove: list[str] = Field(
        default_factory=list, max_length=BATCH_LIMIT, description="Item ids of this collection"
    )

    @model_validator(mode="after")
    def _one_action(self) -> "CollectionBatchIn":
        if bool(self.add) == bool(self.remove):
            raise ValueError("Give either items to add or item ids to remove, not both or neither.")
        return self


BatchOutcome = Literal["added", "already_there", "unavailable", "full", "removed", "not_there", "repeated"]


class BatchResult(APIModel):
    key: str = Field(description="The item as sent: 'type:track:ref' for an add, the item id for a remove")
    outcome: BatchOutcome
    message: str


class CollectionBatchOut(APIModel):
    collection: "CollectionOut"
    results: list[BatchResult] = Field(description="One per item sent, in the order sent")


class OrderIn(APIModel):
    item_ids: list[str] = Field(
        max_length=200, description="Every item id of the collection, in the new order"
    )


class QueueIn(APIModel):
    position: int = Field(ge=0)


class DoneIn(APIModel):
    done: bool


class CollectionItemOut(APIModel):
    id: str
    item_type: ItemType
    track: str
    ref_id: str
    position: int
    title: str
    href: str | None
    available: bool
    unavailable_reason: str | None
    queue_done: bool = Field(description="Marked done in this collection's queue (not mastery)")
    practiced_since_added: bool = Field(description="An answer or submission exists since it was added")


class CollectionSummary(APIModel):
    id: str
    name: str
    items: int
    queue_position: int
    queue_started: bool
    updated_at: datetime
    contains: bool | None = Field(
        default=None, description="Whether it holds the item named in the request (null when none was named)"
    )


class CollectionOut(CollectionSummary):
    item_list: list[CollectionItemOut]
    queue_done: int
