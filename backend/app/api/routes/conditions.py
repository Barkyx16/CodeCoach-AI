"""The conditions of several attempts at once (docs/ATTEMPT_CONDITIONS.md), for lists such as
History: one bounded request for the rows on screen, whatever the history's size."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import (
    CodeReviewAttempt,
    ComparisonAttempt,
    DrillAttempt,
    PracticeAnswer,
    PracticeSession,
    ScenarioAttempt,
    Submission,
    TestDesignRun,
    User,
    WhiteboardAttempt,
    WorkSampleAttempt,
)
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

    def mine(model, ids: list[str]) -> list:
        if not ids:
            return []
        return list(db.scalars(select(model).where(model.user_id == user.id, model.id.in_(set(ids)))).all())

    return ConditionsOut(
        submissions=finder.for_submissions(subs),
        answers=finder.for_answers(answers),
        drill_attempts=finder.for_drills(mine(DrillAttempt, body.drill_attempt_ids)),
        scenario_attempts=finder.for_scenarios(mine(ScenarioAttempt, body.scenario_attempt_ids)),
        whiteboard_attempts=finder.for_whiteboards(mine(WhiteboardAttempt, body.whiteboard_attempt_ids)),
        code_review_attempts=finder.for_code_reviews(mine(CodeReviewAttempt, body.code_review_attempt_ids)),
        comparison_attempts=finder.for_comparisons(mine(ComparisonAttempt, body.comparison_attempt_ids)),
        work_sample_attempts=finder.for_work_samples(mine(WorkSampleAttempt, body.work_sample_attempt_ids)),
        test_design_runs=finder.for_test_design_runs(mine(TestDesignRun, body.test_design_run_ids)),
        # Coding interviews only (a career interview's answers have their own), once they're over.
        interviews=finder.for_interviews(mine(PracticeSession, body.interview_ids)),
    )
