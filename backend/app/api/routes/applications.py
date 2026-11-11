"""Private application tracker: your real applications, stages, interview events and links."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationEventIn,
    ApplicationOut,
    ApplicationStageIn,
    ApplicationSummary,
    ApplicationUpdate,
)
from app.schemas.common import error_responses
from app.schemas.schedule import PrepShiftIn, PrepShiftOut, PrepShiftResult
from app.services.applications import Applications
from app.services.schedule import Schedule

router = APIRouter(prefix="/api/v1/me/applications", tags=["applications"])


@router.get(
    "", response_model=list[ApplicationSummary], responses=error_responses(401), summary="Your applications"
)
def list_applications(
    archived: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationSummary]:
    return Applications(db, user).all(archived)


@router.post(
    "",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 422),
    summary="Record an application (a retry with the same client_request_id returns the first, 200)",
)
def create_application(
    body: ApplicationCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    out, created = Applications(db, user).create(body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return out


@router.get(
    "/{app_id}", response_model=ApplicationOut, responses=error_responses(401, 404), summary="One application"
)
def get_application(
    app_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApplicationOut:
    return Applications(db, user).get(app_id)


@router.patch(
    "/{app_id}",
    response_model=ApplicationOut,
    responses=error_responses(400, 401, 404, 409, 422, 428),
    summary="Edit details (history keeps the title and employer as they were)",
)
def update_application(
    app_id: str,
    body: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    return Applications(db, user).update(app_id, body)


@router.post(
    "/{app_id}/stage",
    response_model=ApplicationOut,
    responses=error_responses(401, 404, 422),
    summary="Move to a stage (recorded in the history; the same stage again changes nothing)",
)
def set_stage(
    app_id: str,
    body: ApplicationStageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    return Applications(db, user).set_stage(app_id, body)


@router.post(
    "/{app_id}/archive", response_model=ApplicationOut, responses=error_responses(401, 404), summary="Archive"
)
def archive(
    app_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApplicationOut:
    return Applications(db, user).set_archived(app_id, True)


@router.post(
    "/{app_id}/unarchive",
    response_model=ApplicationOut,
    responses=error_responses(401, 404),
    summary="Unarchive",
)
def unarchive(
    app_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApplicationOut:
    return Applications(db, user).set_archived(app_id, False)


@router.put(
    "/{app_id}/stories/{story_id}",
    response_model=ApplicationOut,
    responses=error_responses(401, 404, 409),
    summary="Link one of your stories (linking a linked one changes nothing)",
)
def link_story(
    app_id: str, story_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApplicationOut:
    return Applications(db, user).link_story(app_id, story_id, True)


@router.delete(
    "/{app_id}/stories/{story_id}",
    response_model=ApplicationOut,
    responses=error_responses(401, 404),
    summary="Unlink a story (the story itself stays; unlinking one that isn't linked changes nothing)",
)
def unlink_story(
    app_id: str, story_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApplicationOut:
    return Applications(db, user).link_story(app_id, story_id, False)


@router.delete(
    "/{app_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(401, 404), summary="Delete"
)
def delete_application(
    app_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    Applications(db, user).delete(app_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{app_id}/events",
    response_model=ApplicationOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Add an interview or other event (each interview is its own event)",
)
def add_event(
    app_id: str,
    body: ApplicationEventIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    return Applications(db, user).add_event(app_id, body)


@router.put(
    "/{app_id}/events/{event_id}",
    response_model=ApplicationOut,
    responses=error_responses(400, 401, 404, 422),
    summary="Edit an event",
)
def update_event(
    app_id: str,
    event_id: str,
    body: ApplicationEventIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    return Applications(db, user).update_event(app_id, event_id, body)


@router.delete(
    "/{app_id}/events/{event_id}",
    response_model=ApplicationOut,
    responses=error_responses(401, 404),
    summary="Remove an event",
)
def delete_event(
    app_id: str, event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApplicationOut:
    return Applications(db, user).delete_event(app_id, event_id)


@router.get(
    "/{app_id}/events/{event_id}/prep",
    response_model=PrepShiftOut,
    responses=error_responses(401, 404),
    summary="Preview: what would happen to this interview's preparation times",
    description="Read-only. Fixed entries stay; entries that follow the interview get a proposed time "
    "(the same elapsed time before it) when both exact times are known.",
)
def prep_preview(
    app_id: str, event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PrepShiftOut:
    return Schedule(db, user).prep_preview(app_id, event_id)


@router.post(
    "/{app_id}/events/{event_id}/prep/shift",
    response_model=PrepShiftResult,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Move the chosen preparation times as previewed (all or none)",
    description="409 interview_changed if the interview moved again since the preview; 409 "
    "prep_not_movable (nothing moved) if a chosen entry changed or can't move. A resend after a "
    "lost response reports those entries as already aligned (nothing moves twice).",
)
def prep_shift(
    app_id: str,
    event_id: str,
    body: PrepShiftIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PrepShiftResult:
    return Schedule(db, user).prep_shift(app_id, event_id, body)
