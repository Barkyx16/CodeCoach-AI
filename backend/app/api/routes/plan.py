from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.review import ReviewAdd, ReviewQueue, SnoozeIn
from app.schemas.roadmap import GoalsIn, GoalsOut, PlanItemOut, PlanOut
from app.services.review_queue import ReviewQueueService
from app.services.roadmap import Roadmap

router = APIRouter(prefix="/api/v1/me", tags=["plan"])


def _roadmap(request: Request, db: Session) -> Roadmap:
    return Roadmap(db, judge_enabled=request.app.state.execution_backend.enabled)


@router.get(
    "/goals", response_model=GoalsOut, responses=error_responses(401, 404), summary="Your goals for a career"
)
def get_goals(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    track: str | None = Query(default=None, max_length=64, description="Default: your current career"),
) -> GoalsOut:
    return _roadmap(request, db).goals(user, track)


@router.put(
    "/goals",
    response_model=GoalsOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Save goals (every field optional; set setup_skipped to start with defaults). Progress is kept.",
)
def put_goals(
    body: GoalsIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> GoalsOut:
    return _roadmap(request, db).save_goals(user, body)


@router.get(
    "/plan",
    response_model=PlanOut,
    responses=error_responses(401, 404, 422),
    summary="Your practice plan for a career, today's session for the time you have, and your baseline",
)
def get_plan(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    track: str | None = Query(default=None, max_length=64),
    minutes: int = Query(default=15, ge=5, le=240, description="Time available today"),
) -> PlanOut:
    return _roadmap(request, db).plan(user, track, minutes)


@router.post(
    "/plan/items/{item_id}/skip",
    response_model=PlanItemOut,
    responses=error_responses(401, 404, 409),
    summary="Set an activity aside (it's recorded as skipped, never as done)",
)
def skip_item(
    item_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PlanItemOut:
    svc = _roadmap(request, db)
    return svc.item_out(svc.skip(user, item_id))


@router.post(
    "/plan/items/{item_id}/replace",
    response_model=PlanItemOut,
    responses=error_responses(401, 404, 409),
    summary="Swap an activity for another one of the same kind and skill; returns the new activity",
)
def replace_item(
    item_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PlanItemOut:
    svc = _roadmap(request, db)
    return svc.item_out(svc.replace(user, item_id))


@router.post(
    "/plan/items/{item_id}/reviewed",
    response_model=PlanItemOut,
    responses=error_responses(401, 404, 409),
    summary="Mark a 'review feedback' activity as read (self-reported; other activities complete from your work)",
)
def mark_reviewed(
    item_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PlanItemOut:
    svc = _roadmap(request, db)
    return svc.item_out(svc.mark_reviewed(user, item_id))


@router.get(
    "/reviews", response_model=ReviewQueue, responses=error_responses(401), summary="Your spaced review queue"
)
def review_queue(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReviewQueue:
    return ReviewQueueService(db).queue(user)


@router.post(
    "/reviews",
    response_model=ReviewQueue,
    responses=error_responses(400, 401, 404, 422),
    summary="Save a question for spaced review (saving it again is a no-op)",
)
def add_review(
    body: ReviewAdd, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewQueue:
    return ReviewQueueService(db).add(user, body)


@router.post(
    "/reviews/{item_id}/snooze",
    response_model=ReviewQueue,
    responses=error_responses(401, 404, 422),
    summary="Snooze a review by 1, 3 or 7 days",
)
def snooze_review(
    item_id: str, body: SnoozeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewQueue:
    return ReviewQueueService(db).snooze(user, item_id, body.days)


@router.delete(
    "/reviews/{item_id}",
    response_model=ReviewQueue,
    responses=error_responses(401, 404),
    summary="Remove a question from the queue",
)
def remove_review(
    item_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReviewQueue:
    return ReviewQueueService(db).remove(user, item_id)
