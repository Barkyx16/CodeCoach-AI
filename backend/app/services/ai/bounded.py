"""A cap on how many calls to a paid provider run at once in this process.

A provider call can take up to 45 s (anthropic_provider: 25 s per attempt, 3 attempts). Each one
holds a worker thread, and the interview flows also hold their database connection while they
wait. Without a cap, a slow provider plus a burst of requests would take every connection and
every learner would get 503s, including those doing nothing with AI. With it, a call that finds
every slot busy fails at once with reason "busy", and CoachService answers with the offline coach
(labelled as a fallback, counted under `fallback_busy`), so nobody waits and nothing queues.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

from app.schemas.ai import CodeReview, FailureExplanation, HintContent
from app.schemas.interview import InterviewerReply, InterviewEvaluation
from app.services.ai.base import (
    CoachProvider,
    FailureContext,
    HintContext,
    InterviewContext,
    ProviderError,
    ProviderResult,
    ReviewContext,
)

C = TypeVar("C")
T = TypeVar("T")


class BoundedProvider:
    def __init__(self, inner: CoachProvider, limit: int):
        self.inner = inner
        self.name = inner.name
        self.model = inner.model
        self.limit = limit
        self._slots = threading.BoundedSemaphore(limit)

    def _call(self, fn: Callable[[C], ProviderResult[T]], ctx: C) -> ProviderResult[T]:
        if not self._slots.acquire(blocking=False):
            raise ProviderError("every provider slot is busy", reason="busy", attempts=0)
        try:
            return fn(ctx)
        finally:
            self._slots.release()

    def hint(self, ctx: HintContext) -> ProviderResult[HintContent]:
        return self._call(self.inner.hint, ctx)

    def review(self, ctx: ReviewContext) -> ProviderResult[CodeReview]:
        return self._call(self.inner.review, ctx)

    def explain_failure(self, ctx: FailureContext) -> ProviderResult[FailureExplanation]:
        return self._call(self.inner.explain_failure, ctx)

    def interview_turn(self, ctx: InterviewContext) -> ProviderResult[InterviewerReply]:
        return self._call(self.inner.interview_turn, ctx)

    def evaluate_interview(self, ctx: InterviewContext) -> ProviderResult[InterviewEvaluation]:
        return self._call(self.inner.evaluate_interview, ctx)

    def __getattr__(self, item: str) -> object:  # anything else (effort, timeouts) from the provider
        return getattr(self.inner, item)
