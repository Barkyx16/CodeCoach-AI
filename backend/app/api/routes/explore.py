"""The practice explorer, bookmarks and private collections.

The public explorer (`/careers/{slug}/explore`) never includes anything about the caller, even
when a token is sent; personal status comes only from `/me/explore/{slug}`.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.explore import (
    BookmarkOut,
    CollectionBatchIn,
    CollectionBatchOut,
    CollectionIn,
    CollectionItemIn,
    CollectionOut,
    CollectionSummary,
    DoneIn,
    ExploreResult,
    ExploreSort,
    ExploreStatus,
    ItemType,
    MyExploreResult,
    OrderIn,
    QueueIn,
)
from app.services.explore import Explorer

router = APIRouter(prefix="/api/v1", tags=["explore"])

_DIFFICULTY = Query(default=None, pattern="^(easy|medium|hard)$")
_KIND = Query(default=None, pattern="^(knowledge|behavioral|situational|leadership|motivation)$")
_Q = Query(default=None, max_length=80, description="Keywords or a plain description")
_SKILL = Query(default=None, max_length=80)
_PAGE = Query(default=1, ge=1)
_PAGE_SIZE = Query(default=20, ge=1, le=100)


@router.get(
    "/careers/{slug}/explore",
    response_model=ExploreResult,
    responses=error_responses(404, 422),
    summary="Search and filter a career's questions, with counts per filter option (no personal data)",
)
def explore_public(
    slug: str,
    db: Session = Depends(get_db),
    q: str | None = _Q,
    difficulty: str | None = _DIFFICULTY,
    kind: str | None = _KIND,
    skill: str | None = _SKILL,
    sort: Literal["relevance", "library"] | None = Query(default=None),
    page: int = _PAGE,
    page_size: int = _PAGE_SIZE,
) -> ExploreResult:
    return Explorer(db).explore(
        None,
        slug,
        q=q,
        difficulty=difficulty,
        kind=kind,
        skill=skill,
        status=None,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/me/explore/{slug}",
    response_model=MyExploreResult,
    responses=error_responses(401, 404, 422),
    summary="The explorer with your practice status, bookmark/attempt filters and personal sorts",
)
def explore_mine(
    slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = _Q,
    difficulty: str | None = _DIFFICULTY,
    kind: str | None = _KIND,
    skill: str | None = _SKILL,
    status: ExploreStatus | None = Query(default=None),
    sort: ExploreSort | None = Query(default=None),
    page: int = _PAGE,
    page_size: int = _PAGE_SIZE,
) -> ExploreResult:
    return Explorer(db).explore(
        user,
        slug,
        q=q,
        difficulty=difficulty,
        kind=kind,
        skill=skill,
        status=status,
        sort=sort,
        page=page,
        page_size=page_size,
    )


# --- bookmarks ---------------------------------------------------------------------------------


@router.get(
    "/me/bookmarks",
    response_model=list[BookmarkOut],
    responses=error_responses(401),
    summary="Your bookmarks",
)
def list_bookmarks(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BookmarkOut]:
    return Explorer(db).bookmarks(user)


@router.put(
    "/me/bookmarks",
    response_model=list[BookmarkOut],
    responses=error_responses(401, 404, 422),
    summary="Bookmark a question or problem (idempotent)",
)
def add_bookmark(
    body: CollectionItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BookmarkOut]:
    return Explorer(db).set_bookmark(user, body, True)


@router.delete(
    "/me/bookmarks",
    response_model=list[BookmarkOut],
    responses=error_responses(401, 422),
    summary="Remove a bookmark (idempotent; works for items that left the library)",
)
def remove_bookmark(
    item_type: ItemType = Query(),
    ref_id: str = Query(min_length=1, max_length=80),
    track: str = Query(default="", max_length=64),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BookmarkOut]:
    body = CollectionItemIn(item_type=item_type, track=track, ref_id=ref_id)
    return Explorer(db).set_bookmark(user, body, False)


# --- collections -------------------------------------------------------------------------------


@router.get(
    "/me/collections",
    response_model=list[CollectionSummary],
    responses=error_responses(401),
    summary="Your private collections, most recently changed first",
)
def list_collections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    item_type: ItemType | None = Query(
        default=None, description="With ref_id: report which collections hold it"
    ),
    track: str = Query(default="", max_length=64),
    ref_id: str | None = Query(default=None, max_length=80),
) -> list[CollectionSummary]:
    item = CollectionItemIn(item_type=item_type, track=track, ref_id=ref_id) if item_type and ref_id else None
    return Explorer(db).collections(user, item)


@router.post(
    "/me/collections",
    response_model=CollectionOut,
    status_code=201,
    responses=error_responses(400, 401, 422),
    summary="Create a collection",
)
def create_collection(
    body: CollectionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CollectionOut:
    return Explorer(db).create(user, body.name)


@router.get(
    "/me/collections/{collection_id}",
    response_model=CollectionOut,
    responses=error_responses(401, 404),
    summary="A collection with its items in order",
)
def get_collection(
    collection_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CollectionOut:
    return Explorer(db).get(user, collection_id)


@router.patch(
    "/me/collections/{collection_id}",
    response_model=CollectionOut,
    responses=error_responses(401, 404, 422),
    summary="Rename a collection",
)
def rename_collection(
    collection_id: str,
    body: CollectionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    return Explorer(db).rename(user, collection_id, body.name)


@router.delete(
    "/me/collections/{collection_id}",
    status_code=204,
    responses=error_responses(401, 404),
    summary="Delete a collection (the questions and your answers are not affected)",
)
def delete_collection(
    collection_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    Explorer(db).delete(user, collection_id)
    return Response(status_code=204)


@router.post(
    "/me/collections/{collection_id}/items",
    response_model=CollectionOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Add a question or problem (409 if it's already in this collection)",
)
def add_collection_item(
    collection_id: str,
    body: CollectionItemIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    return Explorer(db).add_item(user, collection_id, body)


@router.post(
    "/me/collections/{collection_id}/items/batch",
    response_model=CollectionBatchOut,
    responses=error_responses(401, 404, 422),
    summary="Add several items, or remove several, with an outcome for each (docs/BULK_ACTIONS.md)",
)
def batch_collection_items(
    collection_id: str,
    body: CollectionBatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionBatchOut:
    return Explorer(db).batch(user, collection_id, body)


@router.delete(
    "/me/collections/{collection_id}/items/{item_id}",
    response_model=CollectionOut,
    responses=error_responses(401, 404),
    summary="Remove an item (also how a retired question is cleared out)",
)
def remove_collection_item(
    collection_id: str, item_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CollectionOut:
    return Explorer(db).remove_item(user, collection_id, item_id)


@router.put(
    "/me/collections/{collection_id}/order",
    response_model=CollectionOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Reorder: send every item id once, in the new order",
)
def reorder_collection(
    collection_id: str, body: OrderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CollectionOut:
    return Explorer(db).reorder(user, collection_id, body.item_ids)


@router.put(
    "/me/collections/{collection_id}/queue",
    response_model=CollectionOut,
    responses=error_responses(401, 404, 409, 422),
    summary="Start the collection as a practice queue, or move to a position in it",
)
def set_queue_position(
    collection_id: str, body: QueueIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CollectionOut:
    return Explorer(db).queue(user, collection_id, body.position)


@router.put(
    "/me/collections/{collection_id}/items/{item_id}/done",
    response_model=CollectionOut,
    responses=error_responses(401, 404, 422),
    summary="Mark an item done in this queue (queue progress only; mastery comes from your answers)",
)
def mark_item_done(
    collection_id: str,
    item_id: str,
    body: DoneIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    return Explorer(db).mark_done(user, collection_id, item_id, body.done)
