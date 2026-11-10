"""Recent work to continue: a few of your own records, newest first (docs/CONTINUE.md)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.recent_work import RecentWorkOut
from app.services.recent_work import MAX_LIMIT, recent_work

router = APIRouter(tags=["progress"])


@router.get(
    "/api/v1/me/recent-work",
    response_model=RecentWorkOut,
    responses=error_responses(401),
    summary="A few of your recent records to continue, newest first (titles and times only)",
)
def recent(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=6, ge=1, le=MAX_LIMIT),
) -> RecentWorkOut:
    return RecentWorkOut.model_validate(recent_work(db, user, limit))
