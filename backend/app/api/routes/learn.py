"""Learn mode: public units and the signed-in learner's progress on them."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.learn import CheckIn, CheckResult, EventIn, LearnCatalog, UnitLink, UnitOut, UnitProgress
from app.services import learn

router = APIRouter(prefix="/api/v1", tags=["learn"])


@router.get(
    "/learn",
    response_model=LearnCatalog,
    responses=error_responses(404),
    summary="Learning units for a career, and which careers have any",
)
def list_units(track: str = Query(default="software-engineer", max_length=64)) -> LearnCatalog:
    return learn.catalog(track)


@router.get(
    "/learn/related",
    response_model=list[UnitLink],
    summary="Units that prepare for a question or coding problem",
)
def related_units(
    db: Session = Depends(get_db),
    track: str | None = Query(default=None, max_length=64),
    question_id: str | None = Query(default=None, max_length=80),
    problem_slug: str | None = Query(default=None, max_length=80),
) -> list[UnitLink]:
    return learn.related(db, track=track, question_id=question_id, problem_slug=problem_slug)


@router.get(
    "/learn/units/{unit_id}",
    response_model=UnitOut,
    responses=error_responses(404),
    summary="A learning unit (the check's answers are not included)",
)
def get_unit(unit_id: str) -> UnitOut:
    return learn.unit_out(learn.find_unit(unit_id))


@router.get(
    "/me/learn",
    response_model=dict[str, UnitProgress],
    responses=error_responses(401, 404),
    summary="Your progress on every unit of a career",
)
def my_units(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    track: str = Query(default="software-engineer", max_length=64),
) -> dict[str, UnitProgress]:
    learn.catalog(track)  # 404 for an unknown career
    return learn.Learn(db).statuses(user, track)


@router.get(
    "/me/learn/units/{unit_id}",
    response_model=UnitProgress,
    responses=error_responses(401, 404),
    summary="Your progress on a unit (also records 'practiced' when the linked practice has been done)",
)
def my_progress(
    unit_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UnitProgress:
    return learn.Learn(db).progress(user, unit_id)


@router.post(
    "/me/learn/units/{unit_id}/events",
    response_model=UnitProgress,
    responses=error_responses(401, 404, 409, 422),
    summary="Record that you opened ('started') or finished reading ('read') the unit version on screen",
)
def record_event(
    unit_id: str, body: EventIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UnitProgress:
    return learn.Learn(db).record(user, unit_id, body.kind, body.version)


@router.post(
    "/me/learn/units/{unit_id}/check",
    response_model=CheckResult,
    responses=error_responses(401, 404, 409, 422),
    summary="Submit the comprehension check; graded on the server under the unit's rule",
)
def submit_check(
    unit_id: str, body: CheckIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CheckResult:
    return learn.Learn(db).check(user, unit_id, body)
