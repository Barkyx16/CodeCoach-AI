"""The interview-day kit for one of your recorded interview events."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.kits import KitOut, KitUpdate
from app.services.kits import Kits

router = APIRouter(prefix="/api/v1/me/applications", tags=["applications"])


def _private(response: Response) -> None:
    # Meeting links and notes can be sensitive: never cached.
    response.headers["Cache-Control"] = "no-store"


@router.get(
    "/{app_id}/events/{event_id}/kit",
    response_model=KitOut,
    responses=error_responses(401, 404),
    summary="The interview-day kit (suggestions only, until you change something)",
)
def get_kit(
    app_id: str,
    event_id: str,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KitOut:
    _private(response)
    return Kits(db, user).get(app_id, event_id)


@router.put(
    "/{app_id}/events/{event_id}/kit",
    response_model=KitOut,
    responses=error_responses(401, 404, 422),
    summary="Save changes to the kit (lists are saved in the order given)",
)
def put_kit(
    app_id: str,
    event_id: str,
    body: KitUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KitOut:
    _private(response)
    return Kits(db, user).update(app_id, event_id, body)
