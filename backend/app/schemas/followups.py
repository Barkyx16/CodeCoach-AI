"""Reviewed follow-up questions (Volume 12, prompt 4; docs/FOLLOW_UPS.md)."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.conditions import AttemptConditions


class FollowUpQuestion(APIModel):
    track: str
    question_id: str
    title: str
    version: int = Field(description="The question's current version")
    objective: str = Field(description="What it shares with the question you practised")
    difference: str = Field(description="How it differs")
    exposure: str = Field(
        description="'Not previously attempted in this app', or how many times you answered it here. "
        "Never 'new to you': practice elsewhere isn't known."
    )
    attempts: int = Field(description="Your answers to it in this app")


class FollowUpAnswered(APIModel):
    """A follow-up you answered, kept beside the answer it followed: its own record and score."""

    answer_id: str
    track: str
    question_id: str
    title: str
    score: int
    rating: str
    evidence_level: Literal["sufficient", "insufficient", "unknown"]
    content_version: int
    created_at: datetime
    follows_up_answer_id: str
    conditions: AttemptConditions | None = None


class FollowUpOut(APIModel):
    status: Literal["offered", "not_yet", "none"] = Field(
        description="offered: a reviewed follow-up is available; not_yet: practise this question more "
        "first; none: no reviewed follow-up (or only retired ones)"
    )
    message: str
    threshold: int = Field(description="Answers long enough to score before a follow-up is offered")
    scored_answers: int = Field(description="Your answers to this question long enough to score")
    offers: list[FollowUpQuestion]
    answered: list[FollowUpAnswered] = Field(description="Follow-ups you answered after this question")
