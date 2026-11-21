"""AI coach orchestration: authorization, progressive disclosure, budgets, input sanitizing,
provider fallback, and usage records. Routes stay thin; all policy lives here."""

from __future__ import annotations

import hmac
import re
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
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
    CoachPreview,
    CodeReview,
    Complexity,
    ContextItem,
    ExplainFailurePreviewRequest,
    ExplainFailureRequest,
    ExplainFailureResponse,
    FailureExplanation,
    HintContent,
    HintPreviewRequest,
    HintRequest,
    HintResponse,
    LeftOut,
    ReviewPreview,
    ReviewPreviewRequest,
    ReviewRequest,
    ReviewResponse,
)
from app.services import request_keys
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
from app.services.ai.bounded import BoundedProvider
from app.services.ai.context_text import (
    analysis_text,
    failing_test_text,
    failure_counts_text,
    failure_verdict_text,
    hint_level_text,
)
from app.services.ai.offline import OfflineCoach
from app.services.ai.static_analysis import Analysis, analyze
from app.services.conditions import problem_version
from app.services.judge.views import public_result_view
from app.services.listed_names import names_for, names_note, replace_in, replace_names

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


def redact_secrets_counted(code: str) -> tuple[str, int]:
    """The code with secret-looking strings replaced, and how many were (a string already replaced
    by an earlier pattern isn't counted twice)."""
    count = 0

    def replaced(m: re.Match[str], to: str) -> str:
        nonlocal count
        if m.group(0) != to:
            count += 1
        return to

    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            code = pattern.sub(lambda m: replaced(m, f'{m.group(1)}{m.group(2)}"[REDACTED]"'), code)
        else:
            code = pattern.sub(lambda m: replaced(m, "[REDACTED]"), code)
    return code, count


def redact_secrets(code: str) -> str:
    return redact_secrets_counted(code)[0]


TRUNCATED = "\n// [truncated by CodeCoach: input exceeded the size limit]"


def sanitize_code_report(code: str, max_chars: int) -> tuple[str, int, bool]:
    """The code as the coach receives it, how many secret-looking strings were replaced, and
    whether it was cut to the size limit."""
    code, redacted = redact_secrets_counted(code.replace("\x00", ""))
    truncated = len(code) > max_chars
    if truncated:
        code = code[:max_chars] + TRUNCATED
    return code, redacted, truncated


def sanitize_code(code: str, max_chars: int) -> str:
    return sanitize_code_report(code, max_chars)[0]


def build_provider(settings: Settings) -> CoachProvider:
    if settings.ai_provider == "anthropic" and settings.anthropic_api_key:
        return BoundedProvider(_anthropic(settings), settings.ai_max_concurrent_calls)
    return OfflineCoach()


def _anthropic(settings: Settings) -> CoachProvider:
    assert settings.anthropic_api_key is not None
    return AnthropicCoach(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.anthropic_model,
        effort=settings.anthropic_effort,
    )


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


def request_fingerprint(
    action: AIAction,
    problem_id: int,
    hint_level: int | None,
    source_code: str,
    submission_id: str | None,
    context: str | None = None,
) -> str:
    """What a keyed coaching request stands for, made on the server from validated inputs (never a
    browser-supplied hash): the action, problem, hint level, the code exactly as sent, and the
    submission a review is about. For a review sent against a preview, also the approved context
    (its fingerprint and whether the verdict goes with it), so the same key can't later stand for
    other material. Stored as a digest only; never shown or logged."""
    payload: dict = {
        "problem": problem_id,
        "level": hint_level,
        "code": source_code,
        "submission": submission_id,
    }
    if context is not None:
        payload["context"] = context
    return request_keys.fingerprint(f"ai.{action.value}", payload)


_VERDICT_WORDS = {
    "FAILED": "failed tests",
    "COMPILE_ERROR": "didn't compile",
    "RUNTIME_ERROR": "a runtime error",
    "TIME_LIMIT": "over the time limit",
    "MEMORY_LIMIT": "over the memory limit",
}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def instructions(reader: str = "coach") -> str:
    return f"CodeCoach's own instructions to the {reader}, the same for everyone. They aren't shown here."


INSTRUCTIONS = instructions()


def _turn_key(user_id: str) -> str:
    return f"codecoach:ai-turn:{user_id}"


class CoachService:
    def __init__(
        self, db: Session, settings: Settings, provider: CoachProvider, fallback: CoachProvider | None = None
    ):
        self.db = db
        self.settings = settings
        self.provider = provider
        self.fallback = fallback if fallback is not None else OfflineCoach()

    # --- public API -------------------------------------------------------------------

    def daily_limit(self, user: User) -> int:
        """Requests a day for this account. Guests and accounts whose email isn't verified get the
        smaller allowance (anyone can make one); verifying the address lifts it."""
        limit = self.settings.ai_daily_request_limit
        if user.is_guest or user.email_verified_at is None:
            return min(limit, self.settings.ai_unverified_daily_request_limit)
        return limit

    def usage(self, user: User) -> AIUsage:
        used = self._used_today(user)
        limit = self.daily_limit(user)
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

    def _replayed(
        self,
        user: User,
        key: str | None,
        action: AIAction,
        problem: Problem,
        hint_level: int | None = None,
        fingerprint: str | None = None,
    ) -> AIInteraction | None:
        """The interaction an earlier request with this key made, if any. Sent again because its
        response was lost, a request gets that answer back: no provider call, no budget used. The
        same key with different inputs (other code, level, problem or submission) is refused."""
        if not key:
            return None
        row = self.db.scalar(
            select(AIInteraction).where(
                AIInteraction.user_id == user.id, AIInteraction.client_request_id == key
            )
        )
        if row is None:
            return None
        self._same_intent(row, action, problem, hint_level, fingerprint)
        return row

    @staticmethod
    def _same_intent(
        row: AIInteraction,
        action: AIAction,
        problem: Problem,
        hint_level: int | None,
        fingerprint: str | None,
    ) -> None:
        different = row.action != action or row.problem_id != problem.id or row.hint_level != hint_level
        # Rows from before fingerprints existed are checked as they always were.
        if not different and fingerprint:
            different = not request_keys.same(row.request_fingerprint, fingerprint)
        if different:
            raise ConflictError(
                "This request key was already used for a different coaching request.",
                code="idempotency_key_reused",
            )

    def _commit_or_replay(
        self,
        user: User,
        key: str | None,
        action: AIAction,
        problem: Problem,
        hint_level: int | None = None,
        fingerprint: str | None = None,
    ) -> AIInteraction | None:
        """Commit the new interaction. If the same key won a race meanwhile (two copies of one
        request at once, where the per-user lock doesn't apply), return the one that was kept, but
        only if it stands for the same request: a different one is refused, never returned."""
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if not key:
                raise
            row = self.db.scalar(
                select(AIInteraction).where(
                    AIInteraction.user_id == user.id, AIInteraction.client_request_id == key
                )
            )
            if row is None:
                raise
            self._same_intent(row, action, problem, hint_level, fingerprint)
            return row
        return None

    def _hint_response(
        self, problem: Problem, level: int, content: HintContent, provider: str
    ) -> HintResponse:
        max_level = len(problem.hints)
        return HintResponse(
            level=level,
            level_name=HINT_LEVEL_NAMES[level],
            content=content,
            max_level=max_level,
            next_level_available=level < max_level,
            provider=provider,
            grounded=True,
        )

    def _hint_ladder(self, user: User, problem: Problem, level: int) -> None:
        """Levels unlock one at a time (unchanged by previews: a preview is checked the same way)."""
        max_level = len(problem.hints)
        if level > max_level:
            raise NotFoundError(f"This problem has {max_level} hint levels")
        unlocked = self.highest_hint_level(user, problem) + 1
        if level > unlocked:
            raise ConflictError(
                f"Hints unlock one level at a time. Request level {unlocked} first.",
                code="hint_locked",
                details={"next_unlockable_level": unlocked},
            )

    def hint_preview(self, user: User, req: HintPreviewRequest) -> CoachPreview:
        """Exactly what a hint would send. No provider call, no budget, nothing stored."""
        problem = self._problem(req.problem_slug)
        self._hint_ladder(user, problem, req.level)
        return self._hint_material(user, problem, req.source_code, req.level)[1]

    def _hint_material(
        self, user: User, problem: Problem, source_code: str, level: int
    ) -> tuple[HintContext, CoachPreview]:
        code, analysis, items = self._code_items(
            problem,
            source_code,
            names=names_for(self.db, user.id),
            label="Your code",
            source=lambda lines: (
                f"As in the editor when you asked: {lines} line{'' if lines == 1 else 's'}. "
                "Sent with line numbers added."
            ),
            why="A hint is about your code as it is now.",
        )
        if not source_code.strip():
            items[0].notes.append("Your editor is empty: the coach is told it's an empty draft.")
        name = HINT_LEVEL_NAMES[level]
        levels = len(problem.hints)
        items.insert(
            0,
            ContextItem(
                key="level",
                label="The hint level you're asking for",
                source=f"Level {level} of {levels}.",
                text=hint_level_text(level, name),
                derived=False,
                required=True,
                why_required="A hint is for one level; each goes further than the one before.",
            ),
        )
        seen = self.highest_hint_level(user, problem)
        about = [f"Level {level} of {levels}: {name.capitalize()}."]
        if level <= seen:
            about.append(f"You've had level {level} before: this asks for it again, about your code now.")
        elif seen == 0:
            about.append("Your first hint for this problem.")
        else:
            shown = f"level 1 ({HINT_LEVEL_NAMES[1].capitalize()})" if seen == 1 else f"levels 1 to {seen}"
            about.append(f"You've seen {shown} for this problem, so this one goes further.")
        about.append("Which levels you've seen isn't sent; the level you ask for is.")
        fingerprint = request_keys.fingerprint(
            "ai.hint.context",
            {"problem": problem.slug, "level": level, "sent": [[i.key, i.text] for i in items]},
        )
        preview = self._preview(
            user,
            "hint",
            items,
            [],
            [
                f"The problem “{problem.title}”: its statement, constraints, method signature and expected "
                "complexity. Public, the same for everyone, and needed to give a hint for it.",
                f"The problem's reference hint for level {level}: written by CodeCoach, public and the same for "
                "everyone; the coach adapts it to your code. It isn't shown here, so checking doesn't give the "
                "hint away.",
            ],
            fingerprint,
            about=about,
        )
        ctx = HintContext(problem=problem_context(problem), code=code, level=level, analysis=analysis)
        return ctx, preview

    def hint(self, user: User, req: HintRequest) -> HintResponse:
        problem = self._problem(req.problem_slug)
        bound = req.approved_context is not None
        # Bound to a preview, the key stands for the approved material too: a resend after a lost
        # response gets the first hint back, and the key can't later carry other material.
        print_ = request_fingerprint(
            AIAction.HINT,
            problem.id,
            req.level,
            req.source_code,
            None,
            req.approved_context if bound else None,
        )
        if (
            done := self._replayed(user, req.client_request_id, AIAction.HINT, problem, req.level, print_)
        ) is not None:
            return self._hint_response(
                problem, req.level, HintContent.model_validate(done.response), done.provider
            )
        self._hint_ladder(user, problem, req.level)
        ctx, preview = self._hint_material(user, problem, req.source_code, req.level)
        if bound and not hmac.compare_digest(preview.context_fingerprint, req.approved_context or ""):
            raise ConflictError(
                "What the coach would read changed since you checked it, so nothing was sent. "
                "Check it again before asking.",
                code="context_changed",
                details={"preview": preview.model_dump(mode="json")},
            )
        self.check_budget(user)
        # Holding the turn now, look again: a copy of this keyed request may have been answered while
        # this one waited for it, so the provider is asked once per key (Volume 18, prompt 2).
        if (
            done := self._replayed(user, req.client_request_id, AIAction.HINT, problem, req.level, print_)
        ) is not None:
            return self._hint_response(
                problem, req.level, HintContent.model_validate(done.response), done.provider
            )
        result = self.call_with_fallback(lambda p: p.hint(ctx))
        self.record_interaction(
            user,
            problem,
            AIAction.HINT,
            result,
            hint_level=req.level,
            client_request_id=req.client_request_id,
            request_fingerprint=print_ if req.client_request_id else None,
            # Which version of the problem this hint was for (docs/ATTEMPT_CONDITIONS.md).
            content_version=problem_version(self.db, problem.id),
        )
        self._event(user, problem, ProgressEventType.HINT_USED)
        if (
            kept := self._commit_or_replay(
                user, req.client_request_id, AIAction.HINT, problem, req.level, print_
            )
        ) is not None:
            return self._hint_response(
                problem, req.level, HintContent.model_validate(kept.response), kept.provider
            )
        return self._hint_response(problem, req.level, result.content, result.provider)

    # --- code review: what it reads, previewed and bound (docs/COACH_CONTEXT.md) ----------------

    def _review_material(
        self,
        user: User,
        problem: Problem,
        source_code: str,
        submission_id: str | None,
        share_verdict: bool,
        *,
        strict: bool,
    ) -> tuple[ReviewContext, ReviewPreview, str | None, str | None]:
        """The review's context, built once, and the preview of exactly that context: the context,
        the preview, the verdict to show the learner and the submission it's about.

        `strict` (a preview, or a review sent without one): another account's or an unknown
        submission is 404, the same for both. Not strict (a review sent against a preview): it's
        checked again and, if it's gone, left out as unavailable; the preview it's compared with
        then differs, so nothing is sent and the learner sees why."""
        judge_status = None
        used_submission = None
        judged_at = None
        verdict_unavailable = False
        if submission_id:
            submission = self.db.get(Submission, submission_id)
            # Same answer for "doesn't exist" and "not yours": don't leak other users' ids.
            if submission is None or submission.user_id != user.id or submission.problem_id != problem.id:
                if strict:
                    raise NotFoundError("Submission not found")
                verdict_unavailable = True
            else:
                used_submission = submission.id
                if submission.status.is_terminal:
                    judge_status = submission.status.value
                    judged_at = submission.judged_at or submission.created_at
                    if submission.mode == SubmissionMode.RUN:
                        # Don't let the coach treat a public-tests-only run as a full verdict.
                        judge_status += " on public tests only (a Run; hidden tests were not executed)"
        code, analysis, items = self._code_items(
            problem,
            source_code,
            names=names_for(self.db, user.id),
            label="Your code",
            source=lambda lines: (
                f"As in the editor when you asked: {lines} line{'' if lines == 1 else 's'}. "
                "Sent with line numbers added."
            ),
            why="A code review is of your code.",
        )
        sent_verdict = judge_status if share_verdict else None
        ctx = ReviewContext(
            problem=problem_context(problem), code=code, judge_status=sent_verdict, analysis=analysis
        )
        left_out: list[LeftOut] = []
        if sent_verdict is not None:
            items.append(
                ContextItem(
                    key="verdict",
                    label="The judge's verdict on your submission",
                    source=f"Judged {judged_at.isoformat() if judged_at else 'earlier'}.",
                    text=sent_verdict,
                    derived=False,
                    required=False,
                )
            )
        elif judge_status is not None:
            left_out.append(
                LeftOut(key="verdict", label="The judge's verdict on your submission", reason="removed")
            )
        elif verdict_unavailable and share_verdict:
            left_out.append(
                LeftOut(key="verdict", label="The judge's verdict on your submission", reason="unavailable")
            )
        # The approval covers both what's sent and what was chosen (which submission, verdict or
        # not), so a request can't keep the approval while pointing at something else.
        fingerprint = request_keys.fingerprint(
            "ai.review.context",
            {
                "problem": problem.slug,
                "chosen": {"submission": submission_id, "share_verdict": share_verdict},
                "sent": [[i.key, i.text] for i in items],
            },
        )
        preview = self._preview(
            user,
            "code_review",
            items,
            left_out,
            [
                f"The problem “{problem.title}”: its statement, constraints, method signature and expected "
                "complexity. Public, the same for everyone, and needed to review code against it."
            ],
            fingerprint,
        )
        return ctx, preview, judge_status, used_submission

    # --- shared by every previewed operation ----------------------------------------------------

    def _code_items(
        self,
        problem: Problem,
        source_code: str,
        *,
        label: str,
        source: Callable[[int], str],
        why: str,
        names: tuple[str, ...] = (),
    ) -> tuple[str, Analysis, list[ContextItem]]:
        """The code as it's sent (secret-looking strings replaced, names you listed replaced, cut to
        size, each said) and CodeCoach's own checks of it: the same two items, built the same way, for
        every operation."""
        expected = problem.expected_complexity or {}
        code, redacted, truncated = sanitize_code_report(source_code, self.settings.ai_max_code_chars)
        code, named = replace_names(code, names)
        analysis = analyze(
            code,
            signature=problem.signature,
            starter_code=problem.starter_code,
            expected_time=expected.get("time"),
            constraints=list(problem.constraints),
        )
        notes = []
        if redacted:
            notes.append(
                f"{redacted} secret-looking string{'' if redacted == 1 else 's'} replaced with [REDACTED]."
            )
        if named:
            notes.append(names_note(named) or "")
        if truncated:
            notes.append(f"Cut to its first {self.settings.ai_max_code_chars:,} characters.")
        lines = len(source_code.splitlines()) or 1
        items = [
            ContextItem(
                key="code",
                label=label,
                source=source(lines),
                text=code,
                derived=False,
                required=True,
                why_required=why,
                notes=notes,
                names_replaced=named,
            ),
            ContextItem(
                key="checks",
                label="CodeCoach's own checks of your code",
                source="Worked out from the code above on CodeCoach's server.",
                text=analysis_text(analysis),
                derived=True,
                required=True,
                why_required="They go with your code: the coach confirms or discards each one.",
            ),
        ]
        return code, analysis, items

    def _preview(
        self,
        user: User,
        operation: str,
        items: list[ContextItem],
        left_out: list[LeftOut],
        public: list[str],
        fingerprint: str,
        *,
        about: list[str] | None = None,
        already: str | None = None,
        reader: str = "coach",
        fallback: str | None = None,
    ) -> CoachPreview:
        external = self.provider.name != "offline"
        return CoachPreview(
            operation=operation,
            about=about or [],
            already_answered=already,
            items=items,
            left_out=left_out,
            required_public=public,
            instructions=instructions(reader),
            recipient=(
                "Claude, by Anthropic: an outside service CodeCoach sends this to"
                if external
                else f"The built-in {reader}, on CodeCoach's own server: nothing leaves it"
            ),
            recipient_kind="external" if external else "built_in",
            fallback=(
                fallback
                or f"If it can't be reached, the built-in {reader} answers from this same material, and says so."
                if external
                else None
            ),
            remaining_today=max(0, self.daily_limit(user) - self._used_today(user)),
            context_fingerprint=fingerprint,
            names_replaced=sum(i.names_replaced for i in items),
            names_note=names_note(sum(i.names_replaced for i in items)),
        )

    def review_preview(self, user: User, req: ReviewPreviewRequest) -> ReviewPreview:
        """Exactly what a review would send. No provider call, no budget, nothing stored."""
        problem = self._problem(req.problem_slug)
        return self._review_material(
            user, problem, req.source_code, req.submission_id, req.share_verdict, strict=True
        )[1]

    def review(self, user: User, req: ReviewRequest) -> ReviewResponse:
        problem = self._problem(req.problem_slug)
        bound = req.approved_context is not None
        ctx, preview, judge_status, submission_id = self._review_material(
            user, problem, req.source_code, req.submission_id, req.share_verdict, strict=not bound
        )
        expected = problem.expected_complexity or {}
        # Bound to a preview: the key stands for the approved material, so a resend after a lost
        # response gets the first answer back and a different selection can't reuse it.
        if bound:
            context: str | None = f"{req.approved_context}:{int(req.share_verdict)}"
        else:
            context = None if req.share_verdict else "verdict-left-out"
        print_ = request_fingerprint(
            AIAction.REVIEW,
            problem.id,
            None,
            req.source_code,
            req.submission_id if bound else submission_id,
            context,
        )
        if (
            done := self._replayed(user, req.client_request_id, AIAction.REVIEW, problem, None, print_)
        ) is not None:
            return ReviewResponse(
                review=CodeReview.model_validate(done.response),
                provider=done.provider,
                judge_status=judge_status,
                expected_complexity=Complexity(**expected) if expected else None,
            )
        if bound and not hmac.compare_digest(preview.context_fingerprint, req.approved_context or ""):
            raise ConflictError(
                "What the coach would read changed since you checked it, so nothing was sent. "
                "Check it again before sending.",
                code="context_changed",
                details={"preview": preview.model_dump(mode="json")},
            )
        self.check_budget(user)
        # Holding the turn, look again (as for hints): asked once per key (Volume 18, prompt 2).
        if (
            done := self._replayed(user, req.client_request_id, AIAction.REVIEW, problem, None, print_)
        ) is not None:
            return ReviewResponse(
                review=CodeReview.model_validate(done.response),
                provider=done.provider,
                judge_status=judge_status,
                expected_complexity=Complexity(**expected) if expected else None,
            )
        result = self.call_with_fallback(lambda p: p.review(ctx))
        self.record_interaction(
            user,
            problem,
            AIAction.REVIEW,
            result,
            submission_id=submission_id,
            client_request_id=req.client_request_id,
            request_fingerprint=print_ if req.client_request_id else None,
        )
        self._event(user, problem, ProgressEventType.REVIEW_REQUESTED)
        if (
            kept := self._commit_or_replay(
                user, req.client_request_id, AIAction.REVIEW, problem, None, print_
            )
        ) is not None:
            result = replace(result, content=CodeReview.model_validate(kept.response), provider=kept.provider)
        return ReviewResponse(
            review=result.content,
            provider=result.provider,
            judge_status=judge_status,
            expected_complexity=Complexity(**expected) if expected else None,
        )

    # --- failure explanations: what they read, previewed and bound (docs/COACH_CONTEXT.md) --------

    def _explainable(self, user: User, submission_id: str) -> Submission:
        sub = self.db.get(Submission, submission_id)
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
        return sub

    def _saved_explanation(self, user: User, sub: Submission) -> AIInteraction | None:
        return self.db.scalar(
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

    def _failure_material(
        self, user: User, sub: Submission, share_compile: bool, share_failing: bool
    ) -> tuple[FailureContext, CoachPreview]:
        """The explanation's context, built once, and the preview of exactly that context. Public
        results only (public_result_view re-checks each row is a public test); hidden tests are
        counted, never described."""
        problem = sub.problem
        view = public_result_view(sub)
        rows = view.public_results if view else []
        first = next((r for r in rows if not r.passed), None)
        submitted = _aware(sub.created_at)
        when = submitted.strftime("%d %B %Y, %H:%M UTC").lstrip("0")
        listed = names_for(self.db, user.id)
        code, analysis, items = self._code_items(
            problem,
            sub.source_code,
            names=listed,
            label="The submitted code",
            source=lambda lines: (
                f"Your submission of {when}: {lines} line{'' if lines == 1 else 's'}. "
                "Sent with line numbers added."
            ),
            why="An explanation is of the code that failed.",
        )
        status = sub.status.value
        public_passed, public_total = sum(r.passed for r in rows), len(rows)
        hidden_passed, hidden_total = (view.hidden_passed, view.hidden_total) if view else (0, 0)
        items.append(
            ContextItem(
                key="verdict",
                label="The judge's verdict",
                source=f"Judged {_aware(sub.judged_at or sub.created_at).strftime('%d %B %Y, %H:%M UTC').lstrip('0')}.",
                text=failure_verdict_text(status),
                derived=False,
                required=True,
                why_required="It's what the explanation is about.",
            )
        )
        items.append(
            ContextItem(
                key="counts",
                label="How many tests passed",
                source="Counted by the judge. Hidden tests' inputs and outputs are never sent, only these counts.",
                text=failure_counts_text(public_passed, public_total, hidden_passed, hidden_total),
                derived=True,
                required=True,
                why_required="They say whether only hidden tests failed.",
            )
        )
        left_out: list[LeftOut] = []
        compile_output = view.stderr_excerpt if view else None
        compile_named = 0
        if compile_output:
            compile_output, compile_named = replace_names(compile_output, listed)
        if compile_output:
            if share_compile:
                items.append(
                    ContextItem(
                        key="compile_output",
                        label="The compiler output",
                        source="From the judge, with its own driver lines removed.",
                        text=compile_output,
                        derived=False,
                        required=False,
                        notes=[n for n in [names_note(compile_named)] if n],
                        names_replaced=compile_named,
                    )
                )
            else:
                left_out.append(LeftOut(key="compile_output", label="The compiler output", reason="removed"))
        # What your program printed or threw is yours: names you listed are replaced in it too (the
        # test's own input and expected output are public).
        actual, actual_named = replace_in(first.actual_output, listed) if first else (None, 0)
        message, message_named = replace_names(first.exception_message or "", listed) if first else ("", 0)
        case = (
            FailingCase(
                index=first.index,
                input=first.input,
                expected=first.expected_output,
                actual=actual,
                exception=first.exception,
                message=message if first.exception_message is not None else None,
                line=first.line,
                missing=first.missing,
            )
            if first
            else None
        )
        if case is not None:
            label = "The first failing public test, with your program's output"
            if share_failing:
                items.append(
                    ContextItem(
                        key="failing_test",
                        label=label,
                        source=f"Public test {case.index + 1}: the test is public; what your program printed or "
                        "threw is yours.",
                        text=failing_test_text(
                            case.index,
                            case.input,
                            case.expected,
                            case.actual,
                            case.exception,
                            case.message,
                            case.line,
                            case.missing,
                        ),
                        derived=False,
                        required=False,
                        notes=[n for n in [names_note(actual_named + message_named)] if n],
                        names_replaced=actual_named + message_named,
                    )
                )
            else:
                left_out.append(LeftOut(key="failing_test", label=label, reason="removed"))
        ctx = FailureContext(
            problem=problem_context(problem),
            code=code,
            analysis=analysis,
            status=status,
            compile_output=compile_output if share_compile else None,
            failing_case=case if share_failing else None,
            public_passed=public_passed,
            public_total=public_total,
            hidden_passed=hidden_passed,
            hidden_total=hidden_total,
        )
        # The approval covers what's sent and what was chosen, for this submission only: a newer
        # submission is a different request and needs its own check.
        fingerprint = request_keys.fingerprint(
            "ai.explain.context",
            {
                "problem": problem.slug,
                "submission": sub.id,
                "chosen": {"compile_output": share_compile, "failing_test": share_failing},
                "sent": [[i.key, i.text] for i in items],
            },
        )
        preview = self._preview(
            user,
            "failure_explanation",
            items,
            left_out,
            [
                f"The problem “{problem.title}”: its statement, constraints, method signature and expected "
                "complexity. Public, the same for everyone, and needed to explain a failure against it."
            ],
            fingerprint,
            about=[
                f"Explains your submission of {when} ({_VERDICT_WORDS.get(status, status)}).",
                "One explanation is kept for each submission: asking again shows it and sends nothing.",
            ],
            already=(
                "This submission was explained before: asking again shows that explanation and sends nothing."
                if self._saved_explanation(user, sub) is not None
                else None
            ),
        )
        return ctx, preview

    def explain_preview(self, user: User, req: ExplainFailurePreviewRequest) -> CoachPreview:
        """Exactly what an explanation would send. No provider call, no budget, nothing stored."""
        sub = self._explainable(user, req.submission_id)
        return self._failure_material(user, sub, req.share_compile_output, req.share_failing_test)[1]

    def explain_failure(self, user: User, req: ExplainFailureRequest) -> ExplainFailureResponse:
        sub = self._explainable(user, req.submission_id)
        # One explanation per submission: asking again returns the saved one and costs nothing, so a
        # resend after a lost reply (or with a wider choice) never sends more material.
        saved = self._saved_explanation(user, sub)
        if saved is not None and saved.response is not None:
            return ExplainFailureResponse(
                submission_id=sub.id,
                status=sub.status.value,
                explanation=FailureExplanation.model_validate(saved.response),
                provider=saved.provider,
                cached=True,
            )
        ctx, preview = self._failure_material(user, sub, req.share_compile_output, req.share_failing_test)
        if req.approved_context is not None and not hmac.compare_digest(
            preview.context_fingerprint, req.approved_context
        ):
            raise ConflictError(
                "What the coach would read changed since you checked it, so nothing was sent. "
                "Check it again before asking.",
                code="context_changed",
                details={"preview": preview.model_dump(mode="json")},
            )
        self.check_budget(user)
        problem = sub.problem
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

    def _claim_turn(self, user: User) -> bool:
        """One AI request per user at a time, on PostgreSQL: a transaction-scoped advisory lock,
        taken without waiting and released when this request's transaction ends. Held across
        the count, the provider call and the insert, it makes the daily budget exact: two
        requests can't both pass at 49 of 50, and two copies of one keyed request can't both
        call the provider. The call it is held across is bounded (BoundedProvider: at most 45 s,
        at most AI_MAX_CONCURRENT_CALLS at once), and if the process dies mid-call the database
        ends the transaction: nothing is recorded or charged, and the lock is gone, so there is
        no abandoned reservation to clean up. SQLite (local runs) has no such lock: always True."""
        bind = self.db.get_bind()
        if bind.dialect.name != "postgresql":
            return True
        return bool(
            self.db.scalar(
                text("SELECT pg_try_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": _turn_key(user.id)}
            )
        )

    @staticmethod
    def turn_in_flight(db: Session, user_id: str) -> bool:
        """Whether another request of this user holds the AI turn right now (PostgreSQL; on SQLite
        it can't be told: False). Looks without taking it, so it never makes a request wait."""
        if db.get_bind().dialect.name != "postgresql":
            return False
        return bool(
            db.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_locks l, (SELECT hashtextextended(:k, 0) AS h) x "
                    "WHERE l.locktype = 'advisory' AND l.granted AND l.objsubid = 1 "
                    "AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database()) "
                    "AND l.classid::bigint = ((x.h >> 32) & 4294967295) "
                    "AND l.objid::bigint = (x.h & 4294967295) AND l.pid <> pg_backend_pid())"
                ),
                {"k": _turn_key(user_id)},
            )
        )

    def check_budget(self, user: User) -> None:
        if not self._claim_turn(user):
            raise RateLimitedError.wait(
                "Your previous coaching request is still being answered. Try again when it's done.",
                2,
                code="ai_request_in_progress",
            )
        limit = self.daily_limit(user)
        if self._used_today(user) >= limit:
            since = datetime.now(UTC) - timedelta(days=1)
            # The window is rolling: a request frees up when the oldest in the last 24 h ages out.
            oldest = self.db.scalar(
                select(func.min(AIInteraction.created_at)).where(
                    AIInteraction.user_id == user.id, AIInteraction.created_at >= since
                )
            )
            wait = 3600.0
            if oldest is not None:
                oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=UTC)
                wait = (oldest + timedelta(days=1) - datetime.now(UTC)).total_seconds()
            message = "You've used today's AI coaching budget. It resets on a rolling 24-hour window."
            if limit < self.settings.ai_daily_request_limit:
                message += (
                    " A guest session gets a smaller one: an account with a verified email gets more."
                    if user.is_guest
                    else " Verify your email address to get the full daily budget."
                )
            raise RateLimitedError.wait(message, wait, daily_limit=limit)

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
        client_request_id: str | None = None,
        request_fingerprint: str | None = None,
        content_version: int | None = None,
    ) -> None:
        self.db.add(
            AIInteraction(
                user_id=user.id,
                content_version=content_version,
                client_request_id=client_request_id,
                request_fingerprint=request_fingerprint,
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
