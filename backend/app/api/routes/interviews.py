from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.models import User
from app.schemas.common import Page, error_responses
from app.schemas.interview import (
    FollowupAnswer,
    FormatOption,
    InterviewFinish,
    InterviewMessage,
    InterviewOut,
    InterviewStart,
    InterviewSummary,
    RoundAnswer,
    RoundSkip,
)
from app.schemas.review import Comparison, InterviewReview, RetryIn
from app.services.interviews import InterviewService, format_options
from app.services.review import InterviewReviews

router = APIRouter(prefix="/api/v1/interviews", tags=["interviews"])
_ERRORS = error_responses(400, 401, 404, 409, 422, 429)


def get_interviews(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> InterviewService:
    return InterviewService(
        db, settings, request.app.state.ai_provider, getattr(request.app.state, "practice_limiter", None)
    )


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


@router.get(
    "/formats",
    response_model=list[FormatOption],
    responses=error_responses(404, 422),
    summary="Question-round formats for a career and level: which are available, and their structure",
)
def list_formats(
    track: str = Query(default="software-engineer", max_length=64),
    difficulty: Literal["easy", "medium", "hard"] = Query(default="easy"),
) -> list[FormatOption]:
    return format_options(track, difficulty)


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
    "/{interview_id}/answers",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Question rounds: answer the current question (idempotent per question)",
)
def answer_question(
    interview_id: str,
    body: RoundAnswer,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
) -> InterviewOut:
    return svc.answer_question(user, interview_id, body)


@router.post(
    "/{interview_id}/skip",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Question rounds: skip the current question (idempotent per question)",
)
def skip_question(
    interview_id: str,
    body: RoundSkip,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
) -> InterviewOut:
    return svc.skip_question(user, interview_id, body)


@router.post(
    "/{interview_id}/followup",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Question rounds: answer the pending follow-up (then the next question is asked)",
)
def answer_followup(
    interview_id: str,
    body: FollowupAnswer,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
) -> InterviewOut:
    return svc.followup(user, interview_id, body)


@router.post(
    "/{interview_id}/followup/skip",
    response_model=InterviewOut,
    responses=_ERRORS,
    summary="Question rounds: skip the pending follow-up",
)
def skip_followup(
    interview_id: str,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
) -> InterviewOut:
    return svc.followup(user, interview_id, None)


@router.get(
    "/{interview_id}/review",
    response_model=InterviewReview,
    responses=_ERRORS,
    summary="Structured review of a finished interview: timeline, feedback dimensions, improvements",
)
def review(
    interview_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
    db: Session = Depends(get_db),
) -> InterviewReview:
    return InterviewReviews(db, getattr(request.app.state, "practice_limiter", None)).build(
        user, svc.load(user, interview_id)
    )


@router.post(
    "/{interview_id}/questions/{index}/retries",
    response_model=Comparison,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Retry one question of a finished round; the original answer is kept and compared",
)
def retry_question(
    interview_id: str,
    index: int,
    body: RetryIn,
    request: Request,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
    db: Session = Depends(get_db),
) -> Comparison:
    session = svc.load(user, interview_id)
    return InterviewReviews(db, getattr(request.app.state, "practice_limiter", None)).retry(
        user, session, index, body
    )


@router.get(
    "/{interview_id}/questions/{index}/comparison",
    response_model=Comparison,
    responses=_ERRORS,
    summary="The original answer to a question next to its retries",
)
def compare_question(
    interview_id: str,
    index: int,
    user: User = Depends(get_current_user),
    svc: InterviewService = Depends(get_interviews),
    db: Session = Depends(get_db),
) -> Comparison:
    return InterviewReviews(db).compare(svc.load(user, interview_id), index)


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
