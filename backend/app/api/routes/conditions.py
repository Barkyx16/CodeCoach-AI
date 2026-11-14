"""The conditions of several attempts at once (docs/ATTEMPT_CONDITIONS.md), for lists such as
History: one bounded request for the rows on screen, whatever the history's size."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import PracticeAnswer, Submission, User
from app.schemas.common import error_responses
from app.schemas.conditions import ConditionsOut, ConditionsQuery
from app.services.conditions import Conditions

router = APIRouter(prefix="/api/v1", tags=["progress"])


@router.post(
    "/me/attempt-conditions",
    response_model=ConditionsOut,
    responses=error_responses(401, 422),
    summary="The in-app help shown before each of these attempts (yours only)",
)
def attempt_conditions(
    body: ConditionsQuery, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ConditionsOut:
    finder = Conditions(db, user)
    subs = (
        db.scalars(
            select(Submission).where(
                Submission.user_id == user.id, Submission.id.in_(set(body.submission_ids))
            )
        ).all()
        if body.submission_ids
        else []
    )
    answers = (
        db.scalars(
            select(PracticeAnswer).where(
                PracticeAnswer.user_id == user.id, PracticeAnswer.id.in_(set(body.answer_ids))
            )
        ).all()
        if body.answer_ids
        else []
    )
    return ConditionsOut(submissions=finder.for_submissions(subs), answers=finder.for_answers(answers))
