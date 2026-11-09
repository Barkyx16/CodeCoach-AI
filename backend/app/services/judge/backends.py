"""Execution backends: what happens when a submission is created.

The API process never executes submitted code. Two implementations:

- DisabledExecutionBackend: submissions are stored; nothing runs (EXECUTION_ENABLED=false).
- QueuedExecutionBackend: submissions are queued in the database; the separate judge worker
  (app/worker.py) sends them to the isolated gVisor runner (runner/). Admission control keeps
  any one user, or everyone together, from flooding the judge.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError, RateLimitedError
from app.models import Submission, SubmissionStatus, User

EXECUTION_DISABLED_DETAIL = (
    "Saved and queued. Automatic judging is turned off until the sandboxed Java runner "
    "is approved and deployed, so this submission will not run yet."
)
QUEUED_DETAIL = "Waiting for a judge…"
PENDING = (SubmissionStatus.QUEUED, SubmissionStatus.RUNNING)


class JudgeBusyError(AppError):
    status_code = 503
    code = "judge_busy"


class ExecutionDisabledError(AppError):
    status_code = 503
    code = "execution_disabled"


class JudgeUnavailableError(AppError):
    status_code = 503
    code = "judge_unavailable"


# The judge's full-queue retry hint (Volume 8, prompt 7; docs/RECOVERY.md). Measured, not
# configured: the average gap between the judge's recent completions, which is roughly how often
# a place in the queue frees up. Bounded both ways; and none at all when nothing finished in the
# window (the judge may be down: a countdown would be invented). A hint, never a completion time.
BUSY_WINDOW = timedelta(minutes=5)
BUSY_HINT_MIN_S, BUSY_HINT_MAX_S = 5, 120


def busy_retry_hint(db: Session, now: datetime | None = None) -> int | None:
    now = now or datetime.now(UTC)
    finished = (
        db.scalar(
            select(func.count()).select_from(Submission).where(Submission.judged_at >= now - BUSY_WINDOW)
        )
        or 0
    )
    if finished == 0:
        return None
    gap = BUSY_WINDOW.total_seconds() / finished
    return int(min(BUSY_HINT_MAX_S, max(BUSY_HINT_MIN_S, -(-gap // 1))))


def lock_admission(db: Session, user: User) -> None:
    """One account's submissions are admitted one at a time (PostgreSQL): two tabs pressing at once
    can't both pass the "still being judged" check. Held until the transaction ends. SQLite (local
    development) has no such lock; there two simultaneous presses can both be admitted."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"submit:{user.id}"})


def _pending_submission(db: Session, user: User) -> Submission | None:
    return db.scalar(
        select(Submission)
        .where(Submission.user_id == user.id, Submission.status.in_(PENDING))
        .order_by(Submission.created_at)
        .limit(1)
    )


class ExecutionBackend(Protocol):
    name: str
    enabled: bool

    def admit(self, db: Session, user: User) -> None:
        """Raise if this user may not submit right now."""

    def enqueue(self, db: Session, submission: Submission) -> None:
        """Schedule a submission for judging. Must not block on execution."""


def _check_rate(db: Session, user: User, limit: int) -> None:
    """At most `limit` submissions per user per minute, counted from the saved rows."""
    since = datetime.now(UTC) - timedelta(minutes=1)
    recent = db.scalars(
        select(Submission.created_at)
        .where(Submission.user_id == user.id, Submission.created_at >= since)
        .order_by(Submission.created_at)
    ).all()
    if len(recent) >= limit:
        oldest = recent[-limit]
        oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=UTC)
        wait = (oldest + timedelta(minutes=1) - datetime.now(UTC)).total_seconds()
        raise RateLimitedError.wait(
            "You're submitting very quickly. Wait a moment and try again.",
            wait,
            limit_per_minute=limit,
        )


class DisabledExecutionBackend:
    """Code isn't run, but each submission is still saved (up to MAX_SOURCE_CHARS), so the same
    per-minute limit applies: without it, saving was the one unlimited write."""

    name = "disabled"
    enabled = False

    def __init__(self, settings: Settings | None = None):
        self.limit = settings.submission_rate_limit_per_minute if settings else 6

    def admit(self, db: Session, user: User) -> None:
        _check_rate(db, user, self.limit)

    def enqueue(self, db: Session, submission: Submission) -> None:
        submission.status_detail = EXECUTION_DISABLED_DETAIL


class QueuedExecutionBackend:
    name = "queued"
    enabled = True

    def __init__(self, settings: Settings):
        self.settings = settings

    def admit(self, db: Session, user: User) -> None:
        lock_admission(db, user)
        _check_rate(db, user, self.settings.submission_rate_limit_per_minute)
        pending = (
            db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.user_id == user.id, Submission.status.in_(PENDING))
            )
            or 0
        )
        if pending >= self.settings.max_pending_per_user:
            # The caller's own oldest one, so the page can lead back to it instead of suggesting
            # another submit. No wait: how long judging takes isn't known.
            earliest = _pending_submission(db, user)
            raise RateLimitedError(
                "Your previous submission is still being judged.",
                code="submission_pending",
                details={
                    "max_pending": self.settings.max_pending_per_user,
                    "pending_submission_id": earliest.id if earliest else None,
                    "problem_slug": earliest.problem.slug if earliest else None,
                    "mode": earliest.mode.value if earliest else None,
                },
            )
        depth = (
            db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.status == SubmissionStatus.QUEUED)
            )
            or 0
        )
        if depth >= self.settings.max_queue_depth:
            hint = busy_retry_hint(db)
            if hint is None:
                raise JudgeBusyError(
                    "The judge's queue is full right now, so this wasn't submitted. Nothing was saved."
                )
            raise JudgeBusyError(
                "The judge's queue is full right now, so this wasn't submitted. Nothing was saved.",
                details={"retry_after_seconds": hint},
            )

    def enqueue(self, db: Session, submission: Submission) -> None:
        submission.status = SubmissionStatus.QUEUED
        submission.status_detail = QUEUED_DETAIL


def build_backend(settings: Settings) -> ExecutionBackend:
    return (
        QueuedExecutionBackend(settings) if settings.execution_enabled else DisabledExecutionBackend(settings)
    )
