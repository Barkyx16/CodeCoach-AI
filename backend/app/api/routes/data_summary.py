"""What's saved to your account, as counts (docs/YOUR_DATA.md). Export and deletion stay where they are."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.data_summary import DataCategoryOut, DataSummaryOut
from app.services.data_summary import data_summary

router = APIRouter(tags=["privacy"])


@router.get(
    "/api/v1/me/data-summary",
    response_model=DataSummaryOut,
    responses=error_responses(401),
    summary="What's saved to your account, as counts",
    response_description="One count per kind of record you have; no content, titles or amounts",
)
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DataSummaryOut:
    return DataSummaryOut(categories=[DataCategoryOut(**row) for row in data_summary(db, user)])
