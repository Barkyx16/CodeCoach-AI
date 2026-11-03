"""Content metadata, learners' issue reports, and admin triage."""

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_admin
from app.careers import CATALOG
from app.careers.questions import get_question
from app.errors import NotFoundError, RateLimitedError
from app.models import User
from app.schemas.common import error_responses
from app.schemas.content import (
    AdminReportDetail,
    ContentMeta,
    ContentType,
    CorrectionIn,
    DuplicateIn,
    MyReport,
    QuestionVersionOut,
    ReportGroup,
    ReportIn,
    ReportStatus,
    RestoreIn,
    RetireIn,
    StatusIn,
)
from app.services.content import ContentService

router = APIRouter(prefix="/api/v1", tags=["content quality"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["content quality"])


@router.get(
    "/content/{content_type}/{content_id:path}/meta",
    response_model=ContentMeta,
    responses=error_responses(404),
    summary="Where this content came from, its version, status, corrections and trust labels",
)
def meta(content_type: ContentType, content_id: str, db: Session = Depends(get_db)) -> ContentMeta:
    return ContentService(db).meta(content_type, content_id)


@router.get(
    "/careers/{slug}/questions/{question_id}/versions/{version}",
    response_model=QuestionVersionOut,
    responses=error_responses(404),
    summary="A question as it read at an earlier version (for answers written against it)",
)
def question_version(slug: str, question_id: str, version: int = Path(ge=1)) -> QuestionVersionOut:
    current = get_question(slug, question_id) if slug in CATALOG else None
    if current is None or version > current.version:
        raise NotFoundError("Question version not found")
    q = get_question(slug, question_id, version)
    assert q is not None
    return QuestionVersionOut(version=q.version, title=q.title, prompt=q.prompt)


@router.post(
    "/reports",
    response_model=MyReport,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 409, 422, 429),
    summary="Report a problem with a question, a coding problem, or the feedback on your answer",
)
def report(
    body: ReportIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MyReport:
    allowed, retry_after = request.app.state.report_limiter.hit(f"report:{user.id}")
    if not allowed:
        raise RateLimitedError(
            "You've sent a lot of reports. Try again later.",
            details={"retry_after_seconds": round(retry_after, 1)},
        )
    return ContentService(db).report(user, body)


@router.get(
    "/me/reports",
    response_model=list[MyReport],
    responses=error_responses(401),
    summary="Your reports and what happened to them (never other people's, never internal notes)",
)
def my_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[MyReport]:
    return ContentService(db).mine(user)


# ---------------------------------------------------------------------------- admins only


@admin_router.get(
    "/reports",
    response_model=list[ReportGroup],
    responses=error_responses(404),
    summary="Reports grouped by content",
)
def admin_reports(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    status_filter: ReportStatus | None = Query(
        default=None, alias="status", description="'open' includes investigating"
    ),
) -> list[ReportGroup]:
    return ContentService(db).groups(status_filter)


@admin_router.get(
    "/reports/{report_id}",
    response_model=AdminReportDetail,
    responses=error_responses(404),
    summary="One report with its audit trail",
)
def admin_report(
    report_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> AdminReportDetail:
    return ContentService(db).detail(report_id)


@admin_router.post(
    "/reports/{report_id}/status",
    response_model=AdminReportDetail,
    responses=error_responses(400, 404, 422),
    summary="Change a report's status",
)
def admin_status(
    report_id: str, body: StatusIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> AdminReportDetail:
    return ContentService(db).set_status(admin, report_id, body)


@admin_router.post(
    "/reports/{report_id}/duplicate",
    response_model=AdminReportDetail,
    responses=error_responses(400, 404, 422),
    summary="Group a report under another (or ungroup it)",
)
def admin_duplicate(
    report_id: str, body: DuplicateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> AdminReportDetail:
    return ContentService(db).set_duplicate(admin, report_id, body)


@admin_router.post(
    "/content/question/{slug}/{question_id}/corrections",
    response_model=ContentMeta,
    responses=error_responses(400, 404, 422),
    summary="Publish a correction as a new version (answers keep the version they were written against)",
)
def admin_correct(
    slug: str,
    question_id: str,
    body: CorrectionIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ContentMeta:
    return ContentService(db).correct(admin, slug, question_id, body)


@admin_router.post(
    "/content/{content_type}/{content_id:path}/retire",
    response_model=ContentMeta,
    responses=error_responses(400, 404, 422),
    summary="Retire content: readable in history and saved items, no longer used for practice or assessment",
)
def admin_retire(
    content_type: ContentType,
    content_id: str,
    body: RetireIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ContentMeta:
    return ContentService(db).retire(admin, content_type, content_id, body)


@admin_router.post(
    "/content/{content_type}/{content_id:path}/restore",
    response_model=ContentMeta,
    responses=error_responses(404, 422),
    summary="Undo a retirement",
)
def admin_restore(
    content_type: ContentType,
    content_id: str,
    body: RestoreIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ContentMeta:
    return ContentService(db).restore(admin, content_type, content_id, body.internal_note)
