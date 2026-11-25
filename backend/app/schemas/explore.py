"""Practice explorer (search, filters, sorts, counts), bookmarks and private collections."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import APIModel
from app.schemas.notes import NoteFreshness

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
    id: str
    item_type: ItemType
    track: str
    ref_id: str
    title: str
    href: str | None
    available: bool
    unavailable_reason: str | None = Field(default=None, description="e.g. 'Retired: …' (still readable)")
    content_version: int | None = Field(
        default=None,
        description="The question's or problem's version when it was saved; null: saved before versions "
        "were recorded (not known), or a drill (no versions)",
    )
    freshness: NoteFreshness | None = Field(
        default=None,
        description="Whether the source changed in a way that matters since it was saved, by the same rule "
        "as notes (docs/STORY_FRESHNESS.md); null for a drill",
    )
    created_at: datetime


class SavedReviewIn(APIModel):
    item_type: ItemType
    track: str = Field(default="", max_length=64)
    ref_id: str = Field(min_length=1, max_length=80)
    reviewed_version: int = Field(
        ge=1,
        description="The source's version you were shown. A newer one since isn't reviewed silently: the "
        "badge stays for it.",
    )


class CollectionIn(APIModel):
    name: str = Field(min_length=1, max_length=80)


class CollectionDuplicateIn(APIModel):
    """Duplicate a collection (Volume 16, prompt 8; docs/BULK_ACTIONS.md, "Duplicate a collection")."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        description="The copy's name; default: the original's with “ (copy)”, numbered when that's taken",
    )
    client_request_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="A key for this request: sent again (a retry after a lost reply), it returns the copy it "
        "made, not another",
    )


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


class CollectionTransferIn(APIModel):
    """Copy or move chosen items to another of your collections (Volume 17, prompt 6;
    docs/BULK_ACTIONS.md, "Copy or move items"). Items are named by what they are, not by row, so the
    same request sent again after a lost reply changes nothing twice."""

    to: str = Field(description="The collection they go to (yours, and not this one)")
    items: list[CollectionItemIn] = Field(min_length=1, max_length=BATCH_LIMIT)
    move: bool = Field(
        default=False, description="Take them out of this collection once they're in the other"
    )
    client_request_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="A key for this request (Volume 18, prompt 5): sent again after a lost reply, it gets the "
        "first reply's outcomes back exactly, with both collections as they are now",
    )


TransferOutcome = Literal["copied", "moved", "already_there", "not_there", "full", "repeated"]


class TransferResult(APIModel):
    key: str = Field(description="The item as sent: 'type:track:ref'")
    outcome: TransferOutcome
    message: str


class CollectionTransferOut(APIModel):
    source: "CollectionOut"
    destination: "CollectionOut"
    results: list[TransferResult] = Field(description="One per item sent, in the order sent")
    replayed: bool = Field(
        default=False,
        description="This request was sent before with this key: these are its first reply's outcomes, as they "
        "were then (the collections are as they are now)",
    )


ReviewOutcome = Literal[
    "reviewed", "already_reviewed", "newer_since", "not_versioned", "unavailable", "invalid_version",
    "not_there", "repeated",
]  # fmt: skip


class SavedReviewBatchIn(APIModel):
    """Mark several saved items reviewed, each at the version it was shown (docs/BULK_ACTIONS.md)."""

    items: list[SavedReviewIn] = Field(min_length=1, max_length=BATCH_LIMIT)


class ItemReviewIn(APIModel):
    item_id: str = Field(min_length=1, max_length=36)
    reviewed_version: int = Field(ge=1, description="The source's version you were shown")


class CollectionReviewBatchIn(APIModel):
    """Mark several items of a collection reviewed, each at the version it was shown."""

    items: list[ItemReviewIn] = Field(min_length=1, max_length=BATCH_LIMIT)


class ReviewResult(APIModel):
    key: str = Field(
        description="The item as sent: 'type:track:ref' for a saved item, the item id in a collection"
    )
    outcome: ReviewOutcome
    message: str


class SavedReviewBatchOut(APIModel):
    bookmarks: list[BookmarkOut]
    results: list[ReviewResult] = Field(description="One per item sent, in the order sent")


class CollectionReviewBatchOut(APIModel):
    collection: "CollectionOut"
    results: list[ReviewResult] = Field(description="One per item sent, in the order sent")


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
    content_version: int | None = Field(
        default=None, description="The source's version when it was added; null: not known, or a drill"
    )
    freshness: NoteFreshness | None = Field(
        default=None,
        description="Whether its source changed since it was added (the notes' rule); null for a drill",
    )


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
    copied_from_id: str | None = Field(
        default=None,
        description="The collection this one was duplicated from (it may have been deleted since)",
    )
