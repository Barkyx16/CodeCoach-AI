"""Communication drills: short exercises between full mock interviews."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.drills import DrillAttemptIn, DrillAttemptOut, DrillOut
from app.services.drills import Drills

router = APIRouter(prefix="/api/v1/me/drills", tags=["drills"])


@router.get(
    "",
    response_model=list[DrillOut],
    responses=error_responses(401),
    summary="The drills, with prompts for your career",
)
def list_drills(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DrillOut]:
    return Drills(db, user).all()


@router.get("/{drill_id}", response_model=DrillOut, responses=error_responses(401, 404), summary="One drill")
def get_drill(
    drill_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DrillOut:
    return Drills(db, user).get(drill_id)


@router.get(
    "/{drill_id}/attempts",
    response_model=list[DrillAttemptOut],
    responses=error_responses(401, 404),
    summary="Your attempts, newest first",
)
def attempts(
    drill_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DrillAttemptOut]:
    return Drills(db, user).attempts(drill_id)


@router.post(
    "/{drill_id}/attempts",
    response_model=DrillAttemptOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 422, 429),
    summary="Send an attempt (typed, or a transcript you checked); a retry with the same id returns the first",
)
def submit(
    drill_id: str,
    body: DrillAttemptIn,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DrillAttemptOut:
    out, created = Drills(db, user).submit(drill_id, body, request.app.state.practice_limiter)
    if not created:
        response.status_code = status.HTTP_200_OK
    return out
