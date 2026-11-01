from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.errors import AppError, NotFoundError
from app.models import (
    Problem,
    ProgressEvent,
    ProgressEventType,
    Submission,
    SubmissionStatus,
    TestVisibility,
    User,
)
from app.schemas.common import Page, error_responses
from app.schemas.submission import (
    ExecutionResultOut,
    PublicCaseResult,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionListItem,
)

router = APIRouter(prefix="/api/v1", tags=["submissions"])
_ERRORS = error_responses(400, 401, 404, 422)


def to_detail(sub: Submission, execution_enabled: bool) -> SubmissionDetail:
    result = None
    if sub.result is not None:
        # public_results are only ever written for PUBLIC tests; re-check defensively so a
        # runner bug can never leak hidden test data through this endpoint.
        public_inputs = {
            i: t
            for i, t in enumerate(t for t in sub.problem.test_cases if t.visibility == TestVisibility.PUBLIC)
        }
        rows = [PublicCaseResult(**r) for r in sub.result.public_results if r.get("index") in public_inputs]
        result = ExecutionResultOut(
            runtime_ms=sub.result.runtime_ms,
            memory_kb=sub.result.memory_kb,
            passed_count=sub.result.passed_count,
            total_count=sub.result.total_count,
            public_results=rows,
            stderr_excerpt=sub.result.stderr_excerpt,
        )
    return SubmissionDetail(
        id=sub.id,
        problem_slug=sub.problem.slug,
        problem_title=sub.problem.title,
        language=sub.language,
        status=sub.status,
        status_detail=sub.status_detail,
        is_terminal=sub.status.is_terminal,
        execution_enabled=execution_enabled,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        result=result,
        source_code=sub.source_code,
    )


@router.post(
    "/submissions",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SubmissionDetail,
    responses=_ERRORS,
    summary="Submit a solution (asynchronous; poll GET /submissions/{id})",
)
def create_submission(
    body: SubmissionCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> SubmissionDetail:
    if len(body.source_code) > settings.max_source_chars:
        raise AppError(
            f"Source code exceeds {settings.max_source_chars} characters",
            code="payload_too_large",
            details={"max_source_chars": settings.max_source_chars},
        )
    problem = db.scalar(select(Problem).where(Problem.slug == body.problem_slug))
    if problem is None:
        raise NotFoundError(f"Problem '{body.problem_slug}' not found")
    sub = Submission(
        user_id=user.id,
        problem_id=problem.id,
        language=body.language,
        source_code=body.source_code,
        status=SubmissionStatus.QUEUED,
    )
    db.add(sub)
    db.flush()
    backend = request.app.state.execution_backend
    backend.enqueue(db, sub)
    db.add(ProgressEvent(user_id=user.id, problem_id=problem.id, event_type=ProgressEventType.SUBMITTED))
    db.commit()
    db.refresh(sub)
    return to_detail(sub, backend.enabled)


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionDetail,
    responses=_ERRORS,
    summary="Submission status and results (owner only)",
)
def get_submission(
    submission_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmissionDetail:
    sub = db.scalar(
        select(Submission)
        .options(selectinload(Submission.problem), selectinload(Submission.result))
        .where(Submission.id == submission_id)
    )
    # 404 (not 403) for other users' submissions: don't confirm that the id exists.
    if sub is None or sub.user_id != user.id:
        raise NotFoundError("Submission not found")
    return to_detail(sub, request.app.state.execution_backend.enabled)


@router.get(
    "/me/submissions",
    response_model=Page[SubmissionListItem],
    responses=_ERRORS,
    summary="Your past attempts, newest first",
)
def list_my_submissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    problem_slug: str | None = Query(default=None, max_length=80),
    status_filter: SubmissionStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[SubmissionListItem]:
    stmt = select(Submission).join(Problem).where(Submission.user_id == user.id)
    if problem_slug:
        stmt = stmt.where(Problem.slug == problem_slug)
    if status_filter:
        stmt = stmt.where(Submission.status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(selectinload(Submission.problem), selectinload(Submission.result))
        .order_by(Submission.created_at.desc(), Submission.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        SubmissionListItem(
            id=s.id,
            problem_slug=s.problem.slug,
            problem_title=s.problem.title,
            status=s.status,
            created_at=s.created_at,
            duration_ms=s.result.runtime_ms if s.result else None,
        )
        for s in rows
    ]
    return Page[SubmissionListItem](items=items, total=total, page=page, page_size=page_size)
