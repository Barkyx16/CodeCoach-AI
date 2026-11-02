"""Rotating refresh tokens (session continuity without long-lived bearer tokens).

The browser keeps the short-lived access token in memory only. The refresh token lives in an
HttpOnly, SameSite=Strict cookie scoped to /api/v1/auth, so page scripts (and therefore XSS)
can't read it. The server stores only its SHA-256 hash.

Rotation and reuse detection: every refresh marks the presented token as used and issues a new
one in the same family. If an already-used token is presented again later, someone has a copy:
the whole family is revoked and the user has to sign in again. A short grace window covers two
tabs refreshing at the same moment with the same cookie: the second gets a retryable error
(`refresh_race`) instead of nuking the session.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import UnauthorizedError
from app.models import RefreshToken, User, new_id

COOKIE_NAME = "cc_refresh"
COOKIE_PATH = "/api/v1/auth"
RACE_GRACE = timedelta(seconds=30)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def issue(db: Session, user: User, settings: Settings, family_id: str | None = None) -> str:
    """Create a refresh token (new family unless one is given). Returns the raw token.

    Also prunes this user's expired rows. Used and revoked rows are kept until they expire,
    because they're what lets a replayed token be recognised.
    """
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.expires_at < _now()))
    raw = secrets.token_urlsafe(32)
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or new_id(),
            token_hash=_hash(raw),
            token_version=user.token_version,
            expires_at=_now() + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return raw


def revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def revoke_all(db: Session, user: User) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def find(db: Session, raw: str | None) -> RefreshToken | None:
    if not raw:
        return None
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))


def rotate(db: Session, raw: str | None, settings: Settings) -> tuple[User, str]:
    """Validate and rotate. Returns (user, new raw token) or raises UnauthorizedError.

    Commits on reuse detection so the revocation sticks even though the request fails.
    """
    row = find(db, raw)
    if row is None:
        raise UnauthorizedError("Please sign in again.", code="invalid_refresh")
    now = _now()
    if row.revoked_at is not None:
        raise UnauthorizedError("Please sign in again.", code="invalid_refresh")
    if row.used_at is not None:
        if now - _aware(row.used_at) <= RACE_GRACE:
            # Another tab refreshed with this cookie a moment ago; it now holds the new one.
            raise UnauthorizedError("Session refresh already in progress; retry.", code="refresh_race")
        revoke_family(db, row.family_id)
        db.commit()
        raise UnauthorizedError(
            "This session was used from somewhere else, so it was ended for safety. Please sign in again.",
            code="refresh_reused",
        )
    if _aware(row.expires_at) <= now:
        raise UnauthorizedError("Your session expired. Please sign in again.", code="invalid_refresh")
    user = db.get(User, row.user_id)
    if user is None or user.token_version != row.token_version:
        raise UnauthorizedError("Please sign in again.", code="invalid_refresh")
    row.used_at = now
    return user, issue(db, user, settings, family_id=row.family_id)
