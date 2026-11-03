"""Whiteboard practice: prompts, drafts and evaluated attempts."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel
from app.whiteboard.diagram import Diagram


class WhiteboardPromptRequirement(APIModel):
    id: str
    text: str


class WhiteboardPrompt(APIModel):
    id: str
    version: int
    title: str
    objective: str
    brief: str
    requirements: list[WhiteboardPromptRequirement]


class WhiteboardPromptList(APIModel):
    prompts: list[WhiteboardPrompt]
    note: str = Field(description="What's offered for this career, and what isn't yet")


class WhiteboardDraftIn(APIModel):
    diagram: Diagram
    explanation: str = Field(default="", max_length=4000)
    expected_revision: int = Field(ge=0, description="0 for the first save")


class WhiteboardDraftOut(APIModel):
    prompt_id: str
    diagram: Diagram
    explanation: str
    revision: int
    updated_at: datetime | None
    differs_from_last_attempt: bool = Field(
        description="True if this draft has changed since your last evaluated attempt"
    )


class WhiteboardAttemptIn(APIModel):
    diagram: Diagram
    explanation: str = Field(
        max_length=4000, description="Why you made at least one choice, in your words (needed first)"
    )


class WhiteboardAttemptOut(APIModel):
    id: str
    prompt_id: str
    prompt_version: int
    rubric_version: int
    diagram: Diagram
    digest: str
    explanation: str
    feedback: dict
    created_at: datetime


class WhiteboardAttemptSummary(APIModel):
    id: str
    prompt_version: int
    rubric_version: int
    digest: str
    addressed: int
    total: int
    created_at: datetime
