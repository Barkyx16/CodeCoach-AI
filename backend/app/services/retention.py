"""Data retention: delete guest (demo) accounts nobody has used for a while.

"Try it now" creates a guest account per visitor. Without a policy they'd accumulate forever,
along with their code and AI feedback. A guest's last activity is the latest of: when it was
created, its newest refresh token (an open tab refreshes every ~15 minutes) and its newest
progress event (opening a problem, submitting, asking for a hint, ...). Registered accounts are
never touched. Deleting the user removes everything else through ON DELETE CASCADE.

Run it from cron with `python -m app.cli prune-guests`, or let the judge worker do it daily.

Expired sign-in material goes too: refresh tokens, password-reset links and email codes are
deleted a week after they expire (`purge_expired_tokens`). Until then a reused old token can still
be recognised and refused, and nothing older than that is useful to anyone. Only hashes were ever
stored, never the tokens themselves.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import EmailVerificationToken, PasswordResetToken, ProgressEvent, RefreshToken, User

logger = logging.getLogger("codecoach.retention")


def inactive_guest_ids(db: Session, older_than_days: int, now: datetime | None = None) -> list[str]:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=older_than_days)
    last_refresh = (
        select(RefreshToken.user_id, func.max(RefreshToken.created_at).label("at"))
        .group_by(RefreshToken.user_id)
        .subquery()
    )
    last_event = (
        select(ProgressEvent.user_id, func.max(ProgressEvent.created_at).label("at"))
        .group_by(ProgressEvent.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User.id, User.created_at, last_refresh.c.at, last_event.c.at)
        .outerjoin(last_refresh, last_refresh.c.user_id == User.id)
        .outerjoin(last_event, last_event.c.user_id == User.id)
        .where(User.is_guest.is_(True), User.created_at < cutoff)
    ).all()

    def aware(dt: datetime | None) -> datetime | None:
        return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=UTC))

    stale = []
    for user_id, created, refreshed, acted in rows:
        last = max(d for d in (aware(created), aware(refreshed), aware(acted)) if d is not None)
        if last < cutoff:
            stale.append(user_id)
    return stale


def prune_inactive_guests(db: Session, older_than_days: int, now: datetime | None = None) -> int:
    """Delete inactive guest accounts and all of their data. Returns how many were deleted."""
    if older_than_days <= 0:
        return 0
    ids = inactive_guest_ids(db, older_than_days, now)
    for start in range(0, len(ids), 500):  # bounded statements for large backlogs
        db.execute(delete(User).where(User.id.in_(ids[start : start + 500])))
    db.commit()
    if ids:
        logger.info("pruned inactive guest accounts", extra={"count": len(ids)})
    return len(ids)


TOKEN_GRACE = timedelta(days=7)


def purge_expired_tokens(db: Session, now: datetime | None = None) -> int:
    """Delete sign-in sessions, reset links and email codes that expired more than a week ago.
    Doesn't commit."""
    cutoff = (now or datetime.now(UTC)) - TOKEN_GRACE
    removed = 0
    for model in (RefreshToken, PasswordResetToken, EmailVerificationToken):
        result = db.execute(delete(model).where(model.expires_at < cutoff))
        removed += int(getattr(result, "rowcount", 0) or 0)
    return removed
