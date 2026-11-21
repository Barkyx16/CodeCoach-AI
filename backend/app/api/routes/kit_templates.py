"""Your kit templates: checklist items and questions to start another interview's kit from (docs/TEMPLATES.md)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.kit_templates import KitTemplateCreate, KitTemplateOut, KitTemplateSummary, KitTemplateUpdate
from app.services.kit_templates import KitTemplates

router = APIRouter(prefix="/api/v1/me/kit-templates", tags=["kit-templates"])


@router.get(
    "", response_model=list[KitTemplateSummary], responses=error_responses(401), summary="Your kit templates"
)
def mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[KitTemplateSummary]:
    return KitTemplates(db, user).mine()


@router.post(
    "",
    response_model=KitTemplateOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 409, 422),
    summary="Save a template (only the text you send: never done states, links, notes or outcomes)",
)
def create(
    body: KitTemplateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> KitTemplateOut:
    return KitTemplates(db, user).create(body)


@router.get(
    "/{template_id}",
    response_model=KitTemplateOut,
    responses=error_responses(401, 404),
    summary="One template",
)
def get_one(
    template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> KitTemplateOut:
    return KitTemplates(db, user).get(template_id)


@router.patch(
    "/{template_id}",
    response_model=KitTemplateOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Rename it or change its items (revision-checked; kits made from it don't change)",
)
def update(
    template_id: str,
    body: KitTemplateUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KitTemplateOut:
    return KitTemplates(db, user).update(template_id, body)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404),
    summary="Delete (kits made from it keep their items)",
)
def delete(
    template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    KitTemplates(db, user).delete(template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
