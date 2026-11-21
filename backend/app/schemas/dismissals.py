"""Suggestions dismissed with "Not now", kept with the account (docs/FOLLOW_UPS.md, "Not now")."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class DismissIn(APIModel):
    key: str = Field(
        min_length=1,
        max_length=200,
        description='The suggestion: "question-follow-up:<track>/<from>><to>", "problem-follow-up:<from>><to>" '
        'or "plan-change:<track>@<version>"',
    )
    offered_on: str | None = Field(default=None, max_length=200, description="The page it was offered on")


class DismissBatch(APIModel):
    items: list[DismissIn] = Field(min_length=1, max_length=200)


class Dismissed(APIModel):
    key: str
    kind: Literal["question_follow_up", "problem_follow_up", "plan_change"]
    label: str = Field(description="What it was, in plain words")
    note: str | None = Field(
        default=None, description="What offering it again will do, when that isn't simply offering it"
    )
    offered_on: str | None = None
    dismissed_at: datetime


class DismissedList(APIModel):
    items: list[Dismissed]
