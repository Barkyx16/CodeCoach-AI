"""Mock-interview contracts.

`InterviewerReply` and `InterviewEvaluation` double as the structured-output schemas the AI
interviewer must fill, so every provider (offline or Claude) returns the same shapes.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models import Difficulty, InterviewPhase, InterviewStatus, TurnRole
from app.schemas.common import APIModel

PHASE_GUIDE: dict[InterviewPhase, str] = {
    InterviewPhase.CLARIFY: "Restate the problem and ask clarifying questions about inputs, outputs and edge cases.",
    InterviewPhase.APPROACH: "Explain your approach out loud before writing code, including alternatives.",
    InterviewPhase.CODING: "Write the solution in the editor and narrate key decisions.",
    InterviewPhase.COMPLEXITY: "State the time and space complexity and justify them.",
    InterviewPhase.WRAP_UP: "Walk through test cases and edge cases, then wrap up.",
}

RubricDimension = Literal[
    "problem_solving", "communication", "code_quality", "complexity_analysis", "testing"
]
RUBRIC_DIMENSIONS: tuple[RubricDimension, ...] = (
    "problem_solving",
    "communication",
    "code_quality",
    "complexity_analysis",
    "testing",
)


class InterviewStart(APIModel):
    problem_slug: str | None = Field(
        default=None, description="Omit to let CodeCoach pick a recommended problem"
    )
    duration_minutes: int = Field(default=30, ge=10, le=60)


class InterviewMessage(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    code: str | None = Field(default=None, max_length=20_000, description="Current editor contents")

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v


class InterviewFinish(APIModel):
    code: str | None = Field(default=None, max_length=20_000)


class InterviewerReply(BaseModel):
    """What the interviewer says next. Schema for the AI provider."""

    message: str = Field(description="The interviewer's next message: one question or prompt, conversational")
    advance_phase: bool = Field(
        description="True when the candidate has covered the current phase well enough to move on"
    )


class RubricScore(BaseModel):
    dimension: RubricDimension
    score: int = Field(ge=1, le=4, description="1 = needs work, 2 = developing, 3 = solid, 4 = strong")
    evidence: str = Field(description="A specific observation from the transcript or code")


class InterviewEvaluation(BaseModel):
    """End-of-interview feedback. Schema for the AI provider."""

    scores: list[RubricScore] = Field(description="Exactly one score per rubric dimension")
    overall: Literal["needs_work", "developing", "solid", "strong"]
    summary: str
    strengths: list[str]
    improvements: list[str]
    confidence: Literal["low", "medium", "high"]


class TurnOut(APIModel):
    seq: int
    role: TurnRole
    phase: InterviewPhase
    content: str
    created_at: datetime


class InterviewProblem(APIModel):
    slug: str
    title: str
    difficulty: Difficulty


class InterviewOut(APIModel):
    id: str
    status: InterviewStatus
    phase: InterviewPhase | None
    phase_index: int = Field(description="0-based position of the phase in the arc")
    phase_guide: str | None
    problem: InterviewProblem
    duration_seconds: int
    started_at: datetime
    deadline_at: datetime
    ended_at: datetime | None
    seconds_remaining: int
    candidate_turns_remaining: int
    provider: str | None
    turns: list[TurnOut]
    final_code: str | None
    evaluation: InterviewEvaluation | None


class InterviewSummary(APIModel):
    id: str
    status: InterviewStatus
    problem: InterviewProblem
    started_at: datetime
    ended_at: datetime | None
    overall: str | None
    average_score: float | None
