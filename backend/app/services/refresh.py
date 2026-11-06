"""Rotating refresh tokens (session continuity without long-lived bearer tokens).

The browser keeps the short-lived access token in memory only. The refresh token lives in an
HttpOnly, SameSite=Strict cookie scoped to /api/v1/auth, so page scripts (and therefore XSS)
can't read it. The server stores only its SHA-256 hash.

Rotation and reuse detection: every refresh marks the presented token as used and issues a new
one in the same family. If an already-used token is presented again later, someone has a copy:
the whole family is revoked and the user has to sign in again. A short grace window covers two
tabs refreshing at the same moment with the same cookie: the second gets a retryable error
(`refresh_race`) instead of nuking the session.

Lost responses: a refresh can succeed on the server while its response never reaches the browser
(a reload, a closed tab, a dropped connection). The browser then still holds the token the server
just marked as used, and presenting it again used to end the session. So each refresh attempt may
carry a random per-attempt key, which the client keeps until it learns the outcome. When it does,
the successor token is derived from the presented token and that key with an HMAC under the
server's secret, so for a short, bounded window (`RECOVERY_WINDOW`) the same (token, key) pair
can be presented again and gets back the *same* successor: never a second one, and only while the
successor is unused, unrevoked and unexpired and the account's sessions haven't been ended since.
Without the key, or with a different one, the rules above apply unchanged.

Rotation is atomic: the presented token is claimed with a conditional UPDATE, so two requests
racing with one token can't both rotate it. A family is dead as soon as any of its tokens has been
revoked, which also covers a successor issued in the instant a logout was revoking the family.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import UnauthorizedError
from app.models import RefreshToken, User, new_id

COOKIE_NAME = "cc_refresh"
COOKIE_PATH = "/api/v1/auth"
RACE_GRACE = timedelta(seconds=30)
# How long after a rotation its lost response can still be recovered with the same attempt key.
# Long enough for a reload or a brief network drop; after it, a replay is treated as reuse.
RECOVERY_WINDOW = timedelta(minutes=2)
# The client's per-attempt key: random, URL-safe, 22-64 characters. Anything else is ignored.
ATTEMPT_KEY = re.compile(r"^[A-Za-z0-9_-]{22,64}$")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def valid_attempt_key(value: str | None) -> str | None:
    return value if value and ATTEMPT_KEY.fullmatch(value) else None


def _successor(raw: str, attempt: str, secret: str) -> str:
    """The token that rotating `raw` under this attempt key produces. Unguessable without the
    server's secret, and the same every time for the same (token, key), which is what makes a
    replay of a lost response return the same successor instead of a new one."""
    mac = hmac.new(
        secret.encode(), b"refresh-successor\x00" + raw.encode() + b"\x00" + attempt.encode(), "sha256"
    )
    return base64.urlsafe_b64encode(mac.digest()).rstrip(b"=").decode()


def issue(
    db: Session, user: User, settings: Settings, family_id: str | None = None, raw: str | None = None
) -> str:
    """Create a refresh token (new family unless one is given). Returns the raw token.

    Also prunes this user's expired rows. Used and revoked rows are kept until they expire,
    because they're what lets a replayed token be recognised.
    """
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.expires_at < _now()))
    raw = raw or secrets.token_urlsafe(32)
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
    # Lock the family's rows first (PostgreSQL; SQLite serialises writers anyway). If a refresh
    # is rotating one of them right now, this waits for it, and the UPDATE below, a new
    # statement, then also sees the successor that refresh just issued.
    db.execute(select(RefreshToken.id).where(RefreshToken.family_id == family_id).with_for_update())
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


def _family_revoked(db: Session, family_id: str) -> bool:
    revoked = select(RefreshToken.id).where(
        RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_not(None)
    )
    return db.scalar(revoked.limit(1)) is not None


def _recover(
    db: Session, row: RefreshToken, raw: str, attempt: str, settings: Settings, now: datetime
) -> tuple[User, str] | None:
    """The successor a lost response carried, if this is a bounded replay of that same attempt."""
    if row.used_at is None or now - _aware(row.used_at) > RECOVERY_WINDOW:
        return None
    # The current key first; an older one only if SECRET_KEY was rotated in the last 2 minutes.
    successor_raw, successor = "", None
    for key in settings.verification_keys:
        successor_raw = _successor(raw, attempt, key)
        if (successor := find(db, successor_raw)) is not None:
            break
    if successor is None or successor.family_id != row.family_id or successor.user_id != row.user_id:
        return None  # a different key: not the attempt that rotated this token
    if successor.used_at is not None or successor.revoked_at is not None:
        return None  # its holder already moved on, or the session was ended
    if _aware(successor.expires_at) <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None or user.token_version != successor.token_version:
        return None
    return user, successor_raw


def rotate(db: Session, raw: str | None, settings: Settings, attempt: str | None = None) -> tuple[User, str]:
    """Validate and rotate. Returns (user, new raw token) or raises UnauthorizedError.

    `attempt` is the client's per-attempt key (already validated), if it sent one.
    Commits on reuse detection so the revocation sticks even though the request fails.
    """
    row = find(db, raw)
    if row is None or raw is None:
        raise UnauthorizedError("Please sign in again.", code="invalid_refresh")
    now = _now()
    if row.revoked_at is not None or _family_revoked(db, row.family_id):
        raise UnauthorizedError("Please sign in again.", code="invalid_refresh")
    if row.used_at is not None:
        if attempt is not None:
            recovered = _recover(db, row, raw, attempt, settings, now)
            if recovered is not None:
                return recovered
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
    # Claim the token atomically: if another request used (or a logout revoked) it since we read
    # it, this matches nothing and only one successor is ever issued.
    claim = (
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.used_at.is_(None), RefreshToken.revoked_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if cast(CursorResult[Any], db.execute(claim)).rowcount != 1:
        db.rollback()
        # Lost the claim to a request that has now committed. If it was this same attempt (a page
        # reloaded while its refresh was still being processed), hand back what it issued.
        current = find(db, raw)
        if attempt is not None and current is not None and current.revoked_at is None:
            recovered = _recover(db, current, raw, attempt, settings, _now())
            if recovered is not None:
                return recovered
        raise UnauthorizedError("Session refresh already in progress; retry.", code="refresh_race")
    successor = _successor(raw, attempt, settings.signing_key) if attempt is not None else None
    return user, issue(db, user, settings, family_id=row.family_id, raw=successor)
