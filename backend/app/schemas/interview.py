"""Mock-interview contracts.

`InterviewerReply` and `InterviewEvaluation` double as the structured-output schemas the AI
interviewer must fill, so every provider (offline or Claude) returns the same shapes.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models import Difficulty, InterviewPhase, InterviewStatus, TurnRole
from app.schemas.careers import AnswerOut
from app.schemas.common import APIModel

InterviewKind = Literal["coding", "questions"]
AnswerSource = Literal["typed", "voice", "mixed"]
EngagementState = Literal["following", "more_detail", "explore_further", "not_enough_evidence"]

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
    kind: InterviewKind = Field(
        default="coding",
        description="coding: one problem with an AI interviewer. questions: five of a career's questions",
    )
    problem_slug: str | None = Field(
        default=None, description="coding: omit to let CodeCoach pick a recommended problem"
    )
    track: str | None = Field(default=None, description="questions: the career (default: your own)")
    difficulty: Difficulty | None = Field(default=None, description="questions: default easy")
    question_ids: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=5,
        description="questions: ask exactly these questions of the career, in this order (a targeted round)",
    )
    purpose: Literal["practice", "baseline"] = Field(
        default="practice",
        description="questions: baseline asks three short questions (knowledge, behavioral, scenario) to "
        "start a practice plan",
    )
    duration_minutes: int = Field(default=30, ge=10, le=60)
    format: Literal["mixed", "behavioral", "situational", "technical", "panel"] = Field(
        default="mixed",
        description="questions: the interview format (see GET /interviews/formats). Can't change once started.",
    )


class FollowupAnswer(APIModel):
    answer: str = Field(min_length=1, max_length=3000)
    source: AnswerSource = Field(default="typed")


class SpeakerOut(APIModel):
    id: str
    title: str = Field(description="A simulated role, never a real person or employer")
    objective: str


class FollowupOut(APIModel):
    question_index: int
    detail: str = Field(description="The detail asked about, e.g. result or ownership")
    question: str
    speaker: SpeakerOut | None
    status: Literal["pending", "answered", "skipped"]
    answer: str | None = None
    covered: bool | None = Field(
        default=None, description="Whether the reply supplied the detail (simple check)"
    )


class FormatSlot(APIModel):
    position: int
    speaker: SpeakerOut | None
    kind_label: str


class FormatOption(APIModel):
    id: Literal["mixed", "behavioral", "situational", "technical", "panel"]
    title: str
    practices: str
    available: bool
    unavailable_reason: str | None
    follow_ups: int = Field(description="Most follow-up questions this format may ask")
    roles: list[SpeakerOut]
    structure: list[FormatSlot] = Field(
        description="Who asks what, in order (no questions or answers revealed)"
    )


class RoundFormatOut(APIModel):
    id: Literal["mixed", "behavioral", "situational", "technical", "panel"]
    title: str
    version: str
    rubric_version: str
    roles: list[SpeakerOut]
    followups_used: int
    followups_max: int
    pending_followup: FollowupOut | None


class RoundAnswer(APIModel):
    question_index: int = Field(ge=0, description="Must be the question currently being asked")
    answer: str = Field(min_length=1, max_length=6000)
    source: AnswerSource = Field(
        default="typed",
        description="How the text was produced. Recorded for review only; it never affects scoring",
    )

    @field_validator("answer")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer must not be blank")
        return v


class RoundSkip(APIModel):
    question_index: int = Field(ge=0)


class Engagement(APIModel):
    """A simulated interviewer's read of one answer, built only from what the answer contains."""

    state: EngagementState
    label: str = Field(description="e.g. 'Looking for more detail'")
    reason: str = Field(description="One actionable sentence that refers to the answer")
    evidence: list[str] = Field(description="The signals found in (or missing from) the answer")


class InterviewMessage(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    code: str | None = Field(default=None, max_length=20_000, description="Current editor contents")
    source: AnswerSource = Field(
        default="typed", description="How the text was produced. Recorded for review only"
    )

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
    phase: InterviewPhase | None = Field(description="Coding interviews only")
    content: str
    created_at: datetime
    question_index: int | None = None
    source: AnswerSource | None = Field(default=None, description="Candidate turns: typed or voice")
    skipped: bool = False
    engagement: Engagement | None = Field(default=None, description="Candidate turns: simulated engagement")


class RoundQuestion(APIModel):
    index: int
    id: str
    title: str
    prompt: str
    kind: str
    difficulty: Difficulty
    status: Literal["pending", "current", "answered", "skipped"]
    answer: AnswerOut | None = None
    speaker: SpeakerOut | None = Field(default=None, description="Panel interviews: who asks this question")
    followup: FollowupOut | None = None


class RoundSummary(APIModel):
    answered: int
    skipped: int
    unanswered: int = Field(description="Never reached, e.g. the interview ended early or time ran out")
    average_score: int | None = Field(description="Mean score of answered questions; null if none")
    focus: list[str] = Field(description="Rubric points missed most often, most frequent first")


class InterviewProblem(APIModel):
    slug: str
    title: str
    difficulty: Difficulty


class InterviewOut(APIModel):
    id: str
    kind: InterviewKind
    status: InterviewStatus
    phase: InterviewPhase | None
    phase_index: int = Field(description="0-based position of the phase in the arc")
    phase_guide: str | None
    problem: InterviewProblem | None = Field(description="Coding interviews only")
    track: str | None = Field(default=None, description="Question rounds: the career")
    career_title: str | None = None
    questions: list[RoundQuestion] = Field(description="Question rounds only; empty for coding interviews")
    round_summary: RoundSummary | None = Field(default=None, description="Question rounds only")
    round_format: RoundFormatOut | None = Field(default=None, description="Question rounds only")
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
    kind: InterviewKind
    status: InterviewStatus
    problem: InterviewProblem | None
    track: str | None = None
    career_title: str | None = None
    started_at: datetime
    ended_at: datetime | None
    overall: str | None
    average_score: float | None
