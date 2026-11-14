from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.roles import (
    ExperienceEdit,
    ExperienceIn,
    RequirementHistoryEntry,
    RequirementIn,
    RequirementPatch,
    RequirementSetIn,
    RevisionPreview,
    StoryLinksReviewIn,
    TargetIn,
    TargetOut,
    TargetPatch,
    TargetSummary,
)
from app.services.roles import RoleTargets

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])
_ERRORS = error_responses(400, 401, 404, 422)


def _svc(request: Request, db: Session) -> RoleTargets:
    return RoleTargets(db, judge_enabled=request.app.state.execution_backend.enabled)


@router.get("", response_model=list[TargetSummary], responses=_ERRORS, summary="Your saved target roles")
def list_targets(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TargetSummary]:
    return _svc(request, db).list(user)


@router.post(
    "",
    response_model=TargetOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Save a target role from a pasted job description (requirements are extracted by rules; no AI)",
)
def create_target(
    body: TargetIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TargetOut:
    return _svc(request, db).create(user, body)


@router.get(
    "/{target_id}", response_model=TargetOut, responses=_ERRORS, summary="A target with its preparation map"
)
def get_target(
    target_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TargetOut:
    return _svc(request, db).get(user, target_id)


@router.patch(
    "/{target_id}",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Edit, archive or select a target. Editing the description keeps requirements and attempts",
)
def update_target(
    target_id: str,
    body: TargetPatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).update(user, target_id, body)


@router.delete(
    "/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Delete a target (attempts are kept)",
)
def delete_target(
    target_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    _svc(request, db).delete(user, target_id)


@router.post(
    "/{target_id}/extract",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Find requirements in the current description again (adds new ones only)",
)
def reextract(
    target_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TargetOut:
    return _svc(request, db).reextract(user, target_id)


@router.post(
    "/{target_id}/requirements",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Add your own requirement",
)
def add_requirement(
    target_id: str,
    body: RequirementIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).add_requirement(user, target_id, body)


@router.patch(
    "/{target_id}/requirements/{requirement_id}",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Correct, re-map, remove or restore a requirement",
)
def patch_requirement(
    target_id: str,
    requirement_id: str,
    body: RequirementPatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).patch_requirement(user, target_id, requirement_id, body)


@router.post(
    "/{target_id}/requirements/revision/preview",
    response_model=RevisionPreview,
    responses=_ERRORS,
    summary="What saving this requirement set would change: changed, added, removed, unchanged (nothing saved)",
)
def preview_requirements(
    target_id: str,
    body: RequirementSetIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevisionPreview:
    return _svc(request, db).preview_requirements(user, target_id, body)


@router.put(
    "/{target_id}/requirements",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Save the requirement set against the revision you loaded (409 stale_revision if it changed)",
)
def save_requirements(
    target_id: str,
    body: RequirementSetIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).save_requirements(user, target_id, body)


@router.get(
    "/{target_id}/requirements/{requirement_id}/history",
    response_model=list[RequirementHistoryEntry],
    responses=_ERRORS,
    summary="Every recorded version of a requirement, removed ones too",
)
def requirement_history(
    target_id: str,
    requirement_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RequirementHistoryEntry]:
    return _svc(request, db).requirement_history(user, target_id, requirement_id)


@router.post(
    "/{target_id}/experience/{entry_id}/requirements/{requirement_id}/reuse",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Use this story for the requirement's current wording (recorded as a reuse)",
)
def reuse_story(
    target_id: str,
    entry_id: str,
    requirement_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).reuse_story(user, target_id, entry_id, requirement_id)


@router.post(
    "/{target_id}/experience/{entry_id}/review",
    response_model=TargetOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Refresh a story's requirement links to the version you reviewed, or keep them as linked",
)
def review_story_links(
    target_id: str,
    entry_id: str,
    body: StoryLinksReviewIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).review_story_links(user, target_id, entry_id, body)


@router.post(
    "/{target_id}/actions/{action_id}/requirements/{requirement_id}/reuse",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Use this accepted improvement for the requirement's current wording (recorded as a reuse)",
)
def reuse_action(
    target_id: str,
    action_id: str,
    requirement_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).reuse_action(user, target_id, action_id, requirement_id)


@router.post(
    "/{target_id}/experience",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Add one of your own examples",
)
def add_experience(
    target_id: str,
    body: ExperienceIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).add_experience(user, target_id, body)


@router.put(
    "/{target_id}/experience/{entry_id}",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Edit one of your examples",
)
def edit_experience(
    target_id: str,
    entry_id: str,
    body: ExperienceEdit,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).patch_experience(user, target_id, entry_id, body)


@router.delete(
    "/{target_id}/experience/{entry_id}",
    response_model=TargetOut,
    responses=_ERRORS,
    summary="Delete one of your examples",
)
def delete_experience(
    target_id: str,
    entry_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetOut:
    return _svc(request, db).delete_experience(user, target_id, entry_id)
