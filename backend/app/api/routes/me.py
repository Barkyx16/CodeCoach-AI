from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.careers import CATALOG
from app.errors import NotFoundError, RateLimitedError
from app.models import User
from app.schemas.activity import (
    ActivityFacets,
    ActivityItem,
    ActivityStatus,
    ActivityType,
    CareerAnalytics,
    ResumeOut,
)
from app.schemas.common import APIModel, Page, error_responses
from app.schemas.progress import ProgressOut, Recommendation
from app.services.account import export_user_data
from app.services.activity import ActivityFilters, ActivityService
from app.services.progress import ProgressService
from app.services.rate_limit import enforce

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
    request: Request,
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

    enforce(
        request.app.state.export_limiter,
        f"export:{user.id}",
        "You've downloaded your data many times this hour. Try again later.",
    )
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


class RequestOutcome(APIModel):
    """What a request sent with this key made, if anything (Volume 8, prompt 1)."""

    kind: Literal["submission", "run", "hint", "review", "explain", "story", "answer", "note"]
    state: Literal["done", "pending"] = Field(
        description="pending: a submission still queued or being judged"
    )
    id: str = Field(description="The record it made: a submission, AI interaction, story, answer or note id")
    created_at: datetime
    problem_slug: str | None = None
    hint_level: int | None = None


@router.get(
    "/requests/{key}",
    response_model=RequestOutcome,
    summary="What a request you sent with this key made (read-only)",
    responses=error_responses(401, 404, 422, 429),
)
def request_outcome(
    key: str = Path(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RequestOutcome:
    """A page that lost a reply, then was reloaded, asks here before offering to send again: did
    the request arrive, and what did it make? Only your own records are searched. It reads and
    never creates; 404 means the server has no record (it never arrived, or what it made has been
    deleted since). 429 `request_in_progress` means a coaching request of yours is still being
    answered (PostgreSQL), so there's no record yet: ask again after `Retry-After`. The key is
    never permission for anything: it only finds your own record."""
    from sqlalchemy import select

    from app.models import (
        AIAction,
        AIInteraction,
        ExperienceEntry,
        Note,
        PracticeAnswer,
        Problem,
        Submission,
        SubmissionMode,
        SubmissionStatus,
    )

    sub = db.scalar(
        select(Submission).where(Submission.user_id == user.id, Submission.client_request_id == key)
    )
    if sub is not None:
        slug = db.scalar(select(Problem.slug).where(Problem.id == sub.problem_id))
        running = sub.status in (SubmissionStatus.QUEUED, SubmissionStatus.RUNNING)
        return RequestOutcome(
            kind="run" if sub.mode == SubmissionMode.RUN else "submission",
            state="pending" if running else "done",
            id=sub.id,
            created_at=sub.created_at,
            problem_slug=slug,
        )
    ai = db.scalar(
        select(AIInteraction).where(AIInteraction.user_id == user.id, AIInteraction.client_request_id == key)
    )
    if ai is not None:
        kind: Literal["hint", "review", "explain"] = (
            "hint" if ai.action == AIAction.HINT else "review" if ai.action == AIAction.REVIEW else "explain"
        )
        return RequestOutcome(
            kind=kind,
            state="done",
            id=ai.id,
            created_at=ai.created_at,
            problem_slug=db.scalar(select(Problem.slug).where(Problem.id == ai.problem_id)),
            hint_level=ai.hint_level,
        )
    story = db.scalar(
        select(ExperienceEntry).where(
            ExperienceEntry.user_id == user.id, ExperienceEntry.client_request_id == key
        )
    )
    if story is not None:
        return RequestOutcome(kind="story", state="done", id=story.id, created_at=story.created_at)
    answer = db.scalar(
        select(PracticeAnswer).where(
            PracticeAnswer.user_id == user.id, PracticeAnswer.client_request_id == key
        )
    )
    if answer is not None:
        return RequestOutcome(kind="answer", state="done", id=answer.id, created_at=answer.created_at)
    note = db.scalar(select(Note).where(Note.user_id == user.id, Note.client_request_id == key))
    if note is not None:
        return RequestOutcome(kind="note", state="done", id=note.id, created_at=note.created_at)
    from app.services.ai.service import CoachService

    if CoachService.turn_in_flight(db, user.id):
        # A hint or review is recorded only when its answer is, so while one is still being
        # answered there's no record yet. That isn't "never arrived": say so, and to ask again.
        raise RateLimitedError.wait(
            "A coaching request you sent is still being answered, so this can't be told yet. "
            "Check again in a moment.",
            2,
            code="request_in_progress",
        )
    raise NotFoundError(
        "The server has no record of this request: it never arrived, or what it made has since been deleted.",
        code="request_not_found",
    )
