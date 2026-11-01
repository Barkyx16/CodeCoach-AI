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

from sqlalchemy import func, select
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


class ExecutionBackend(Protocol):
    name: str
    enabled: bool

    def admit(self, db: Session, user: User) -> None:
        """Raise if this user may not submit right now."""

    def enqueue(self, db: Session, submission: Submission) -> None:
        """Schedule a submission for judging. Must not block on execution."""


class DisabledExecutionBackend:
    name = "disabled"
    enabled = False

    def admit(self, db: Session, user: User) -> None:
        return None

    def enqueue(self, db: Session, submission: Submission) -> None:
        submission.status_detail = EXECUTION_DISABLED_DETAIL


class QueuedExecutionBackend:
    name = "queued"
    enabled = True

    def __init__(self, settings: Settings):
        self.settings = settings

    def admit(self, db: Session, user: User) -> None:
        since = datetime.now(UTC) - timedelta(minutes=1)
        recent = (
            db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.user_id == user.id, Submission.created_at >= since)
            )
            or 0
        )
        if recent >= self.settings.submission_rate_limit_per_minute:
            raise RateLimitedError(
                "You're submitting very quickly. Wait a moment and try again.",
                details={"limit_per_minute": self.settings.submission_rate_limit_per_minute},
            )
        pending = (
            db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.user_id == user.id, Submission.status.in_(PENDING))
            )
            or 0
        )
        if pending >= self.settings.max_pending_per_user:
            raise RateLimitedError(
                "Your previous submission is still being judged.",
                code="submission_pending",
                details={"max_pending": self.settings.max_pending_per_user},
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
            raise JudgeBusyError("The judge is very busy right now. Please try again in a minute.")

    def enqueue(self, db: Session, submission: Submission) -> None:
        submission.status = SubmissionStatus.QUEUED
        submission.status_detail = QUEUED_DETAIL


def build_backend(settings: Settings) -> ExecutionBackend:
    return QueuedExecutionBackend(settings) if settings.execution_enabled else DisabledExecutionBackend()
