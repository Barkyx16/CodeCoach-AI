"""Provider-neutral interface for the AI coach (blueprint: keep AI vendors behind a small
service interface so providers can be swapped)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from app.models import InterviewPhase
from app.schemas.ai import CodeReview, FailureExplanation, HintContent
from app.schemas.interview import InterviewerReply, InterviewEvaluation
from app.services.ai.static_analysis import Analysis

T = TypeVar("T")


@dataclass(frozen=True)
class ProblemContext:
    slug: str
    title: str
    statement: str
    constraints: list[str]
    signature: dict
    starter_code: str
    expected_time: str | None
    expected_space: str | None
    curated_hints: list[str]


@dataclass(frozen=True)
class HintContext:
    problem: ProblemContext
    code: str
    level: int
    analysis: Analysis


@dataclass(frozen=True)
class ReviewContext:
    problem: ProblemContext
    code: str
    analysis: Analysis
    judge_status: str | None


@dataclass(frozen=True)
class FailingCase:
    """One failing PUBLIC test. Hidden tests are never described beyond counts."""

    index: int
    input: dict | None
    expected: object | None
    actual: object | None
    exception: str | None
    message: str | None
    line: int | None
    missing: bool


@dataclass(frozen=True)
class FailureContext:
    problem: ProblemContext
    code: str
    analysis: Analysis
    status: str  # a failing SubmissionStatus value
    compile_output: str | None
    failing_case: FailingCase | None  # first failing public test, if any
    public_passed: int
    public_total: int
    hidden_passed: int
    hidden_total: int


@dataclass(frozen=True)
class TranscriptTurn:
    role: str  # "interviewer" | "candidate"
    phase: InterviewPhase
    content: str


@dataclass(frozen=True)
class InterviewContext:
    problem: ProblemContext
    phase: InterviewPhase
    transcript: list[TranscriptTurn]
    code: str
    analysis: Analysis
    candidate_turns_in_phase: int
    seconds_remaining: int
    is_opening: bool = False
    end_reason: str | None = None  # "finished" | "time_expired" | "abandoned" (evaluation only)


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    content: T
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    attempts: int = 1  # requests sent to the provider for this answer (retries included)


class ProviderError(Exception):
    """The provider could not produce a usable answer (network, quota, refusal, bad output).

    `reason` is a short, safe code for logs and metrics (no learner text): timeout, connection,
    rate_limited, http_5xx, http_4xx, refusal, cut_off, invalid_output, invalid_body.
    `attempts` is how many requests were sent before giving up."""

    def __init__(self, message: str, *, reason: str = "error", attempts: int = 1) -> None:
        super().__init__(message)
        self.reason, self.attempts = reason, attempts


class CoachProvider(Protocol):
    name: str
    model: str

    def hint(self, ctx: HintContext) -> ProviderResult[HintContent]: ...

    def review(self, ctx: ReviewContext) -> ProviderResult[CodeReview]: ...

    def explain_failure(self, ctx: FailureContext) -> ProviderResult[FailureExplanation]: ...

    def interview_turn(self, ctx: InterviewContext) -> ProviderResult[InterviewerReply]: ...

    def evaluate_interview(self, ctx: InterviewContext) -> ProviderResult[InterviewEvaluation]: ...
