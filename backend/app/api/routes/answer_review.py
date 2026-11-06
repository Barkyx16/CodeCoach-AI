"""How written answers are evaluated, and the learner's own reflection beside the result."""

from fastapi import APIRouter, Depends, Response
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.careers import CATALOG
from app.careers.questions import get_question
from app.errors import NotFoundError
from app.models import User
from app.schemas.answer_review import AnswerReviewOut, CriteriaOut, FlagIn, SelfReviewIn
from app.schemas.common import APIModel, error_responses
from app.services.answer_review import AnswerReview, criteria_for

router = APIRouter(prefix="/api/v1", tags=["careers"])


class ReevaluateIn(APIModel):
    reason: str = Field(default="", max_length=500, description="Why you'd like it checked again (private)")


@router.get(
    "/careers/{slug}/questions/{question_id}/criteria",
    response_model=CriteriaOut,
    responses=error_responses(404),
    summary="What the coach looks for in this question, before you answer",
)
def criteria(slug: str, question_id: str) -> CriteriaOut:
    q = get_question(slug, question_id) if slug in CATALOG else None
    if q is None:
        raise NotFoundError("Question not found")
    return criteria_for(q)


@router.get(
    "/me/answers/{answer_id}/review",
    response_model=AnswerReviewOut,
    responses=error_responses(401, 404),
    summary="Your answer, its feedback and your reflection",
)
def get_review(
    answer_id: str, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AnswerReviewOut:
    response.headers["Cache-Control"] = "no-store"
    return AnswerReview(db, user).review(answer_id)


@router.put(
    "/me/answers/{answer_id}/self-review",
    response_model=AnswerReviewOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Save (or skip) your own reflection; it never changes the answer or its result",
)
def put_self_review(
    answer_id: str, body: SelfReviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AnswerReviewOut:
    return AnswerReview(db, user).save_self_review(answer_id, body)


@router.post(
    "/me/answers/{answer_id}/flags",
    response_model=AnswerReviewOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Mark a criterion as unclear or one you disagree with, with a private note",
)
def add_flag(
    answer_id: str, body: FlagIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AnswerReviewOut:
    return AnswerReview(db, user).add_flag(answer_id, body)


@router.delete(
    "/me/answers/{answer_id}/flags/{flag_id}",
    response_model=AnswerReviewOut,
    responses=error_responses(401, 404),
    summary="Remove a flag",
)
def remove_flag(
    answer_id: str, flag_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AnswerReviewOut:
    return AnswerReview(db, user).remove_flag(answer_id, flag_id)


@router.post(
    "/me/answers/{answer_id}/evaluations",
    response_model=AnswerReviewOut,
    responses=error_responses(401, 404, 409, 422),
    summary="Check again under the current rubric (only when it could change; the original is kept)",
)
def reevaluate(
    answer_id: str, body: ReevaluateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AnswerReviewOut:
    return AnswerReview(db, user).reevaluate(answer_id, body.reason)
