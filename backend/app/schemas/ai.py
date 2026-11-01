"""Request/response contracts for the AI coach.

The response models double as the *structured output schemas* sent to the model provider,
so the LLM is constrained to exactly the shape the frontend renders.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import APIModel

HintLevel = Literal[1, 2, 3, 4]
HINT_LEVEL_NAMES: dict[int, str] = {
    1: "nudge",
    2: "concept",
    3: "pseudocode",
    4: "full explanation",
}


class HintRequest(APIModel):
    problem_slug: str
    source_code: str = Field(default="", description="The learner's current draft")
    level: HintLevel = Field(description="1 nudge, 2 concept, 3 pseudocode, 4 full explanation")


class HintContent(BaseModel):
    """Schema the model must fill for a hint."""

    hint: str = Field(description="One focused hint at the requested level. No full solution below level 4.")
    focus_area: str = Field(description="Short label for what the hint is about, e.g. 'edge cases'")
    encouragement: str = Field(description="One short, specific sentence of encouragement")


class HintResponse(APIModel):
    level: HintLevel
    level_name: str
    content: HintContent
    max_level: int
    next_level_available: bool
    provider: str
    grounded: bool = Field(description="True when the hint came from the curated hint ladder")


class ReviewRequest(APIModel):
    problem_slug: str
    source_code: str = Field(min_length=1)
    submission_id: str | None = None


class Complexity(BaseModel):
    time: str = Field(description="Big-O time complexity of the learner's code, e.g. 'O(n)'")
    space: str = Field(description="Big-O extra space complexity, e.g. 'O(1)'")


class ReviewIssue(BaseModel):
    severity: Literal["low", "medium", "high"]
    category: Literal["correctness", "edge-case", "complexity", "readability", "style"]
    detail: str = Field(description="What is wrong and why it matters")
    suggestion: str = Field(description="A concrete next action, without writing the full solution")
    line_hint: int | None = Field(default=None, description="1-based line number, if known")


class CodeReview(BaseModel):
    """Matches the structured review example in the blueprint (section 06)."""

    summary: str
    complexity: Complexity
    issues: list[ReviewIssue]
    strengths: list[str]
    next_step: str
    confidence: Literal["low", "medium", "high"] = Field(
        description="How sure the reviewer is. Reviews are advisory; the judge decides correctness."
    )


class ReviewResponse(APIModel):
    review: CodeReview
    provider: str
    expected_complexity: Complexity | None = None
    judge_status: str | None = Field(
        default=None, description="Deterministic verdict, when a submission is referenced"
    )
    disclaimer: str = "AI feedback can be wrong. Pass/fail comes only from the test judge, never from the AI."


class AIUsage(APIModel):
    used_today: int
    daily_limit: int
    remaining_today: int
    provider: str


class AIHistoryItem(APIModel):
    id: str
    problem_slug: str
    problem_title: str
    action: str
    hint_level: int | None
    provider: str
    created_at: datetime
    response: dict | None


FailureCause = Literal[
    "compile-error",
    "index-out-of-bounds",
    "null-reference",
    "arithmetic",
    "number-format",
    "recursion-depth",
    "time-limit",
    "memory-limit",
    "crash",
    "wrong-answer",
    "hidden-edge-case",
    "overflow",
    "other",
]


class ExplainFailureRequest(APIModel):
    submission_id: str = Field(min_length=1, max_length=36)


class FailureExplanation(BaseModel):
    """Schema the model must fill when explaining a failed submission."""

    cause: FailureCause = Field(description="The single most likely root-cause category")
    headline: str = Field(description="One plain-English sentence saying what went wrong")
    explanation: str = Field(
        description="Why it happened, grounded in the evidence (test case or compiler message). "
        "Explain the bug; do not write the corrected solution."
    )
    evidence: str = Field(description="The specific test case, exception or compiler message relied on")
    line_hint: int | None = Field(default=None, description="1-based line in the learner's code, if known")
    next_steps: list[str] = Field(description="One to three concrete things to check or try")
    concept: str | None = Field(default=None, description="Java or DSA concept worth reviewing")
    confidence: Literal["low", "medium", "high"]


class ExplainFailureResponse(APIModel):
    submission_id: str
    status: str
    explanation: FailureExplanation
    provider: str
    cached: bool = Field(description="True when this explanation was saved earlier (no budget used)")
    disclaimer: str = (
        "Explanations are based only on the public tests and compiler output. Hidden test inputs "
        "are never shown to the AI or to you."
    )
