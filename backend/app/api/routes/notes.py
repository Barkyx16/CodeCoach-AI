"""The personal practice notebook (private to its owner)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.notes import (
    DeletedOut,
    KeyPoints,
    NoteIn,
    NoteOut,
    NotePage,
    NotePatch,
    NoteStatus,
    SourceType,
)
from app.services.notes import Notebook

router = APIRouter(prefix="/api/v1/me/notes", tags=["notes"])


@router.get(
    "", response_model=NotePage, responses=error_responses(401, 422), summary="Search and filter your notes"
)
def list_notes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = Query(
        default=None, max_length=120, description="Words in the title, text, reflection or tags"
    ),
    career: str | None = Query(default=None, max_length=64),
    source_type: SourceType | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=32),
    source_id: str | None = Query(
        default=None, max_length=120, description="Notes on one item (with source_type)"
    ),
    status: NoteStatus = Query(default="active"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> NotePage:
    return Notebook(db).search(
        user,
        q=q,
        career=career,
        source_type=source_type,
        tag=tag,
        source_id=source_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=NoteOut,
    status_code=201,
    responses=error_responses(400, 401, 404, 422),
    summary="Create a note, optionally from a question, problem, lesson or interview",
)
def create_note(
    body: NoteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NoteOut:
    return Notebook(db).create(user, body)


@router.get("/{note_id}", response_model=NoteOut, responses=error_responses(401, 404), summary="One note")
def get_note(note_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> NoteOut:
    return Notebook(db).get(user, note_id)


@router.patch(
    "/{note_id}",
    response_model=NoteOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Save changes (text changes need base_revision; 409 note_conflict carries the current note)",
)
def update_note(
    note_id: str, body: NotePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NoteOut:
    return Notebook(db).update(user, note_id, body)


@router.delete(
    "/{note_id}",
    response_model=DeletedOut,
    responses=error_responses(401, 404),
    summary="Delete a note (restorable for 10 minutes, then purged)",
)
def delete_note(
    note_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DeletedOut:
    return Notebook(db).delete(user, note_id)


@router.post(
    "/{note_id}/restore",
    response_model=NoteOut,
    responses=error_responses(401, 404),
    summary="Undo a delete within the window",
)
def restore_note(
    note_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NoteOut:
    return Notebook(db).restore(user, note_id)


@router.post(
    "/{note_id}/key-points",
    response_model=KeyPoints,
    responses=error_responses(401, 404),
    summary="Suggest key points from the note's own sentences (no AI model; nothing is saved)",
)
def suggest_key_points(
    note_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> KeyPoints:
    return Notebook(db).key_points(user, note_id)
