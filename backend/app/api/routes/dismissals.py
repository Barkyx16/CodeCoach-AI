"""Suggestions dismissed with "Not now", kept with the account so every device respects them, and
offered again from Settings (Volume 15, prompt 2; docs/FOLLOW_UPS.md, "Not now")."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.dismissals import DismissBatch, Dismissed, DismissedList
from app.services.dismissals import Dismissals

router = APIRouter(prefix="/api/v1/me/dismissals", tags=["dismissals"])


@router.get(
    "",
    response_model=DismissedList,
    responses=error_responses(401),
    summary="What you said “Not now” to, newest first, each in plain words",
)
def list_dismissals(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DismissedList:
    return DismissedList(items=[Dismissed(**d) for d in Dismissals(db, user).listed()])


@router.post(
    "",
    response_model=DismissedList,
    responses=error_responses(400, 401, 422),
    summary="Dismiss suggestions (the same one twice is one record); returns the whole list",
)
def dismiss(
    body: DismissBatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DismissedList:
    store = Dismissals(db, user)
    for item in body.items:
        store.add(item.key, item.offered_on)
    return DismissedList(items=[Dismissed(**d) for d in store.listed()])


@router.delete(
    "",
    status_code=204,
    responses=error_responses(401, 404),
    summary="Offer a dismissed suggestion again (it then follows its own rules)",
)
def offer_again(
    key: str = Query(min_length=1, max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    Dismissals(db, user).remove(key)
    return Response(status_code=204)
