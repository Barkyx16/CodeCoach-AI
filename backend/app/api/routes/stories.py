"""The story bank: your own STAR stories for behavioral interviews (private to you)."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.stories import (
    Competency,
    StoryAssistIn,
    StoryAssistOut,
    StoryCreate,
    StoryOut,
    StoryRestoreIn,
    StoryRevisionOut,
    StorySummary,
    StoryUpdate,
)
from app.services.stories import Stories

router = APIRouter(prefix="/api/v1/me/stories", tags=["stories"])


@router.get("", response_model=list[StorySummary], responses=error_responses(401), summary="Your stories")
def list_stories(
    archived: bool = Query(default=False, description="true: only archived stories"),
    q: str = Query(default="", max_length=200, description="Words that must all appear in the story"),
    competency: Competency | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StorySummary]:
    return Stories(db).all(user, archived, q, competency)


@router.post(
    "",
    response_model=StoryOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 422),
    summary="Write a new story",
)
def create_story(
    body: StoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StoryOut:
    return Stories(db).create(user, body)


@router.get("/{story_id}", response_model=StoryOut, responses=error_responses(401, 404), summary="One story")
def get_story(
    story_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StoryOut:
    return Stories(db).get(user, story_id)


@router.patch(
    "/{story_id}",
    response_model=StoryOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Save changes (a new revision; 409 stale_revision if it changed since you opened it)",
)
def update_story(
    story_id: str, body: StoryUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StoryOut:
    return Stories(db).update(user, story_id, body)


@router.post(
    "/{story_id}/archive", response_model=StoryOut, responses=error_responses(401, 404), summary="Archive"
)
def archive_story(
    story_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StoryOut:
    return Stories(db).set_archived(user, story_id, True)


@router.post(
    "/{story_id}/unarchive", response_model=StoryOut, responses=error_responses(401, 404), summary="Unarchive"
)
def unarchive_story(
    story_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StoryOut:
    return Stories(db).set_archived(user, story_id, False)


@router.delete(
    "/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404),
    summary="Delete a story and its revisions (answers that rehearsed it are kept)",
)
def delete_story(
    story_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    Stories(db).delete(user, story_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{story_id}/revisions",
    response_model=list[StoryRevisionOut],
    responses=error_responses(401, 404),
    summary="Every saved version, newest first",
)
def story_revisions(
    story_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[StoryRevisionOut]:
    return Stories(db).revisions(user, story_id)


@router.post(
    "/{story_id}/revisions/{revision}/restore",
    response_model=StoryOut,
    responses=error_responses(401, 404, 409),
    summary="Bring back an earlier version (as a new revision; nothing is deleted)",
)
def restore_revision(
    story_id: str,
    revision: int,
    body: StoryRestoreIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryOut:
    return Stories(db).restore(user, story_id, revision, body.expected_revision)


@router.post(
    "/{story_id}/assist",
    response_model=StoryAssistOut,
    responses=error_responses(401, 404, 422),
    summary="Built-in writing check: proposals to review and questions (rules, not AI; nothing is saved)",
)
def assist_story(
    story_id: str, body: StoryAssistIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StoryAssistOut:
    return Stories(db).assist(user, story_id, body)
