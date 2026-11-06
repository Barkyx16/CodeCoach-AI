"""A durable outbox for account emails: nothing is lost to a restart or a mail-server outage.

A route records an `EmailJob` in its own transaction (so the job exists exactly when the change
that needs it does), then asks for a first attempt right after the response, as before. If that
attempt fails, or the process stops first, the jobs loop (app/jobs.py, in every API process and
in `python -m app.worker`) tries again with backoff until it's sent, too old to matter, or given
up on after `MAX_ATTEMPTS`.

Each attempt is claimed with one conditional UPDATE, so any number of processes can drain the same
table without sending an email twice. A claim is a lease: a process that dies mid-send leaves the
job due again after `LEASE`.

Jobs hold what to send, never a usable secret: a verification code or reset link is created when
the email is actually sent (by the same functions as before), so nothing in this table can sign
anyone in. Addresses are cleared from a job once it's finished.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import EmailJob
from app.services import email_verification, password_reset
from app.services.email import EmailSender

logger = logging.getLogger("codecoach.outbox")

KINDS = ("verify_email", "password_reset", "email_changed")
MAX_ATTEMPTS = 5
BACKOFF = (timedelta(seconds=30), timedelta(minutes=2), timedelta(minutes=10), timedelta(minutes=30))
LEASE = timedelta(minutes=5)
KEEP_FINISHED = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def enqueue(db: Session, kind: str, *, user_id: str | None = None, payload: dict | None = None) -> EmailJob:
    """Add a job to the caller's transaction (it's committed with the caller's change)."""
    assert kind in KINDS, kind
    job = EmailJob(kind=kind, user_id=user_id, payload=payload or {}, next_attempt_at=_now())
    db.add(job)
    db.flush()
    return job


def _max_age(kind: str, settings: Settings) -> timedelta:
    if kind == "password_reset":  # a link sent later than its lifetime would arrive dead
        return timedelta(minutes=settings.password_reset_ttl_minutes)
    if kind == "verify_email":
        return timedelta(hours=settings.email_verification_ttl_hours)
    return timedelta(days=3)


def _send(
    job: dict[str, Any], session_factory: Callable[[], Session], settings: Settings, sender: EmailSender
) -> bool:
    """One attempt. True: sent; False: nothing to send. Raises if sending failed."""
    first = job["attempts"] == 1  # the once-a-minute dedupe applies to a request, not to its retries
    payload = job["payload"] or {}
    if job["kind"] == "verify_email":
        return email_verification.send_verification(
            session_factory, job["user_id"], settings, sender, cooldown=first, raise_errors=True
        )
    if job["kind"] == "password_reset":
        return password_reset.request_reset(
            session_factory, payload["email"], settings, sender, cooldown=first, raise_errors=True
        )
    return email_verification.notify_email_changed(sender, payload["old"], payload["new"], raise_errors=True)


def run(session_factory: Callable[[], Session], job_id: str, settings: Settings, sender: EmailSender) -> str:
    """Claim and attempt one job if it's due. Returns what happened: sent, skipped, dropped,
    retry, failed, or not_due (someone else has it, or it's finished)."""
    now = _now()
    with session_factory() as db:
        claimed = db.execute(
            update(EmailJob)
            .where(
                EmailJob.id == job_id,
                EmailJob.status.in_(("pending", "sending")),
                EmailJob.next_attempt_at <= now,
            )
            .values(status="sending", attempts=EmailJob.attempts + 1, next_attempt_at=now + LEASE)
            .returning(
                EmailJob.kind, EmailJob.user_id, EmailJob.payload, EmailJob.attempts, EmailJob.created_at
            )
            .execution_options(synchronize_session=False)
        ).one_or_none()
        db.commit()
    if claimed is None:
        return "not_due"
    job = dict(claimed._mapping)
    if now - _aware(job["created_at"]) > _max_age(job["kind"], settings):
        _finish(session_factory, job_id, "dropped")
        return "dropped"
    try:
        sent = _send(job, session_factory, settings, sender)
    except Exception as exc:  # noqa: BLE001 - recorded on the job and retried; never shown to anyone
        error = type(exc).__name__[:80]
        if job["attempts"] >= MAX_ATTEMPTS:
            logger.error("email job gave up", extra={"kind": job["kind"], "attempts": job["attempts"]})
            _finish(session_factory, job_id, "failed", error)
            return "failed"
        wait = BACKOFF[min(job["attempts"], len(BACKOFF)) - 1]
        with session_factory() as db:
            db.execute(
                update(EmailJob)
                .where(EmailJob.id == job_id)
                .values(status="pending", next_attempt_at=_now() + wait, last_error=error)
            )
            db.commit()
        logger.warning("email job will retry", extra={"kind": job["kind"], "attempts": job["attempts"]})
        return "retry"
    outcome = "sent" if sent else "skipped"
    _finish(session_factory, job_id, outcome)
    return outcome


def _finish(
    session_factory: Callable[[], Session], job_id: str, status: str, error: str | None = None
) -> None:
    with session_factory() as db:
        db.execute(
            update(EmailJob)
            .where(EmailJob.id == job_id)
            .values(status=status, finished_at=_now(), payload=None, last_error=error)
        )
        db.commit()


def drain(
    session_factory: Callable[[], Session], settings: Settings, sender: EmailSender, limit: int = 50
) -> dict[str, int]:
    """Attempt every due job (up to `limit`). Returns counts by outcome."""
    with session_factory() as db:
        due = db.scalars(
            select(EmailJob.id)
            .where(EmailJob.status.in_(("pending", "sending")), EmailJob.next_attempt_at <= _now())
            .order_by(EmailJob.next_attempt_at)
            .limit(limit)
        ).all()
    counts: dict[str, int] = {}
    for job_id in due:
        outcome = run(session_factory, job_id, settings, sender)
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def purge_finished(db: Session, now: datetime | None = None) -> int:
    """Delete finished jobs older than a week (their addresses were already cleared)."""
    cutoff = (now or _now()) - KEEP_FINISHED
    result = db.execute(
        delete(EmailJob).where(
            EmailJob.status.in_(("sent", "skipped", "dropped", "failed")), EmailJob.finished_at < cutoff
        )
    )
    return int(cast(CursorResult[Any], result).rowcount or 0)
