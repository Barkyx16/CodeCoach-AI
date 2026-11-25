"""Search your own saved work: notes, stories, kits and applications (docs/WORKSPACE_SEARCH.md).

A POST so the words travel in the body: they stay out of URLs, browser history, proxy access logs
and the request log, which records the path only."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.errors import RateLimitedError
from app.models import User
from app.schemas.common import error_responses
from app.schemas.workspace_search import WorkspaceSearchIn, WorkspaceSearchOut
from app.services.workspace_search import search

router = APIRouter(tags=["progress"])


@router.post(
    "/api/v1/me/search",
    response_model=WorkspaceSearchOut,
    responses=error_responses(401, 422, 429),
    summary="Search your own notes, stories, interview-day kits and applications",
)
def search_workspace(
    body: WorkspaceSearchIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceSearchOut:
    allowed, retry_after = request.app.state.search_limiter.hit(f"search:{user.id}")
    if not allowed:
        raise RateLimitedError.wait(
            "That's a lot of searches in a minute. Try again in a moment.", retry_after
        )
    return WorkspaceSearchOut.model_validate(
        search(db, user, body.q, kinds=body.kinds, include_archived=body.include_archived, limit=body.limit)
    )
