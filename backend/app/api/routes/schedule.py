"""Your schedule: existing activities placed on dates and times you choose, and calendar files."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.models import User
from app.schemas.common import error_responses
from app.schemas.schedule import (
    EntryIn,
    EntryMove,
    EntryOut,
    SchedulableOut,
    ScheduleSettingsIn,
    ScheduleSettingsOut,
)
from app.services.schedule import Schedule

router = APIRouter(prefix="/api/v1/me/schedule", tags=["schedule"])


@router.get(
    "", response_model=list[EntryOut], responses=error_responses(400, 401), summary="Entries in a date range"
)
def list_entries(
    from_: date = Query(alias="from"),
    to: date = Query(),
    include_cancelled: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EntryOut]:
    return Schedule(db, user).between(from_, to, include_cancelled)


@router.post(
    "",
    response_model=EntryOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Schedule an activity (a retry with the same client_request_id returns the first, 200)",
)
def create_entry(
    body: EntryIn, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> EntryOut:
    out, created = Schedule(db, user).create(body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return out


@router.get(
    "/schedulable",
    response_model=list[SchedulableOut],
    responses=error_responses(401),
    summary="What you could schedule",
)
def schedulable(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SchedulableOut]:
    return Schedule(db, user).schedulable()


@router.get(
    "/settings",
    response_model=ScheduleSettingsOut,
    responses=error_responses(401),
    summary="Time zone and reminders",
)
def get_settings(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScheduleSettingsOut:
    return Schedule(db, user).settings()


@router.put(
    "/settings",
    response_model=ScheduleSettingsOut,
    responses=error_responses(400, 401, 422),
    summary="Change them",
)
def put_settings(
    body: ScheduleSettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ScheduleSettingsOut:
    return Schedule(db, user).save_settings(body)


@router.get(
    "/export.ics",
    responses={
        **error_responses(400, 401, 404),
        200: {"content": {"text/calendar": {}}, "description": "An iCalendar file"},
    },
    summary="Download selected entries (ids) or a date range as an .ics file",
)
def export_ics(
    ids: str | None = Query(default=None, description="Comma-separated entry ids"),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    body = Schedule(db, user).ics(
        [i for i in (ids or "").split(",") if i] or None, from_, to, settings.app_base_url
    )
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="codecoach-schedule.ics"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{entry_id}", response_model=EntryOut, responses=error_responses(401, 404), summary="One entry")
def get_entry(
    entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> EntryOut:
    return Schedule(db, user).get(entry_id)


@router.patch(
    "/{entry_id}",
    response_model=EntryOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Move it",
)
def move_entry(
    entry_id: str, body: EntryMove, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> EntryOut:
    return Schedule(db, user).move(entry_id, body)


@router.post(
    "/{entry_id}/cancel", response_model=EntryOut, responses=error_responses(401, 404), summary="Cancel it"
)
def cancel_entry(
    entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> EntryOut:
    return Schedule(db, user).cancel(entry_id)
