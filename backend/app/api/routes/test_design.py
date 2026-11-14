"""Test design: propose cases, run them against a reference and authored faulty versions."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app import tracing
from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.models import User
from app.schemas.common import error_responses
from app.schemas.test_design import (
    TestDesignExercise,
    TestDesignRunIn,
    TestDesignRunOut,
    TestDesignRunSummary,
    TestDesignSummary,
    TestDesignVariant,
)
from app.services.judge.backends import JudgeUnavailableError
from app.services.judge.health import MESSAGES
from app.services.test_design import TestDesign

router = APIRouter(tags=["test design"])
PUBLIC = "/api/v1/test-design"
MINE = "/api/v1/me/test-design"


@router.get(PUBLIC, response_model=list[TestDesignSummary], summary="Test design exercises")
def exercises(db: Session = Depends(get_db)) -> list[TestDesignSummary]:
    return TestDesign(db).exercises()


@router.get(
    PUBLIC + "/{slug}",
    response_model=TestDesignExercise,
    responses=error_responses(404),
    summary="One exercise: the specification, its input shape and limits (not the faulty versions)",
)
def exercise(slug: str, request: Request, db: Session = Depends(get_db)) -> TestDesignExercise:
    return TestDesign(db).exercise(slug, request.app.state.execution_backend.enabled)


@router.get(
    PUBLIC + "/{slug}/variants",
    response_model=list[TestDesignVariant],
    responses=error_responses(404),
    summary="The authored faulty versions and their defects (shown when the learner asks)",
)
def variants(slug: str, db: Session = Depends(get_db)) -> list[TestDesignVariant]:
    return TestDesign(db).variants(slug)


@router.post(
    MINE + "/{slug}/runs",
    response_model=TestDesignRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(401, 404, 409, 422, 429, 503),
    summary="Run your cases (asynchronous; poll the run). Without a judge they're saved as not run",
)
def start_run(
    slug: str,
    body: TestDesignRunIn,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TestDesignRunOut:
    enabled = request.app.state.execution_backend.enabled
    service = TestDesign(db, user, settings)
    if enabled and service.find_by_key(body.client_request_id) is None:
        # Quick feedback, like Run: queueing behind an outage helps no one, so it's refused and the
        # cases stay on the page. A resend of a run already made is answered with that run.
        state, reason, _ = request.app.state.execution_health.check(db)
        if state != "ready" and reason != "queue_delayed":
            raise JudgeUnavailableError(MESSAGES[reason])
    run, created = service.start_run(slug, body, enabled, tracing.current_trace_id())
    if not created:
        response.status_code = status.HTTP_200_OK  # a resend: the run it already made
    return run


@router.get(
    MINE + "/{slug}/runs",
    response_model=list[TestDesignRunSummary],
    responses=error_responses(401, 404),
    summary="Your runs of this exercise",
)
def runs(
    slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TestDesignRunSummary]:
    return TestDesign(db, user).runs(slug)


@router.get(
    MINE + "/runs/{run_id}",
    response_model=TestDesignRunOut,
    responses=error_responses(401, 404),
    summary="One run: its cases, exercise version and report",
)
def get_run(
    run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TestDesignRunOut:
    return TestDesign(db, user).get_run(run_id)
