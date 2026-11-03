from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.errors import AppError, ConflictError, NotFoundError
from app.models import (
    Problem,
    ProgressEvent,
    ProgressEventType,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    User,
)
from app.schemas.common import Page, error_responses
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionDetail,
    SubmissionListItem,
)
from app.services.content import is_problem_retired
from app.services.judge.backends import ExecutionDisabledError, JudgeUnavailableError
from app.services.judge.health import MESSAGES
from app.services.judge.views import public_result_view

router = APIRouter(prefix="/api/v1", tags=["submissions"])
_ERRORS = error_responses(400, 401, 404, 422, 429, 503)


def to_detail(sub: Submission, execution_enabled: bool) -> SubmissionDetail:
    result = public_result_view(sub)
    return SubmissionDetail(
        id=sub.id,
        problem_slug=sub.problem.slug,
        problem_title=sub.problem.title,
        language=sub.language,
        mode=sub.mode,
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
    backend = request.app.state.execution_backend
    if body.client_request_id:
        existing = _by_request_id(db, user, body.client_request_id)
        if existing is not None:
            return _replay(existing, problem, body, backend.enabled)
    if is_problem_retired(problem.slug):
        raise ConflictError(
            "This problem was retired and isn't used for practice any more. Your earlier submissions are kept.",
            code="content_retired",
        )
    if body.mode == SubmissionMode.RUN and not backend.enabled:
        # A queued run that can never execute is useless; a submission is still worth saving.
        raise ExecutionDisabledError(
            "Running code isn't available on this deployment. Submit to save your attempt."
        )
    if body.mode == SubmissionMode.RUN:
        state, reason, _ = request.app.state.execution_health.check(db)
        if state != "ready" and reason != "queue_delayed":
            # Run is for quick feedback; queueing it behind an outage helps no one. Submit still queues.
            raise JudgeUnavailableError(MESSAGES[reason])
    backend.admit(db, user)
    sub = Submission(
        user_id=user.id,
        problem_id=problem.id,
        language=body.language,
        source_code=body.source_code,
        mode=body.mode,
        status=SubmissionStatus.QUEUED,
        client_request_id=body.client_request_id,
    )
    db.add(sub)
    try:
        db.flush()
    except IntegrityError:
        # The same request is being handled concurrently: answer with that submission.
        db.rollback()
        existing = _by_request_id(db, user, body.client_request_id or "")
        if existing is None:
            raise
        return _replay(existing, problem, body, backend.enabled)
    backend.enqueue(db, sub)
    if body.mode == SubmissionMode.SUBMIT:
        db.add(ProgressEvent(user_id=user.id, problem_id=problem.id, event_type=ProgressEventType.SUBMITTED))
    db.commit()
    db.refresh(sub)
    return to_detail(sub, backend.enabled)


def _by_request_id(db: Session, user: User, key: str) -> Submission | None:
    return db.scalar(
        select(Submission)
        .options(selectinload(Submission.result))
        .where(Submission.user_id == user.id, Submission.client_request_id == key)
    )


def _replay(
    existing: Submission, problem: Problem, body: SubmissionCreate, enabled: bool
) -> SubmissionDetail:
    if (
        existing.problem_id != problem.id
        or existing.mode != body.mode
        or existing.source_code != body.source_code
    ):
        raise ConflictError(
            "That request id was already used for a different submission.", code="idempotency_key_reused"
        )
    return to_detail(existing, enabled)


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
    mode: SubmissionMode = Query(
        default=SubmissionMode.SUBMIT, description="`submit` (default): attempts. `run`: public-test runs."
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[SubmissionListItem]:
    stmt = select(Submission).join(Problem).where(Submission.user_id == user.id, Submission.mode == mode)
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
            mode=s.mode,
            status=s.status,
            created_at=s.created_at,
            duration_ms=s.result.runtime_ms if s.result else None,
        )
        for s in rows
    ]
    return Page[SubmissionListItem](items=items, total=total, page=page, page_size=page_size)
