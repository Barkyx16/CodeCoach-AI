from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

RecentType = Literal["interview", "note", "story", "kit", "application", "offer_comparison"]


class RecentItem(APIModel):
    type: RecentType
    id: str = Field(description="The record's id; for a kit, its event's id")
    parent_id: str | None = Field(default=None, description="For a kit: its application's id")
    title: str
    state: Literal["in_progress", "time_up", "finished", "expired", "ended_early"] | None = Field(
        default=None, description="Interviews only"
    )
    detail: str | None = Field(
        default=None, description="A short status: an application's stage, a kit's date"
    )
    at: datetime
    at_meaning: Literal["saved", "started", "finished"] = Field(
        description="saved: last saved to your account; started/finished: the session's own times. "
        "Nothing here means 'opened'."
    )


class RecentWorkOut(APIModel):
    items: list[RecentItem]
    unavailable: list[str] = Field(
        description="Kinds of record that couldn't be read just now; the rest are listed"
    )
