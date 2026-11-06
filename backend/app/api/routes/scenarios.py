"""Branching scenarios: the public catalog and the learner's server-side attempts."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.scenarios import (
    ScenarioAttemptOut,
    ScenarioAttemptSummary,
    ScenarioCatalog,
    ScenarioDetail,
    StartIn,
    StepIn,
)
from app.services import scenarios

router = APIRouter(prefix="/api/v1", tags=["scenarios"])


@router.get(
    "/scenarios",
    response_model=ScenarioCatalog,
    responses=error_responses(404),
    summary="Scenarios for a career",
)
def list_scenarios(track: str = Query(default="software-engineer", max_length=64)) -> ScenarioCatalog:
    return scenarios.catalog(track)


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioDetail,
    responses=error_responses(404),
    summary="What a scenario is about before you start (role, objective, time, scope, review)",
)
def get_scenario(scenario_id: str) -> ScenarioDetail:
    return scenarios.detail(scenario_id)


@router.post(
    "/me/scenarios/{scenario_id}/attempts",
    response_model=ScenarioAttemptOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Start (or resume) an attempt; mode=exploration with parent_id tries another approach",
)
def start_attempt(
    scenario_id: str, body: StartIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScenarioAttemptOut:
    return scenarios.Scenarios(db).start(user, scenario_id, body)


@router.get(
    "/me/scenario-attempts",
    response_model=list[ScenarioAttemptSummary],
    responses=error_responses(401),
    summary="Your scenario attempts, newest first",
)
def list_attempts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scenario_id: str | None = Query(default=None, max_length=64),
) -> list[ScenarioAttemptSummary]:
    return scenarios.Scenarios(db).attempts(user, scenario_id)


@router.get(
    "/me/scenario-attempts/{attempt_id}",
    response_model=ScenarioAttemptOut,
    responses=error_responses(401, 404),
    summary="An attempt: where you are, what you've decided, and the debrief once finished",
)
def get_attempt(
    attempt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScenarioAttemptOut:
    return scenarios.Scenarios(db).get(user, attempt_id)


@router.post(
    "/me/scenario-attempts/{attempt_id}/steps",
    response_model=ScenarioAttemptOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Answer the current node (continue, a choice or a written response); the server picks the next node",
)
def take_step(
    attempt_id: str, body: StepIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScenarioAttemptOut:
    return scenarios.Scenarios(db).step(user, attempt_id, body)
