"""Provider-neutral interface for the AI coach (blueprint: keep AI vendors behind a small
service interface so providers can be swapped)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from app.schemas.ai import CodeReview, HintContent
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
class ProviderResult(Generic[T]):
    content: T
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ProviderError(Exception):
    """The provider could not produce a usable answer (network, quota, refusal, bad output)."""


class CoachProvider(Protocol):
    name: str
    model: str

    def hint(self, ctx: HintContext) -> ProviderResult[HintContent]: ...

    def review(self, ctx: ReviewContext) -> ProviderResult[CodeReview]: ...
