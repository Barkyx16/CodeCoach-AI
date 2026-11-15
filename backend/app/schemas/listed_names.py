"""A learner's private list of names, replaced wherever text leaves the app (docs/PRIVACY.md)."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class ListedNameIn(APIModel):
    name: str = Field(
        min_length=1,
        max_length=200,
        description="A name as you'd type it (spaces and letter case don't matter)",
    )


class ListedNameOut(APIModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class ListedNamesOut(APIModel):
    items: list[ListedNameOut]
    max: int = Field(description="How many the list holds")
    placeholder: str = Field(description="What each one becomes in what leaves the app")
    note: str
