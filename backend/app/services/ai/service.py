"""AI coach orchestration: authorization, progressive disclosure, budgets, input sanitizing,
provider fallback, and usage records. Routes stay thin; all policy lives here."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tracing
from app.config import Settings
from app.errors import ConflictError, NotFoundError, RateLimitedError
from app.models import (
    AIAction,
    AIInteraction,
    Problem,
    ProgressEvent,
    ProgressEventType,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    User,
)
from app.schemas.ai import (
    HINT_LEVEL_NAMES,
    AIUsage,
    Complexity,
    ExplainFailureRequest,
    ExplainFailureResponse,
    FailureExplanation,
    HintRequest,
    HintResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.services.ai.anthropic_provider import AnthropicCoach
from app.services.ai.base import (
    CoachProvider,
    FailingCase,
    FailureContext,
    HintContext,
    ProblemContext,
    ProviderError,
    ProviderResult,
    ReviewContext,
)
from app.services.ai.offline import OfflineCoach
from app.services.ai.static_analysis import analyze
from app.services.judge.views import public_result_view

T = TypeVar("T")

# Learner-caused verdicts. PASSED has nothing to explain; INTERNAL_ERROR is the judge's fault.
EXPLAINABLE = {
    SubmissionStatus.FAILED,
    SubmissionStatus.COMPILE_ERROR,
    SubmissionStatus.RUNTIME_ERROR,
    SubmissionStatus.TIME_LIMIT,
    SubmissionStatus.MEMORY_LIMIT,
}

# Secrets must never be forwarded to a model provider (blueprint section 06).
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b(\s*[=:]\s*)\"[^\"]{4,}\""),
]


def redact_secrets(code: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            code = pattern.sub(lambda m: f'{m.group(1)}{m.group(2)}"[REDACTED]"', code)
        else:
            code = pattern.sub("[REDACTED]", code)
    return code


def sanitize_code(code: str, max_chars: int) -> str:
    code = redact_secrets(code.replace("\x00", ""))
    if len(code) > max_chars:
        code = code[:max_chars] + "\n// [truncated by CodeCoach: input exceeded the size limit]"
    return code


def build_provider(settings: Settings) -> CoachProvider:
    if settings.ai_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicCoach(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
        )
    return OfflineCoach()


def problem_context(problem: Problem) -> ProblemContext:
    return ProblemContext(
        slug=problem.slug,
        title=problem.title,
        statement=problem.statement,
        constraints=list(problem.constraints),
        signature=dict(problem.signature),
        starter_code=problem.starter_code,
        expected_time=(problem.expected_complexity or {}).get("time"),
        expected_space=(problem.expected_complexity or {}).get("space"),
        curated_hints=list(problem.hints),
    )


class CoachService:
    def __init__(
        self, db: Session, settings: Settings, provider: CoachProvider, fallback: CoachProvider | None = None
    ):
        self.db = db
        self.settings = settings
        self.provider = provider
        self.fallback = fallback if fallback is not None else OfflineCoach()

    # --- public API -------------------------------------------------------------------

    def usage(self, user: User) -> AIUsage:
        used = self._used_today(user)
        limit = self.settings.ai_daily_request_limit
        return AIUsage(
            used_today=used,
            daily_limit=limit,
            remaining_today=max(0, limit - used),
            provider=self.provider.name,
        )

    def highest_hint_level(self, user: User, problem: Problem) -> int:
        return (
            self.db.scalar(
                select(func.coalesce(func.max(AIInteraction.hint_level), 0)).where(
                    AIInteraction.user_id == user.id,
                    AIInteraction.problem_id == problem.id,
                    AIInteraction.action == AIAction.HINT,
                )
            )
            or 0
        )

    def hint(self, user: User, req: HintRequest) -> HintResponse:
        problem = self._problem(req.problem_slug)
        max_level = len(problem.hints)
        if req.level > max_level:
            raise NotFoundError(f"This problem has {max_level} hint levels")
        unlocked = self.highest_hint_level(user, problem) + 1
        if req.level > unlocked:
            raise ConflictError(
                f"Hints unlock one level at a time. Request level {unlocked} first.",
                code="hint_locked",
                details={"next_unlockable_level": unlocked},
            )
        self.check_budget(user)

        code = sanitize_code(req.source_code, self.settings.ai_max_code_chars)
        ctx = HintContext(
            problem=problem_context(problem),
            code=code,
            level=req.level,
            analysis=analyze(
                code,
                signature=problem.signature,
                starter_code=problem.starter_code,
                expected_time=(problem.expected_complexity or {}).get("time"),
                constraints=list(problem.constraints),
            ),
        )
        result = self.call_with_fallback(lambda p: p.hint(ctx))
        self.record_interaction(user, problem, AIAction.HINT, result, hint_level=req.level)
        self._event(user, problem, ProgressEventType.HINT_USED)
        self.db.commit()
        return HintResponse(
            level=req.level,
            level_name=HINT_LEVEL_NAMES[req.level],
            content=result.content,
            max_level=max_level,
            next_level_available=req.level < max_level,
            provider=result.provider,
            grounded=True,
        )

    def review(self, user: User, req: ReviewRequest) -> ReviewResponse:
        problem = self._problem(req.problem_slug)
        judge_status = None
        submission_id = None
        if req.submission_id:
            submission = self.db.get(Submission, req.submission_id)
            # Same 404 for "doesn't exist" and "not yours": don't leak other users' ids.
            if submission is None or submission.user_id != user.id or submission.problem_id != problem.id:
                raise NotFoundError("Submission not found")
            submission_id = submission.id
            if submission.status.is_terminal:
                judge_status = submission.status.value
                if submission.mode == SubmissionMode.RUN:
                    # Don't let the coach treat a public-tests-only run as a full verdict.
                    judge_status += " on public tests only (a Run; hidden tests were not executed)"
        self.check_budget(user)

        code = sanitize_code(req.source_code, self.settings.ai_max_code_chars)
        expected = problem.expected_complexity or {}
        ctx = ReviewContext(
            problem=problem_context(problem),
            code=code,
            judge_status=judge_status,
            analysis=analyze(
                code,
                signature=problem.signature,
                starter_code=problem.starter_code,
                expected_time=expected.get("time"),
                constraints=list(problem.constraints),
            ),
        )
        result = self.call_with_fallback(lambda p: p.review(ctx))
        self.record_interaction(user, problem, AIAction.REVIEW, result, submission_id=submission_id)
        self._event(user, problem, ProgressEventType.REVIEW_REQUESTED)
        self.db.commit()
        return ReviewResponse(
            review=result.content,
            provider=result.provider,
            judge_status=judge_status,
            expected_complexity=Complexity(**expected) if expected else None,
        )

    def explain_failure(self, user: User, req: ExplainFailureRequest) -> ExplainFailureResponse:
        sub = self.db.get(Submission, req.submission_id)
        # Same 404 for "doesn't exist" and "not yours": don't leak other users' ids.
        if sub is None or sub.user_id != user.id:
            raise NotFoundError("Submission not found")
        if not sub.status.is_terminal:
            raise ConflictError("This submission hasn't been judged yet.", code="not_judged")
        if sub.status == SubmissionStatus.PASSED:
            raise ConflictError(
                "This submission passed, so there's no failure to explain.", code="not_failed"
            )
        if sub.status not in EXPLAINABLE:
            raise ConflictError(
                "The judge had a problem running this submission. It wasn't your code; please resubmit.",
                code="judge_error",
            )

        # One explanation per submission: asking again returns the saved one and costs nothing.
        saved = self.db.scalar(
            select(AIInteraction)
            .where(
                AIInteraction.user_id == user.id,
                AIInteraction.submission_id == sub.id,
                AIInteraction.action == AIAction.EXPLAIN_FAILURE,
                AIInteraction.response.is_not(None),
            )
            .order_by(AIInteraction.created_at.desc())
            .limit(1)
        )
        if saved is not None and saved.response is not None:
            return ExplainFailureResponse(
                submission_id=sub.id,
                status=sub.status.value,
                explanation=FailureExplanation.model_validate(saved.response),
                provider=saved.provider,
                cached=True,
            )
        self.check_budget(user)

        problem = sub.problem
        view = public_result_view(sub)
        rows = view.public_results if view else []
        first = next((r for r in rows if not r.passed), None)
        code = sanitize_code(sub.source_code, self.settings.ai_max_code_chars)
        ctx = FailureContext(
            problem=problem_context(problem),
            code=code,
            analysis=analyze(
                code,
                signature=problem.signature,
                starter_code=problem.starter_code,
                expected_time=(problem.expected_complexity or {}).get("time"),
                constraints=list(problem.constraints),
            ),
            status=sub.status.value,
            compile_output=view.stderr_excerpt if view else None,
            failing_case=FailingCase(
                index=first.index,
                input=first.input,
                expected=first.expected_output,
                actual=first.actual_output,
                exception=first.exception,
                message=first.exception_message,
                line=first.line,
                missing=first.missing,
            )
            if first
            else None,
            public_passed=sum(r.passed for r in rows),
            public_total=len(rows),
            hidden_passed=view.hidden_passed if view else 0,
            hidden_total=view.hidden_total if view else 0,
        )
        result = self.call_with_fallback(lambda p: p.explain_failure(ctx))
        self.record_interaction(user, problem, AIAction.EXPLAIN_FAILURE, result, submission_id=sub.id)
        self.db.commit()
        return ExplainFailureResponse(
            submission_id=sub.id,
            status=sub.status.value,
            explanation=result.content,
            provider=result.provider,
            cached=False,
        )

    # --- internals --------------------------------------------------------------------

    def _problem(self, slug: str) -> Problem:
        problem = self.db.scalar(select(Problem).where(Problem.slug == slug))
        if problem is None:
            raise NotFoundError(f"Problem '{slug}' not found")
        return problem

    def _used_today(self, user: User) -> int:
        since = datetime.now(UTC) - timedelta(days=1)
        return (
            self.db.scalar(
                select(func.count())
                .select_from(AIInteraction)
                .where(AIInteraction.user_id == user.id, AIInteraction.created_at >= since)
            )
            or 0
        )

    def check_budget(self, user: User) -> None:
        if self._used_today(user) >= self.settings.ai_daily_request_limit:
            raise RateLimitedError(
                "You've used today's AI coaching budget. It resets on a rolling 24-hour window.",
                details={"daily_limit": self.settings.ai_daily_request_limit},
            )

    def call_with_fallback(self, call: Callable[[CoachProvider], ProviderResult[T]]) -> ProviderResult[T]:
        """Run `call` on the configured provider; on ProviderError, answer with the offline coach.

        Measured as the span `coach.provider`, whose outcome says what happened without any learner
        text: `ok`, or `fallback_<reason>` (timeout, connection, rate_limited, http_5xx, http_4xx,
        refusal, cut_off, invalid_output, invalid_body). The metrics endpoint counts spans by name
        and outcome, so fallbacks are counted by reason."""
        start = time.perf_counter()
        with tracing.span("coach.provider", provider=self.provider.name) as step:
            try:
                result = call(self.provider)
                step.set(attempt=result.attempts)  # requests sent, retries included
            except ProviderError as exc:
                step.set(attempt=getattr(exc, "attempts", 1))
                if self.fallback is None or self.fallback is self.provider:
                    raise
                step.outcome = f"fallback_{getattr(exc, 'reason', 'error')}"
                result = replace(call(self.fallback), provider=f"{self.fallback.name} (fallback)")
        return replace(result, latency_ms=int((time.perf_counter() - start) * 1000))

    def record_interaction(
        self,
        user: User,
        problem: Problem,
        action: AIAction,
        result: ProviderResult,
        *,
        hint_level: int | None = None,
        submission_id: str | None = None,
        store_response: bool = True,
    ) -> None:
        self.db.add(
            AIInteraction(
                user_id=user.id,
                problem_id=problem.id,
                submission_id=submission_id,
                action=action,
                hint_level=hint_level,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                response=result.content.model_dump(mode="json") if store_response else None,
            )
        )

    def _event(self, user: User, problem: Problem, kind: ProgressEventType) -> None:
        self.db.add(ProgressEvent(user_id=user.id, problem_id=problem.id, event_type=kind))
