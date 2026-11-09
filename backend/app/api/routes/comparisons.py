"""Comparing authored sample answers: mark excerpts with reasons, then reveal the explanation."""

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.comparisons import (
    ComparisonAttemptIn,
    ComparisonAttemptOut,
    ComparisonAttemptSummary,
    ComparisonLesson,
    ComparisonSummary,
)
from app.services.comparisons import Comparisons

router = APIRouter(tags=["comparisons"])
PUBLIC = "/api/v1/comparisons"
MINE = "/api/v1/me/comparisons"


@router.get(PUBLIC, response_model=list[ComparisonSummary], summary="Sample-answer comparison lessons")
def lessons() -> list[ComparisonSummary]:
    return Comparisons.lessons()


@router.get(
    PUBLIC + "/{lesson_id}",
    response_model=ComparisonLesson,
    responses=error_responses(404),
    summary="One lesson: the question, rubric and samples (not the explanation)",
)
def lesson(lesson_id: str) -> ComparisonLesson:
    return Comparisons.lesson(lesson_id)


@router.get(
    PUBLIC + "/{lesson_id}/explanation",
    response_model=dict[str, Any],
    responses=error_responses(404),
    summary="The authored explanation (a deliberate reveal)",
)
def explanation(lesson_id: str) -> dict[str, Any]:
    return Comparisons.explanation(lesson_id)


@router.post(
    MINE + "/{lesson_id}/attempts",
    response_model=ComparisonAttemptOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 422),
    summary="Send your reading and compare it with the explanation",
)
def attempt(
    lesson_id: str,
    body: ComparisonAttemptIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComparisonAttemptOut:
    return Comparisons(db, user).attempt(lesson_id, body)


@router.get(
    MINE + "/{lesson_id}/attempts",
    response_model=list[ComparisonAttemptSummary],
    responses=error_responses(401, 404),
    summary="Your readings of this lesson",
)
def attempts(
    lesson_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ComparisonAttemptSummary]:
    return Comparisons(db, user).attempts(lesson_id)


@router.get(
    MINE + "/attempts/{attempt_id}",
    response_model=ComparisonAttemptOut,
    responses=error_responses(401, 404),
    summary="One reading, with the samples and explanation as they were",
)
def get_attempt(
    attempt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ComparisonAttemptOut:
    return Comparisons(db, user).get_attempt(attempt_id)
