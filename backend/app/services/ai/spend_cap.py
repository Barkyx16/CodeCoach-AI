"""An app-wide ceiling on calls to a paid AI provider (docs/SECURITY.md, "AI spending").

Each account has its own daily budget (`CoachService.check_budget`), but anyone can start a guest
session or register, so per-account budgets alone don't bound what the deployment spends. This
wraps the paid provider: every call first takes one from a shared counter (in the database, so
every API replica and restart share it) of `AI_APP_DAILY_PAID_CALL_LIMIT` a rolling day. With none
left it raises `ProviderError(reason="app_budget")` without calling the provider, and the coach's
usual fallback answers with the free built-in coach, labelled as a fallback, until the window frees
up. Nothing about the learner's request is sent anywhere or stored here: the counter's key is
fixed.

The counter is read, then taken (`peek`, then `hit`), so a refused call doesn't count and the
ceiling frees up on its own; requests passing the read at the same moment can each take one, so the
ceiling can be passed by at most the number of calls in flight at once (`AI_MAX_CONCURRENT_CALLS`
per API process). A call is counted when it's attempted, whatever it costs or however it ends.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

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
from app.services.rate_limit import DatabaseRateLimiter, SlidingWindowLimiter

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

T = TypeVar("T")
C = TypeVar("C")

KEY = "ai-paid-calls:app"
DAY_S = 86_400


class SpendCappedProvider:
    def __init__(self, inner: CoachProvider, limiter: DatabaseRateLimiter | SlidingWindowLimiter):
        self.inner = inner
        self.name = inner.name
        self.model = inner.model
        self.limiter = limiter

    def remaining(self) -> bool:
        """Whether a paid call would be allowed now (reads only)."""
        return self.limiter.peek(KEY)[0]

    def _call(self, fn: Callable[[C], ProviderResult[T]], ctx: C) -> ProviderResult[T]:
        if self.limiter.limit <= 0 or not self.limiter.peek(KEY)[0]:
            raise ProviderError(
                "the app's daily allowance of paid AI calls is used", reason="app_budget", attempts=0
            )
        self.limiter.hit(KEY)
        return fn(ctx)

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

    def __getattr__(self, item: str) -> object:  # anything else (effort, timeouts, limit) from the provider
        return getattr(self.inner, item)


def capped(
    provider: CoachProvider, settings: Settings, session_factory: Callable[[], Session]
) -> CoachProvider:
    """The provider the API and the worker use: a paid one behind the app's daily ceiling, the
    offline coach as it is. Both share one counter (in the database unless RATE_LIMIT_BACKEND=memory)."""
    if provider.name == "offline":
        return provider
    limit = settings.ai_app_daily_paid_call_limit
    limiter: DatabaseRateLimiter | SlidingWindowLimiter = (
        DatabaseRateLimiter(session_factory, limit, DAY_S)
        if settings.rate_limit_backend == "database"
        else SlidingWindowLimiter(limit, float(DAY_S))
    )
    return SpendCappedProvider(provider, limiter)
