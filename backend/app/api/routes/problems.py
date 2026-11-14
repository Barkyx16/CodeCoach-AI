from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_optional_user
from app.errors import NotFoundError
from app.models import Difficulty, Problem, ProgressEvent, ProgressEventType, TestVisibility, User
from app.schemas.common import Page, error_responses
from app.schemas.problem import (
    DifficultyCounts,
    LabBrief,
    LabExplanation,
    ProblemDetail,
    ProblemKind,
    ProblemSummary,
    PublicTestCase,
    TopicCount,
)
from app.services import search
from app.services.content import retired_problem_slugs

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
    if seen_today:
        return
    key = f"opened:{problem.id}:{day_start.date().isoformat()}"
    db.add(
        ProgressEvent(
            user_id=user.id, problem_id=problem.id, event_type=ProgressEventType.OPENED, dedupe_key=key
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # a concurrent request recorded today's open first: count it once


def _search_text(p: Problem) -> search.Searchable:
    return search.Searchable(
        title=p.title.lower(),
        topics=" ".join(t.replace("-", " ") for t in p.topics).lower(),
        summary=p.summary.lower(),
        statement=p.statement.lower(),
    )


_KIND = Query(
    default="problem", description="problem: the coding library; debug: the debugging lab's exercises"
)


def _matching(db: Session, topic: str | None, q: str | None, kind: str = "problem") -> list[Problem]:
    """Problems of one kind matching the topic and search words, in library order (or by relevance)."""
    retired = retired_problem_slugs()  # not offered for practice; still readable by link
    rows = [
        p
        for p in db.scalars(
            select(Problem).where(Problem.kind == kind).order_by(Problem.order_index, Problem.id)
        ).all()
        if p.slug not in retired
    ]
    # Topics are a small JSON list per problem; filtering in Python keeps the query portable
    # across SQLite and Postgres. With thousands of problems this moves to a join table.
    if topic:
        rows = [p for p in rows if topic in p.topics]
    if q and q.strip():
        rows = search.rank(((p, _search_text(p)) for p in rows), q)
    return rows


@router.get("/problems", response_model=Page[ProblemSummary], summary="List problems (paginated, filterable)")
def list_problems(
    db: Session = Depends(get_db),
    difficulty: Difficulty | None = Query(default=None),
    topic: str | None = Query(default=None, max_length=40, description="Exact topic slug, e.g. 'hash-maps'"),
    q: str | None = Query(
        default=None,
        max_length=80,
        description="Keywords or a plain description, e.g. 'reverse words' or 'dp grid'. Matches titles, "
        "topics, summaries and statements; results are ranked by relevance.",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    kind: ProblemKind = _KIND,
) -> Page[ProblemSummary]:
    rows = _matching(db, topic, q, kind)
    if difficulty:
        rows = [p for p in rows if p.difficulty == difficulty]
    start = (page - 1) * page_size
    return Page[ProblemSummary](
        items=[ProblemSummary.model_validate(p) for p in rows[start : start + page_size]],
        total=len(rows),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/problems/counts",
    response_model=DifficultyCounts,
    summary="How many problems match the filters, per difficulty (for the library tabs)",
)
def count_problems(
    db: Session = Depends(get_db),
    topic: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=80),
    kind: ProblemKind = _KIND,
) -> DifficultyCounts:
    counts = dict.fromkeys(Difficulty, 0)
    for p in _matching(db, topic, q, kind):
        counts[p.difficulty] += 1
    return DifficultyCounts(
        easy=counts[Difficulty.EASY], medium=counts[Difficulty.MEDIUM], hard=counts[Difficulty.HARD]
    )


@router.get("/topics", response_model=list[TopicCount], summary="All topics with problem counts")
def list_topics(db: Session = Depends(get_db)) -> list[TopicCount]:
    counts: dict[str, int] = {}
    for topics in db.scalars(select(Problem.topics).where(Problem.kind == "problem")):
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
        kind=problem.kind,
        lab=_lab_brief(problem),
    )


def _lab_brief(problem: Problem) -> LabBrief | None:
    if problem.kind != "debug" or not problem.lab:
        return None
    by_position = {t.position: t.id for t in problem.test_cases if t.visibility == TestVisibility.PUBLIC}
    return LabBrief(
        version=problem.lab["version"],
        intended_behavior=problem.lab["intended_behavior"],
        reproduction_test_ids=[by_position[i] for i in problem.lab["reproduction"] if i in by_position],
        review_status=problem.lab["review_status"],
    )


@router.get(
    "/problems/{slug}/lab/explanation",
    response_model=LabExplanation,
    responses=error_responses(404),
    summary="A debugging exercise's defect explanation and reference repair (shown when the learner asks)",
)
def get_lab_explanation(slug: str, db: Session = Depends(get_db)) -> LabExplanation:
    """Authored content, the same for everyone: what the defect is, why a simple case misses it,
    one correct repair and a follow-up. It reveals no hidden test. Asking for it is recorded nowhere:
    looking is part of learning, not a mark against the learner."""
    problem = db.scalar(select(Problem).where(Problem.slug == slug, Problem.kind == "debug"))
    if problem is None or not problem.lab:
        raise NotFoundError(f"Debugging exercise '{slug}' not found")
    lab = problem.lab
    return LabExplanation(
        version=lab["version"],
        defect_summary=lab["defect"]["summary"],
        explanation=lab["defect"]["explanation"],
        why_missed=lab["defect"]["why_missed"],
        reference_repair=lab["reference_repair"],
        follow_up=lab["follow_up"],
    )
