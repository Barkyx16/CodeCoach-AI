"""Improvements you accepted: one action each, shown by the plan, the schedule and a kit (docs/ACCEPTED_ACTIONS.md)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.actions import ActionAccept, ActionOut, ActionUpdate, OccurrencesIn
from app.schemas.common import error_responses
from app.services.actions import Actions

router = APIRouter(prefix="/api/v1/me/actions", tags=["actions"])


@router.get(
    "", response_model=list[ActionOut], responses=error_responses(401), summary="Improvements you accepted"
)
def mine(
    state: Literal["open", "done", "all"] = Query(default="all"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActionOut]:
    return Actions(db, user).mine(state)


@router.post(
    "",
    response_model=ActionOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404, 409, 422),
    summary="Accept a suggested improvement (accepting it again returns the same action, 200)",
)
def accept(
    body: ActionAccept,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActionOut:
    out, created = Actions(db, user).accept(body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return out


@router.get(
    "/{action_id}", response_model=ActionOut, responses=error_responses(401, 404), summary="One action"
)
def get(action_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ActionOut:
    return Actions(db, user).get(action_id)


@router.patch(
    "/{action_id}",
    response_model=ActionOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Rename it or change its notes (409 stale_revision with the saved action if it changed since)",
)
def update(
    action_id: str, body: ActionUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionOut:
    return Actions(db, user).update(action_id, body)


@router.post(
    "/{action_id}/complete",
    response_model=ActionOut,
    responses=error_responses(401, 404, 409),
    summary="Say a one-off action is done (changes no score)",
)
def complete(
    action_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionOut:
    return Actions(db, user).complete(action_id)


@router.post(
    "/{action_id}/reopen",
    response_model=ActionOut,
    responses=error_responses(401, 404, 409),
    summary="Undo: a one-off action is open again",
)
def reopen(
    action_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionOut:
    return Actions(db, user).reopen(action_id)


@router.post(
    "/{action_id}/occurrences",
    response_model=ActionOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Put it on the schedule: once, or weekly for a number of weeks",
)
def schedule(
    action_id: str, body: OccurrencesIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionOut:
    return Actions(db, user).schedule(action_id, body)


@router.post(
    "/{action_id}/occurrences/{entry_id}/complete",
    response_model=ActionOut,
    responses=error_responses(401, 404, 409),
    summary="Say one occurrence is done (a weekly action's others stay open)",
)
def complete_occurrence(
    action_id: str, entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionOut:
    return Actions(db, user).complete_occurrence(action_id, entry_id, True)


@router.post(
    "/{action_id}/occurrences/{entry_id}/reopen",
    response_model=ActionOut,
    responses=error_responses(401, 404, 409),
    summary="Undo one occurrence's completion",
)
def reopen_occurrence(
    action_id: str, entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionOut:
    return Actions(db, user).complete_occurrence(action_id, entry_id, False)
