"""Recent work to continue: a few of your own records, newest first (docs/CONTINUE.md)."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.recent_work import RecentWorkOut
from app.services.recent_work import MAX_LIMIT, SHOWS, recent_work

router = APIRouter(tags=["progress"])


@router.get(
    "/api/v1/me/recent-work",
    response_model=RecentWorkOut,
    responses=error_responses(401),
    summary="A few of your recent records to continue, newest first (titles and times only)",
)
def recent(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=6, ge=1, le=MAX_LIMIT),
    shows: str = Query(
        default="",
        max_length=200,
        description="What the page can show beyond the kinds from before Volume 20, comma-separated: "
        f"{', '.join(sorted(SHOWS))}. Unknown values are ignored; without it, the response is as before.",
    ),
) -> RecentWorkOut:
    asked = frozenset(s.strip() for s in shows.split(",") if s.strip())
    return RecentWorkOut.model_validate(
        recent_work(db, user, limit, judge_enabled=request.app.state.execution_backend.enabled, shows=asked)
    )
