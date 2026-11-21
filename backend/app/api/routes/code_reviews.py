"""Code-review practice: review someone else's code, then compare with an authored review."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.code_reviews import (
    ReviewAttemptIn,
    ReviewAttemptOut,
    ReviewAttemptSummary,
    ReviewDraftIn,
    ReviewDraftOut,
    ReviewExerciseOut,
    ReviewExerciseSummary,
    ReviewReference,
)
from app.schemas.common import error_responses
from app.services.code_reviews import CodeReviews

router = APIRouter(tags=["code reviews"])
PUBLIC = "/api/v1/code-reviews"
MINE = "/api/v1/me/code-reviews"


@router.get(PUBLIC, response_model=list[ReviewExerciseSummary], summary="Code-review exercises")
def exercises(db: Session = Depends(get_db)) -> list[ReviewExerciseSummary]:
    return CodeReviews(db).exercises()


@router.get(
    PUBLIC + "/{slug}",
    response_model=ReviewExerciseOut,
    responses=error_responses(404),
    summary="One exercise: the code and the task, without the authored review",
)
def exercise(slug: str, db: Session = Depends(get_db)) -> ReviewExerciseOut:
    return CodeReviews(db).exercise(slug)


@router.get(
    MINE + "/{slug}/draft",
    response_model=ReviewDraftOut,
    responses=error_responses(401, 404),
    summary="Your review so far",
)
def get_draft(
    slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewDraftOut:
    return CodeReviews(db, user).draft(slug)


@router.put(
    MINE + "/{slug}/draft",
    response_model=ReviewDraftOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Save it (409 if it changed elsewhere)",
)
def put_draft(
    slug: str, body: ReviewDraftIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewDraftOut:
    return CodeReviews(db, user).save_draft(slug, body)


@router.post(
    MINE + "/{slug}/reveal",
    response_model=ReviewReference,
    responses=error_responses(401, 404),
    summary="Show the authored review (later reviews of this version say they came after it)",
)
def reveal(
    slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewReference:
    return CodeReviews(db, user).reveal(slug)


@router.post(
    MINE + "/{slug}/attempts",
    response_model=ReviewAttemptOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 422),
    summary="Send your review and compare it with the authored one",
)
def attempt(
    slug: str, body: ReviewAttemptIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewAttemptOut:
    return CodeReviews(db, user).attempt(slug, body)


@router.get(
    MINE + "/{slug}/attempts",
    response_model=list[ReviewAttemptSummary],
    responses=error_responses(401, 404),
    summary="Your reviews of this exercise",
)
def attempts(
    slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ReviewAttemptSummary]:
    return CodeReviews(db, user).attempts(slug)


@router.get(
    MINE + "/attempts/{attempt_id}",
    response_model=ReviewAttemptOut,
    responses=error_responses(401, 404),
    summary="One of your reviews, with the version it was compared against",
)
def get_attempt(
    attempt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewAttemptOut:
    return CodeReviews(db, user).get_attempt(attempt_id)
