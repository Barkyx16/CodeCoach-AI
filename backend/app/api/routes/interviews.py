from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.models import User
from app.schemas.common import Page, error_responses
from app.schemas.interview import (
    InterviewFinish,
    InterviewMessage,
    InterviewOut,
    InterviewStart,
    InterviewSummary,
)
from app.services.interviews import InterviewService

router = APIRouter(prefix="/api/v1/interviews", tags=["interviews"])
_ERRORS = error_responses(400, 401, 404, 409, 422, 429)


def get_interviews(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> InterviewService:
    return InterviewService(db, settings, request.app.state.ai_provider)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Start a timed mock interview (one active interview per user)",
)
def start(
    body: InterviewStart,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
) -> InterviewOut:
    return svc.start(user, body)


@router.get("", response_model=Page[InterviewSummary], responses=_ERRORS, summary="Your interview history")
def list_interviews(
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[InterviewSummary]:
    return svc.list(user, page, page_size)


@router.get(
    "/{interview_id}",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Interview state, transcript and (when finished) evaluation",
)
def get_interview(
    interview_id: str, user: User = Depends(get_current_user), svc: InterviewService = Depends(get_interviews)
) -> InterviewOut:
    return svc.get(user, interview_id)


@router.post(
    "/{interview_id}/messages",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Send the candidate's answer (and current code); returns the interviewer's reply",
)
def respond(
    interview_id: str,
    body: InterviewMessage,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
) -> InterviewOut:
    return svc.respond(user, interview_id, body)


@router.post(
    "/{interview_id}/finish",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="End the interview and get rubric feedback (idempotent)",
)
def finish(
    interview_id: str,
    body: InterviewFinish | None = None,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
) -> InterviewOut:
    return svc.finish(user, interview_id, body)


@router.post(
    "/{interview_id}/abandon",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Stop early; still returns feedback for what was covered",
)
def abandon(
    interview_id: str, user: User = Depends(get_current_user), svc: InterviewService = Depends(get_interviews)
) -> InterviewOut:
    return svc.abandon(user, interview_id)
