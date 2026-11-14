"""Work-sample practice: write a short professional artifact from a fictional brief."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.work_samples import (
    WorkSampleAttemptIn,
    WorkSampleAttemptOut,
    WorkSampleAttemptSummary,
    WorkSampleBrief,
    WorkSampleDraftIn,
    WorkSampleDraftOut,
    WorkSampleSummary,
)
from app.services.work_samples import WorkSamples

router = APIRouter(tags=["work samples"])
PUBLIC = "/api/v1/work-samples"
MINE = "/api/v1/me/work-samples"


@router.get(PUBLIC, response_model=list[WorkSampleSummary], summary="Work-sample briefs and their careers")
def briefs() -> list[WorkSampleSummary]:
    return WorkSamples.briefs()


@router.get(
    PUBLIC + "/{brief_id}",
    response_model=WorkSampleBrief,
    responses=error_responses(404),
    summary="One brief: audience, purpose, facts and limits (not the reference artifact)",
)
def brief(brief_id: str) -> WorkSampleBrief:
    return WorkSamples.brief(brief_id)


@router.get(
    MINE + "/{brief_id}/draft",
    response_model=WorkSampleDraftOut,
    responses=error_responses(401, 404),
    summary="Your draft",
)
def get_draft(
    brief_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WorkSampleDraftOut:
    return WorkSamples(db, user).draft(brief_id)


@router.put(
    MINE + "/{brief_id}/draft",
    response_model=WorkSampleDraftOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Save it (409 if it changed elsewhere)",
)
def put_draft(
    brief_id: str,
    body: WorkSampleDraftIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkSampleDraftOut:
    return WorkSamples(db, user).save_draft(brief_id, body)


@router.post(
    MINE + "/{brief_id}/attempts",
    response_model=WorkSampleAttemptOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 422),
    summary="Send the work sample for feedback (a revision names the attempt it revises)",
)
def attempt(
    brief_id: str,
    body: WorkSampleAttemptIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkSampleAttemptOut:
    return WorkSamples(db, user).attempt(brief_id, body)


@router.get(
    MINE + "/{brief_id}/attempts",
    response_model=list[WorkSampleAttemptSummary],
    responses=error_responses(401, 404),
    summary="Your attempts at this brief",
)
def attempts(
    brief_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WorkSampleAttemptSummary]:
    return WorkSamples(db, user).attempts(brief_id)


@router.get(
    MINE + "/attempts/{attempt_id}",
    response_model=WorkSampleAttemptOut,
    responses=error_responses(401, 404),
    summary="One attempt, with the brief version it was written against",
)
def get_attempt(
    attempt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WorkSampleAttemptOut:
    return WorkSamples(db, user).get_attempt(attempt_id)
