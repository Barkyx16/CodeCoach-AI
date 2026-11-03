"""Restore your own data from a CodeCoach backup: preview first, add only what you choose."""

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.errors import AppError
from app.models import User
from app.schemas.common import error_responses
from app.schemas.restore import RestoreBatch, RestorePreview
from app.services.restore import MAX_BYTES, Restore

router = APIRouter(prefix="/api/v1/me/restore", tags=["backup"])
_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"type": "object", "description": "A CodeCoach backup (the export file), as is"}
            }
        },
    }
}


async def _read(request: Request) -> bytes:
    """The body, refused as soon as it passes the size limit (never read in full first)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise AppError(
            "That file is larger than 5 MB, so it can't be a CodeCoach backup.", code="file_too_large"
        )
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BYTES:
            raise AppError(
                "That file is larger than 5 MB, so it can't be a CodeCoach backup.", code="file_too_large"
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/preview",
    response_model=RestorePreview,
    responses=error_responses(400, 401),
    openapi_extra=_BODY,
    summary="Check a backup and show what would be restored (nothing changes)",
)
async def preview(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RestorePreview:
    raw = await _read(request)
    response.headers["Cache-Control"] = "no-store"
    return await run_in_threadpool(Restore(db, user).preview, raw)


@router.post(
    "",
    response_model=RestoreBatch,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401),
    openapi_extra=_BODY,
    summary="Add the chosen kinds of records (the same file again changes nothing)",
)
async def apply(
    request: Request,
    response: Response,
    categories: list[str] = Query(description="notes, stories, bookmarks, applications"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RestoreBatch:
    raw = await _read(request)
    batch, created = await run_in_threadpool(Restore(db, user).apply, raw, categories)
    if not created:
        response.status_code = status.HTTP_200_OK
    return batch


@router.get(
    "/batches", response_model=list[RestoreBatch], responses=error_responses(401), summary="Your restores"
)
def batches(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RestoreBatch]:
    return Restore(db, user).batches()


@router.post(
    "/batches/{batch_id}/remove",
    response_model=RestoreBatch,
    responses=error_responses(401, 404),
    summary="Remove what a restore added, except anything you've edited since",
)
def remove(
    batch_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> RestoreBatch:
    return Restore(db, user).remove(batch_id)
