from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class DataCategoryOut(APIModel):
    key: str
    group: Literal["work", "sharing", "account"] = Field(
        description="Your work; sharing and reports; your account and sign-in"
    )
    label: str
    count: int = Field(ge=0, description="How many rows of yours; nothing's content is read to count them")
    note: str | None = None


class DataSummaryOut(APIModel):
    categories: list[DataCategoryOut]
