"""Communication drills."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey


class DrillOut(APIModel):
    id: str
    title: str
    objective: str
    looks_for: list[str]
    target_seconds: int | None
    prompt: str = Field(description="For your career")
    attempts: int


class DrillAttemptIn(APIModel):
    text: str = Field(
        min_length=1, max_length=4000, description="What you said (a transcript you checked) or typed"
    )
    source: Literal["typed", "voice"] = "typed"
    spoken_seconds: int | None = Field(
        default=None, ge=1, le=900, description="Only when the browser timed a recording"
    )
    client_request_id: OptionalKey = Field(default=None, max_length=64)


class DrillAttemptOut(APIModel):
    id: str
    drill_id: str
    prompt: str
    text: str
    source: Literal["typed", "voice"]
    spoken_seconds: int | None
    rubric_version: int
    feedback: dict
    compared_with_previous: list[str] | None = Field(
        description="What changed since your previous attempt at this drill"
    )
    created_at: datetime
