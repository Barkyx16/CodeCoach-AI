from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_optional_user
from app.errors import NotFoundError
from app.models import Difficulty, Problem, ProgressEvent, ProgressEventType, TestVisibility, User
from app.schemas.common import Page, error_responses
from app.schemas.problem import ProblemDetail, ProblemSummary, PublicTestCase, TopicCount

router = APIRouter(prefix="/api/v1", tags=["problems"])


def _record_open(db: Session, user: User, problem: Problem) -> None:
    """Log at most one OPENED event per user, problem and UTC day (keeps the table small)."""
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    seen_today = db.scalar(
        select(ProgressEvent.id)
        .where(
            ProgressEvent.user_id == user.id,
            ProgressEvent.problem_id == problem.id,
            ProgressEvent.event_type == ProgressEventType.OPENED,
            ProgressEvent.created_at >= day_start,
        )
        .limit(1)
    )
    if not seen_today:
        db.add(ProgressEvent(user_id=user.id, problem_id=problem.id, event_type=ProgressEventType.OPENED))
        db.commit()


@router.get("/problems", response_model=Page[ProblemSummary], summary="List problems (paginated, filterable)")
def list_problems(
    db: Session = Depends(get_db),
    difficulty: Difficulty | None = Query(default=None),
    topic: str | None = Query(default=None, max_length=40, description="Exact topic slug, e.g. 'hash-maps'"),
    q: str | None = Query(
        default=None, max_length=80, description="Case-insensitive search in title and summary"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[ProblemSummary]:
    stmt = select(Problem)
    if difficulty:
        stmt = stmt.where(Problem.difficulty == difficulty)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Problem.title).like(like), func.lower(Problem.summary).like(like)))
    rows = db.scalars(stmt.order_by(Problem.order_index, Problem.id)).all()
    # Topics are a small JSON list per problem; filtering in Python keeps the query portable
    # across SQLite and Postgres. With thousands of problems this moves to a join table.
    if topic:
        rows = [p for p in rows if topic in p.topics]
    start = (page - 1) * page_size
    return Page[ProblemSummary](
        items=[ProblemSummary.model_validate(p) for p in rows[start : start + page_size]],
        total=len(rows),
        page=page,
        page_size=page_size,
    )


@router.get("/topics", response_model=list[TopicCount], summary="All topics with problem counts")
def list_topics(db: Session = Depends(get_db)) -> list[TopicCount]:
    counts: dict[str, int] = {}
    for topics in db.scalars(select(Problem.topics)):
        for t in topics:
            counts[t] = counts.get(t, 0) + 1
    return [TopicCount(topic=t, count=n) for t, n in sorted(counts.items())]


@router.get(
    "/problems/{slug}",
    response_model=ProblemDetail,
    responses=error_responses(404),
    summary="Problem statement, starter code and public tests",
)
def get_problem(
    slug: str, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> ProblemDetail:
    problem = db.scalar(select(Problem).options(selectinload(Problem.test_cases)).where(Problem.slug == slug))
    if problem is None:
        raise NotFoundError(f"Problem '{slug}' not found")
    if user is not None:
        _record_open(db, user, problem)
    public = [t for t in problem.test_cases if t.visibility == TestVisibility.PUBLIC]
    return ProblemDetail(
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        topics=problem.topics,
        summary=problem.summary,
        statement=problem.statement,
        constraints=problem.constraints,
        examples=problem.examples,
        starter_code=problem.starter_code,
        signature=problem.signature,
        public_tests=[
            PublicTestCase(id=t.id, input=t.input, expected_output=t.expected_output) for t in public
        ],
        hidden_test_count=len(problem.test_cases) - len(public),
        hint_levels=len(problem.hints),
    )
