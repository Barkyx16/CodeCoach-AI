"""Private offer comparisons: terms entered by hand, your own priorities, figures that show their working."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.offer_comparisons import (
    ComparisonDoc,
    DerivedOut,
    OfferComparisonCreate,
    OfferComparisonOut,
    OfferComparisonSave,
    OfferComparisonSummary,
)
from app.services.offer_comparisons import OfferComparisons

router = APIRouter(tags=["offer-comparisons"])
MINE = "/api/v1/me/offer-comparisons"


@router.get(
    MINE,
    response_model=list[OfferComparisonSummary],
    responses=error_responses(401),
    summary="Your comparisons",
)
def mine(
    archived: bool = Query(default=False, description="true: only archived comparisons (docs/ARCHIVE.md)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OfferComparisonSummary]:
    return OfferComparisons(db, user).mine(archived)


@router.post(
    MINE,
    response_model=OfferComparisonOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 422),
    summary="Start a comparison (empty, or a fictional example)",
)
def create(
    body: OfferComparisonCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OfferComparisonOut:
    return OfferComparisons(db, user).create(body)


@router.post(
    MINE + "/preview",
    response_model=DerivedOut,
    responses=error_responses(400, 401, 422),
    summary="The figures for an unsaved draft (nothing is stored)",
)
def preview(
    doc: ComparisonDoc, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DerivedOut:
    return OfferComparisons(db, user).preview(doc)


@router.get(
    MINE + "/{comparison_id}",
    response_model=OfferComparisonOut,
    responses=error_responses(401, 404),
    summary="A comparison",
)
def one(
    comparison_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OfferComparisonOut:
    return OfferComparisons(db, user).get(comparison_id)


@router.put(
    MINE + "/{comparison_id}",
    response_model=OfferComparisonOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Save against the revision you started from",
)
def save(
    comparison_id: str,
    body: OfferComparisonSave,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OfferComparisonOut:
    return OfferComparisons(db, user).save(comparison_id, body)


@router.delete(
    MINE + "/{comparison_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=error_responses(401, 404),
    summary="Delete a comparison",
)
def delete(
    comparison_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    OfferComparisons(db, user).delete(comparison_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    MINE + "/{comparison_id}/archive",
    response_model=OfferComparisonOut,
    responses=error_responses(401, 404),
    summary="Archive: out of the active list, nothing else changes",
)
def archive(
    comparison_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OfferComparisonOut:
    return OfferComparisons(db, user).set_archived(comparison_id, True)


@router.post(
    MINE + "/{comparison_id}/unarchive",
    response_model=OfferComparisonOut,
    responses=error_responses(401, 404),
    summary="Restore to the active list, unchanged",
)
def unarchive(
    comparison_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OfferComparisonOut:
    return OfferComparisons(db, user).set_archived(comparison_id, False)
