"""Operator diagnostics for the email outbox, with redaction, and recovery after an outage.

For whoever runs the server, through the CLI (`email-status`, `email-retry`, `email-quarantine`). There's no web
route: reaching these needs shell access to the server, which is the authorization. Output names
jobs, kinds, statuses, attempts, error classes or SMTP codes, the Message-ID (to match a provider's
logs) and the account id. It never shows an address's local part, a subject, a code or a link.
The recipient's domain is shown, because "every gmail.com message is deferred" is a diagnosis.

What the app knows is the SMTP outcome: `accepted` means the mail server took the message, not
that it reached an inbox (docs/EMAIL.md). Bounces and complaints that happen after acceptance
need a provider's delivery events, and none is connected. Until then they stay unknown, and
nothing here pretends otherwise.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import EmailJob, User

logger = logging.getLogger("codecoach.email_ops")


def domain_of(address: str | None) -> str:
    return address.rpartition("@")[2].lower() if address and "@" in address else "-"


def _row(job: EmailJob, user: User | None) -> dict[str, Any]:
    address = None
    if user is not None:
        address = user.pending_email if job.kind == "verify_email" and user.pending_email else user.email
    return {
        "job": job.id,
        "kind": job.kind,
        "status": job.status,
        "attempts": job.attempts,
        "last_error": job.last_error or "",
        "message_id": job.message_id or "",
        "account": job.user_id or "",
        "to_domain": domain_of(address),
        "created_at": job.created_at.isoformat() if job.created_at else "",
        "finished_at": job.finished_at.isoformat() if job.finished_at else "",
        "next_attempt_at": job.next_attempt_at.isoformat()
        if job.status == "pending" and job.next_attempt_at
        else "",
    }


def status_report(
    db: Session,
    *,
    job_id: str | None = None,
    message_id: str | None = None,
    account_email: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Recent jobs (or one job, or one account's), plus counts by status."""
    query = select(EmailJob, User).outerjoin(User, User.id == EmailJob.user_id)
    if job_id:
        query = query.where(EmailJob.id == job_id)
    if message_id:
        query = query.where(EmailJob.message_id == message_id.strip())
    if account_email:
        wanted = account_email.strip().lower()
        query = query.where(or_(func.lower(User.email) == wanted, func.lower(User.pending_email) == wanted))
    rows = db.execute(query.order_by(EmailJob.created_at.desc()).limit(limit)).all()
    counts = dict(db.execute(select(EmailJob.status, func.count()).group_by(EmailJob.status)).all())
    return {"jobs": [_row(job, user) for job, user in rows], "counts": counts}


# Only verification emails are rebuilt from the account when sent. A reset email needs the address
# it was requested for, and the change notices need both addresses. Those lived in the job's
# payload, which is cleared when a job finishes. A reset can simply be requested again, and its
# link would be past its 30 minutes after most outages anyway.
RETRYABLE = ("verify_email",)


def requeue_failed(db: Session, *, within: timedelta, now: datetime | None = None) -> dict[str, int]:
    """After an outage: give `failed` verification emails from the last `within` more attempts.
    Each still goes through the normal checks when it runs: an address verified meanwhile is
    skipped, and a code older than its lifetime is dropped. `rejected` jobs are never retried: the
    mail server refused them for good. Commits.

    `attempts` restarts at 1, not 0: this is a retry of the original request, so the once-a-minute
    duplicate check (meant for a person pressing "send" twice) doesn't apply, and the job gets
    MAX_ATTEMPTS - 1 further tries."""
    now = now or datetime.now(UTC)
    window = (EmailJob.status == "failed", EmailJob.created_at >= now - within)
    result = db.execute(
        update(EmailJob)
        .where(*window, EmailJob.kind.in_(RETRYABLE))
        .values(status="pending", attempts=1, next_attempt_at=now, finished_at=None, last_error=None)
        .execution_options(synchronize_session=False)
    )
    left = db.scalar(select(func.count()).select_from(EmailJob).where(*window))
    db.commit()
    return {"requeued": int(getattr(result, "rowcount", 0) or 0), "not_resendable": int(left or 0)}


# --- After a restore: held emails ------------------------------------------------------------
# A restored database brings back the outbox as it was at backup time. Its unfinished jobs may
# have been sent since by the old server, or may no longer be wanted, and the restored app would
# send them as soon as it started. So restore-database holds every unfinished job (`held`) before
# anything can start on the copy: no worker claims one (they claim `pending` and `sending` only),
# however many workers start or restart, until an operator releases or suppresses it.
#
# The hold records, in `last_error` (`held:<purpose>:<was>`):
# - why: `rehearsal` (the default: a copy to inspect, whose addresses are real people's) or
#   `recovery` (this copy will serve users);
# - what the job was doing at backup time: `pending` (never tried), `retrying` (tried, failed, due
#   again later), or `sending` (leased mid-send: the mail server may have taken it after the
#   snapshot, so it may already have arrived).
#
# SMTP has no idempotency: resending a job reuses its Message-ID (`<codecoach.JOB_ID@domain>`), so
# a recipient's mail client or a provider can tell it's the same message, but nothing guarantees it
# arrives only once. A job never holds a usable code or link: one is made when the email is sent,
# so releasing a verification email sends a fresh code, and an expired one is never revived.
# Ordinary restarts hold nothing.

HELD = "held"
PURPOSES = ("rehearsal", "recovery")


class QuarantineRefused(Exception):
    """A release that would email the real people in a rehearsal copy."""


def hold_unsent(db: Session, purpose: str = "rehearsal") -> int:
    """Hold every job that hasn't finished, recording why and what it was doing. Commits."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {PURPOSES}")
    states = {
        "sending": EmailJob.status == "sending",
        "retrying": and_(EmailJob.status == "pending", EmailJob.attempts > 0),
        "pending": and_(EmailJob.status == "pending", EmailJob.attempts == 0),
    }
    held = 0
    for was, which in states.items():
        result = db.execute(
            update(EmailJob)
            .where(which)
            .values(status=HELD, last_error=f"held:{purpose}:{was}")
            .execution_options(synchronize_session=False)
        )
        held += int(getattr(result, "rowcount", 0) or 0)
    db.commit()
    if held:
        logger.info("held unsent emails after a restore", extra={"count": held, "purpose": purpose})
    return held


def held_as(job: EmailJob) -> tuple[str, str]:
    """(purpose, what it was doing at backup time). Unreadable markers count as a rehearsal."""
    parts = (job.last_error or "").split(":")
    if len(parts) == 3 and parts[0] == HELD and parts[1] in PURPOSES:
        return parts[1], parts[2]
    return "rehearsal", "unknown"


def _on_release(job: EmailJob, user: User | None, too_old: bool, was: str) -> str:
    """What releasing this job would do, by the outbox's own rules (services/outbox.py)."""
    from app.services.email_verification import target_address

    if too_old:
        outcome = "dropped: older than its kind's limit, nothing goes out"
    elif job.kind == "verify_email" and (user is None or target_address(user) is None):
        outcome = "skipped: nothing to verify any more (verified, a guest, or the account is gone)"
    elif job.kind == "verify_email":
        outcome = "sent, with a fresh code and link made at send time"
    elif job.kind == "password_reset":
        outcome = "sent, with a fresh single-use link made at send time (if the account still exists)"
    else:
        outcome = "sent as queued (a notice, no code or link)"
    if was == "sending" and not outcome.startswith(("dropped", "skipped")):
        outcome += "; it was mid-send at backup time and may already have arrived (same Message-ID)"
    return outcome


def held_inventory(db: Session, settings: Any, now: datetime | None = None) -> list[dict[str, Any]]:
    """Every held job, redacted like email-status, with what releasing it would do."""
    from app.services import outbox

    now = now or datetime.now(UTC)
    rows = db.execute(
        select(EmailJob, User)
        .outerjoin(User, User.id == EmailJob.user_id)
        .where(EmailJob.status == HELD)
        .order_by(EmailJob.created_at)
    ).all()
    out = []
    for job, user in rows:
        created = job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=UTC)
        age = now - created
        purpose, was = held_as(job)
        row = _row(job, user)
        row["age_hours"] = round(age.total_seconds() / 3600, 1)
        row["held_by"] = purpose
        row["was"] = was
        row["on_release"] = _on_release(job, user, age > outbox._max_age(job.kind, settings), was)
        out.append(row)
    return out


def _held(kind: str | None, job_ids: list[str] | None) -> list[Any]:
    clauses = [EmailJob.status == HELD]
    if kind:
        clauses.append(EmailJob.kind == kind)
    if job_ids:
        clauses.append(EmailJob.id.in_(job_ids))
    return clauses


def release_held(
    db: Session,
    settings: Any,
    *,
    kind: str | None = None,
    job_ids: list[str] | None = None,
    apply: bool = False,
) -> list[str]:
    """Let the chosen held jobs go out (they become due now). A dry run unless `apply`. Touches
    only held jobs, so running it twice is harmless. One statement: an interruption releases all
    of them or none. Commits when applying.

    Refused (QuarantineRefused, dry run included) for jobs a rehearsal held while email goes out
    over SMTP: the addresses in a copy of production are real people's. A capture transport
    (EMAIL_BACKEND=file or console) can rehearse a release."""
    jobs = list(db.scalars(select(EmailJob).where(*_held(kind, job_ids))))
    rehearsal = [j.id for j in jobs if held_as(j)[0] == "rehearsal"]
    if rehearsal and settings.email_backend == "smtp":
        raise QuarantineRefused(
            f"{len(rehearsal)} of these were held by a restore rehearsal: releasing them would email "
            "the real people in the backup. Suppress them, or rehearse a release with "
            "EMAIL_BACKEND=file. For a real recovery, restore with --recovery."
        )
    chosen = [j.id for j in jobs]
    if apply and chosen:
        db.execute(
            update(EmailJob)
            .where(*_held(kind, job_ids), EmailJob.id.in_(chosen))
            .values(status="pending", next_attempt_at=datetime.now(UTC), last_error=None)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        logger.info(
            "released held emails", extra={"count": len(chosen), "jobs": chosen, "kind": kind or "any"}
        )
    return chosen


def suppress_held(
    db: Session, *, kind: str | None = None, job_ids: list[str] | None = None, apply: bool = False
) -> list[str]:
    """Never send the chosen held jobs: they're finished as `dropped`, their addresses cleared, and
    the decision kept on the job (`suppressed:<purpose>:<was>`). A dry run unless `apply`. Running
    it twice is harmless. Commits when applying."""
    jobs = list(db.scalars(select(EmailJob).where(*_held(kind, job_ids))))
    chosen = [j.id for j in jobs]
    if apply and chosen:
        now = datetime.now(UTC)
        for job in jobs:
            purpose, was = held_as(job)
            db.execute(
                update(EmailJob)
                .where(EmailJob.id == job.id, EmailJob.status == HELD)
                .values(
                    status="dropped", finished_at=now, payload=None, last_error=f"suppressed:{purpose}:{was}"
                )
                .execution_options(synchronize_session=False)
            )
        db.commit()
        logger.info(
            "suppressed held emails", extra={"count": len(chosen), "jobs": chosen, "kind": kind or "any"}
        )
    return chosen
