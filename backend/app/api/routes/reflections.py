"""Private reflections on real interviews you recorded on an application."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.reflections import (
    Outcome,
    ReflectionActionAccept,
    ReflectionActionEdit,
    ReflectionIn,
    ReflectionOut,
    ReflectionOutcomeIn,
    ReflectionSummary,
)
from app.services.reflections import Reflections

router = APIRouter(prefix="/api/v1/me", tags=["applications"])
BASE = "/applications/{app_id}/events/{event_id}/reflection"


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get(
    "/reflections",
    response_model=list[ReflectionSummary],
    responses=error_responses(401),
    summary="Search your reflections",
)
def search(
    response: Response,
    q: str = Query(default="", max_length=200),
    outcome: Outcome | None = None,
    include_archived: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReflectionSummary]:
    _private(response)
    return Reflections(db, user).all(q, outcome, include_archived)


@router.get(
    BASE,
    response_model=ReflectionOut,
    responses=error_responses(401, 404),
    summary="Your reflection on this interview",
)
def get_reflection(
    app_id: str,
    event_id: str,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReflectionOut:
    _private(response)
    return Reflections(db, user).get(app_id, event_id)


@router.put(
    BASE,
    response_model=ReflectionOut,
    responses=error_responses(401, 404, 409, 422),
    summary="Save it (every part is optional)",
)
def put_reflection(
    app_id: str,
    event_id: str,
    body: ReflectionIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReflectionOut:
    _private(response)
    return Reflections(db, user).save(app_id, event_id, body)


@router.post(
    f"{BASE}/suggestions",
    response_model=ReflectionOut,
    responses=error_responses(400, 401, 404),
    summary="Suggest next steps from what you wrote (nothing is applied)",
)
def suggest(
    app_id: str,
    event_id: str,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReflectionOut:
    _private(response)
    return Reflections(db, user).suggest(app_id, event_id)


@router.patch(
    f"{BASE}/actions/{{action_id}}",
    response_model=ReflectionOut,
    responses=error_responses(401, 404, 409, 422),
    summary="Edit or dismiss a suggestion",
)
def edit_action(
    app_id: str,
    event_id: str,
    action_id: str,
    body: ReflectionActionEdit,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReflectionOut:
    _private(response)
    return Reflections(db, user).edit_action(app_id, event_id, action_id, body)


@router.post(
    f"{BASE}/actions/{{action_id}}/accept",
    response_model=ReflectionOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Add a step to your notebook, schedule or Saved (again: no duplicate)",
)
def accept_action(
    app_id: str,
    event_id: str,
    action_id: str,
    body: ReflectionActionAccept,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReflectionOut:
    _private(response)
    return Reflections(db, user).accept(app_id, event_id, action_id, body)


@router.put(
    f"{BASE}/outcome",
    response_model=ReflectionOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Record what happened; the application changes only if you ask",
)
def set_outcome(
    app_id: str,
    event_id: str,
    body: ReflectionOutcomeIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReflectionOut:
    _private(response)
    return Reflections(db, user).set_outcome(app_id, event_id, body)
