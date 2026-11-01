from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.models import AIAction, AIInteraction, Problem, User
from app.schemas.ai import (
    AIHistoryItem,
    AIUsage,
    HintRequest,
    HintResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.schemas.common import Page, error_responses
from app.services.ai.service import CoachService

router = APIRouter(prefix="/api/v1", tags=["ai coach"])
_ERRORS = error_responses(401, 404, 409, 422, 429)


def get_coach(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> CoachService:
    return CoachService(db, settings, request.app.state.ai_provider)


@router.post(
    "/ai/hint",
    response_model=HintResponse,
    responses=_ERRORS,
    summary="Progressive hint (levels unlock one at a time)",
)
def hint(
    body: HintRequest, user: User = Depends(get_current_user), coach: CoachService = Depends(get_coach)
) -> HintResponse:
    return coach.hint(user, body)


@router.post(
    "/ai/review",
    response_model=ReviewResponse,
    responses=_ERRORS,
    summary="Structured code review (advisory; never overrides the judge)",
)
def review(
    body: ReviewRequest, user: User = Depends(get_current_user), coach: CoachService = Depends(get_coach)
) -> ReviewResponse:
    return coach.review(user, body)


@router.get("/ai/usage", response_model=AIUsage, responses=_ERRORS, summary="Your AI budget for the last 24h")
def usage(user: User = Depends(get_current_user), coach: CoachService = Depends(get_coach)) -> AIUsage:
    return coach.usage(user)


@router.get(
    "/me/ai-history",
    response_model=Page[AIHistoryItem],
    responses=_ERRORS,
    summary="Saved hints and reviews, newest first",
)
def ai_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    problem_slug: str | None = Query(default=None, max_length=80),
    action: AIAction | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[AIHistoryItem]:
    stmt = (
        select(AIInteraction, Problem)
        .join(Problem, Problem.id == AIInteraction.problem_id)
        .where(AIInteraction.user_id == user.id)
    )
    if problem_slug:
        stmt = stmt.where(Problem.slug == problem_slug)
    if action:
        stmt = stmt.where(AIInteraction.action == action)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(AIInteraction.created_at.desc(), AIInteraction.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        AIHistoryItem(
            id=ai.id,
            problem_slug=p.slug,
            problem_title=p.title,
            action=ai.action.value,
            hint_level=ai.hint_level,
            provider=ai.provider,
            created_at=ai.created_at,
            response=ai.response,
        )
        for ai, p in rows
    ]
    return Page[AIHistoryItem](items=items, total=total, page=page, page_size=page_size)
