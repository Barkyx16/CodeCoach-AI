"""The optional first-session introduction (welcome choice, guided tour, career intros)."""

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.onboarding import OnboardingOut, OnboardingUpdate
from app.services.onboarding import Onboarding

router = APIRouter(prefix="/api/v1/me/onboarding", tags=["onboarding"])


@router.get(
    "",
    response_model=OnboardingOut,
    responses=error_responses(401),
    summary="Where you are in the introduction, and a real starter activity for your career",
)
def get_onboarding(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OnboardingOut:
    return Onboarding(db, user).get()


@router.patch(
    "",
    response_model=OnboardingOut,
    responses=error_responses(401, 422),
    summary="Record a choice about the introduction (never answer text; never practice progress)",
)
def update_onboarding(
    body: OnboardingUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OnboardingOut:
    try:
        return Onboarding(db, user).update(body)
    except IntegrityError:  # two first writes raced to create the row: apply this one to it
        db.rollback()
        return Onboarding(db, user).update(body)
