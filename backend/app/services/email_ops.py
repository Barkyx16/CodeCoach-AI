"""Operator diagnostics for the email outbox, with redaction, and recovery after an outage.

For whoever runs the server, through the CLI (`email-status`, `email-retry`). There's no web
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

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models import EmailJob, User


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
# A restored database brings back the outbox as it was at backup time. Its pending jobs may have
# been sent since by the old server, or may no longer be wanted, and the restored app would send
# them as soon as it started. So restore-database holds every unsent job (`held`): no worker
# claims one (they claim `pending` and `sending` only), however many workers start or restart,
# until an operator releases or suppresses it. A job never holds a usable code or link: one is
# made when the email is actually sent, so releasing a verification email sends a fresh code. An
# expired one is never revived. Restarts outside a restore don't hold anything.

HELD = "held"


def hold_unsent(db: Session) -> int:
    """Hold every job that hasn't finished (pending, retrying, or leased mid-send). Commits."""
    result = db.execute(
        update(EmailJob)
        .where(EmailJob.status.in_(("pending", "sending")))
        .values(status=HELD, last_error="held after a restore")
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


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
        too_old = age > outbox._max_age(job.kind, settings)
        row = _row(job, user)
        row["age_hours"] = round(age.total_seconds() / 3600, 1)
        row["on_release"] = (
            "dropped: too old to send (its kind's limit), nothing goes out"
            if too_old
            else "sent, with a fresh code or link made at send time"
            if job.kind in ("verify_email", "password_reset")
            else "sent as it was queued"
        )
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
    db: Session, *, kind: str | None = None, job_ids: list[str] | None = None, apply: bool = False
) -> list[str]:
    """Let the chosen held jobs go out (they become due now). A dry run unless `apply`. Touches
    only held jobs, so running it twice is harmless. Commits when applying."""
    chosen = list(db.scalars(select(EmailJob.id).where(*_held(kind, job_ids))))
    if apply and chosen:
        db.execute(
            update(EmailJob)
            .where(*_held(kind, job_ids), EmailJob.id.in_(chosen))
            .values(status="pending", next_attempt_at=datetime.now(UTC), last_error=None)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    return chosen


def suppress_held(
    db: Session, *, kind: str | None = None, job_ids: list[str] | None = None, apply: bool = False
) -> list[str]:
    """Never send the chosen held jobs: they're finished as `dropped`, their addresses cleared.
    A dry run unless `apply`. Running it twice is harmless. Commits when applying."""
    chosen = list(db.scalars(select(EmailJob.id).where(*_held(kind, job_ids))))
    if apply and chosen:
        db.execute(
            update(EmailJob)
            .where(*_held(kind, job_ids), EmailJob.id.in_(chosen))
            .values(
                status="dropped",
                finished_at=datetime.now(UTC),
                payload=None,
                last_error="suppressed after a restore",
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
    return chosen
