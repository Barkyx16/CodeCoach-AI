from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.progress import ProgressOut, Recommendation
from app.services.account import export_user_data
from app.services.progress import ProgressService

router = APIRouter(prefix="/api/v1/me", tags=["progress"])


@router.get(
    "/progress",
    response_model=ProgressOut,
    responses=error_responses(401),
    summary="Your aggregate progress and analytics",
)
def progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProgressOut:
    return ProgressService(db).progress(user)


@router.get(
    "/recommendations",
    response_model=list[Recommendation],
    responses=error_responses(401),
    summary="Personalized next problems, each with a reason",
)
def recommendations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[Recommendation]:
    return ProgressService(db).recommend(user, limit=limit)


@router.get(
    "/export",
    responses=error_responses(401),
    summary="Download all of your data as JSON",
    response_description="A JSON document with your profile, submissions, AI feedback, interviews and activity",
)
def export(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(
        export_user_data(db, user),
        headers={
            "Content-Disposition": 'attachment; filename="codecoach-data.json"',
            "Cache-Control": "no-store",
        },
    )
