"""Whiteboard practice: explain a design with a small, accessible diagram."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.whiteboard import (
    WhiteboardAttemptIn,
    WhiteboardAttemptOut,
    WhiteboardAttemptSummary,
    WhiteboardDraftIn,
    WhiteboardDraftOut,
    WhiteboardPromptList,
)
from app.services.whiteboard import Whiteboard
from app.whiteboard.diagram import WhiteboardDiagram

router = APIRouter(prefix="/api/v1/me/whiteboard", tags=["whiteboard"])


@router.get(
    "/prompts",
    response_model=WhiteboardPromptList,
    responses=error_responses(401),
    summary="Prompts for your career",
)
def prompts(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WhiteboardPromptList:
    return Whiteboard(db, user).prompts()


@router.post(
    "/validate",
    response_model=WhiteboardDiagram,
    responses=error_responses(401, 422),
    summary="Check a diagram file before it's loaded (nothing is saved)",
)
def validate(body: WhiteboardDiagram, user: User = Depends(get_current_user)) -> WhiteboardDiagram:
    # The schema is the check: unknown fields, bad ids, oversize text or lists, and non-plain
    # characters are refused with 422; what comes back is the cleaned diagram.
    return body


@router.get(
    "/{prompt_id}/draft",
    response_model=WhiteboardDraftOut,
    responses=error_responses(401, 404),
    summary="Your working diagram",
)
def get_draft(
    prompt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WhiteboardDraftOut:
    return Whiteboard(db, user).draft(prompt_id)


@router.put(
    "/{prompt_id}/draft",
    response_model=WhiteboardDraftOut,
    responses=error_responses(401, 404, 409, 422),
    summary="Save it (409 if it changed elsewhere)",
)
def put_draft(
    prompt_id: str,
    body: WhiteboardDraftIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WhiteboardDraftOut:
    return Whiteboard(db, user).save_draft(prompt_id, body)


@router.post(
    "/{prompt_id}/attempts",
    response_model=WhiteboardAttemptOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 422),
    summary="Freeze this diagram and get feedback (needs your explanation first)",
)
def attempt(
    prompt_id: str,
    body: WhiteboardAttemptIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WhiteboardAttemptOut:
    return Whiteboard(db, user).attempt(prompt_id, body)


@router.get(
    "/{prompt_id}/attempts",
    response_model=list[WhiteboardAttemptSummary],
    responses=error_responses(401, 404),
    summary="Your attempts",
)
def attempts(
    prompt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WhiteboardAttemptSummary]:
    return Whiteboard(db, user).attempts(prompt_id)


@router.get(
    "/attempts/{attempt_id}",
    response_model=WhiteboardAttemptOut,
    responses=error_responses(401, 404),
    summary="One attempt",
)
def get_attempt(
    attempt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WhiteboardAttemptOut:
    return Whiteboard(db, user).get_attempt(attempt_id)
