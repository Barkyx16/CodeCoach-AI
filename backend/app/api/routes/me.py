from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.careers import CATALOG
from app.errors import NotFoundError
from app.models import User
from app.schemas.activity import (
    ActivityFacets,
    ActivityItem,
    ActivityStatus,
    ActivityType,
    CareerAnalytics,
    ResumeOut,
)
from app.schemas.common import Page, error_responses
from app.schemas.progress import ProgressOut, Recommendation
from app.services.account import export_user_data
from app.services.activity import ActivityFilters, ActivityService
from app.services.progress import ProgressService

router = APIRouter(prefix="/api/v1/me", tags=["progress"])


@router.get(
    "/progress",
    response_model=ProgressOut,
    responses=error_responses(401),
    summary="Your aggregate progress and analytics",
)
def progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProgressOut:
    return ProgressService(db).progress(user)


@router.get(
    "/recommendations",
    response_model=list[Recommendation],
    responses=error_responses(401),
    summary="Personalized next problems, each with a reason",
)
def recommendations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[Recommendation]:
    return ProgressService(db).recommend(user, limit=limit)


@router.get(
    "/export",
    responses=error_responses(401),
    summary="Download all of your data as JSON",
    response_description="A JSON document with your profile, submissions, AI feedback, interviews and activity",
)
def export(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    version: int = Query(
        default=1,
        ge=1,
        le=2,
        description="1 (default; what restore reads) or 2: the same data plus record ids and typed links "
        "between records (applications, events, targets, stories, notes, schedule entries, kits, "
        "reflections and their steps). Version 2 can't be restored yet.",
    ),
) -> JSONResponse:
    from app.services.export_v2 import export_v2

    data = export_v2(db, user) if version == 2 else export_user_data(db, user)
    name = "codecoach-data-v2.json" if version == 2 else "codecoach-data.json"
    return JSONResponse(
        data,
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


def _activity(request: Request, db: Session) -> ActivityService:
    return ActivityService(db, judge_enabled=request.app.state.execution_backend.enabled)


@router.get(
    "/activity",
    response_model=Page[ActivityItem],
    responses=error_responses(401, 422),
    summary="Everything you've practised, newest first, across careers (filterable)",
)
def activity(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    career: str | None = Query(default=None, max_length=64, description="A career slug, or 'coding'"),
    type: ActivityType | None = Query(default=None),  # noqa: A002 - the API's field name
    since: date | None = Query(default=None, description="Inclusive (UTC)"),
    until: date | None = Query(default=None, description="Inclusive (UTC)"),
    skill: str | None = Query(default=None, max_length=120),
    status: ActivityStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1, le=500),
    page_size: int = Query(default=20, ge=1, le=50),
) -> Page[ActivityItem]:
    f = ActivityFilters(career=career, type=type, since=since, until=until, skill=skill, status=status, q=q)
    return _activity(request, db).feed(user, f, page, page_size)


@router.get(
    "/activity/facets",
    response_model=ActivityFacets,
    responses=error_responses(401),
    summary="Filter options for your activity: careers, types, statuses and (for one career) skills",
)
def activity_facets(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    career: str | None = Query(default=None, max_length=64),
) -> ActivityFacets:
    return _activity(request, db).facets(user, career)


@router.get(
    "/careers/{slug}/analytics",
    response_model=CareerAnalytics,
    responses=error_responses(401, 404, 422),
    summary="Your analytics for one career's questions over a date range (any career, not only your current one)",
)
def career_analytics(
    slug: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    since: date | None = Query(default=None, description="Inclusive; omit for all time"),
    until: date | None = Query(default=None, description="Inclusive; default today (UTC)"),
) -> CareerAnalytics:
    if slug not in CATALOG:
        raise NotFoundError(f"Career '{slug}' not found")
    end = until or datetime.now(UTC).date()
    return _activity(request, db).career_analytics(user, slug, since, end)


@router.get(
    "/resume",
    response_model=ResumeOut,
    responses=error_responses(401),
    summary="Saved work to continue: an interview in progress, an unsolved problem, your last question",
)
def resume(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ResumeOut:
    return _activity(request, db).resume(user)
