"""Names you don't want anywhere outside the app (Volume 15, prompt 7; docs/PRIVACY.md, "Names you
listed"). Private to the account; the packet, shares and every coach-context preview replace them."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.listed_names import ListedNameIn, ListedNameOut, ListedNamesOut
from app.services.listed_names import MAX_NAMES, PLACEHOLDER, ListedNames

router = APIRouter(prefix="/api/v1/me/listed-names", tags=["listed names"])

NOTE = (
    "Each of these is replaced with [name] in what leaves CodeCoach: the practice packet, a shared "
    "answer, and what the coach or interviewer reads. Your own notes, answers and stories keep them. "
    "Only names on this list are found; other names aren't."
)


def _out(store: ListedNames) -> ListedNamesOut:
    return ListedNamesOut(
        items=[ListedNameOut.model_validate(r, from_attributes=True) for r in store.all()],
        max=MAX_NAMES,
        placeholder=PLACEHOLDER,
        note=NOTE,
    )


@router.get("", response_model=ListedNamesOut, responses=error_responses(401), summary="Your listed names")
def list_names(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ListedNamesOut:
    return _out(ListedNames(db, user))


@router.post(
    "",
    response_model=ListedNamesOut,
    responses=error_responses(400, 401, 422),
    summary="Add a name (the same name again, in any letter case, is the one already listed)",
)
def add_name(
    body: ListedNameIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ListedNamesOut:
    store = ListedNames(db, user)
    store.add(body.name)
    return _out(store)


@router.patch(
    "/{name_id}",
    response_model=ListedNamesOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Change a name",
)
def change_name(
    name_id: str, body: ListedNameIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ListedNamesOut:
    store = ListedNames(db, user)
    store.update(name_id, body.name)
    return _out(store)


@router.delete("/{name_id}", status_code=204, responses=error_responses(401, 404), summary="Remove a name")
def remove_name(
    name_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    ListedNames(db, user).remove(name_id)
    return Response(status_code=204)
