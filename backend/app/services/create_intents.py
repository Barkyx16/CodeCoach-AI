"""Recovering an account-creating request whose reply was lost (Volume 8, prompt 6;
docs/RECOVERY.md "Starting as a guest or registering").

A guest start or a registration makes an account and a session in one request. If its reply is
lost, the browser has neither the access token nor (usually) the session cookie, and sending the
request again used to make a second guest, or answer "email taken" for the account it had just
made. Now the browser first gets an **anchor**: a random value in an HttpOnly, SameSite=Strict
cookie scoped to the auth endpoints, which page scripts can't read and other sites can't send. The
create stores a hash of it with the new account, in the same transaction. Sent again from the same
browser, the request finds that account:

- a **guest** is resumed by the anchor alone. A guest has no password or email; the anchor is the
  only thing that ties it to this browser, the same way the session cookie would have;
- a **registration** is resumed only when the password is right too (as a sign-in would be), and no
  second verification email is sent. Without both, it's the usual answer.

The anchor is never accepted from anywhere but its cookie, never shown to scripts, and proves the
same browser only; a request id in page storage proves nothing and isn't used. An intent lasts
CREATE_INTENT_MINUTES, is deleted when the browser signs out deliberately (or the account signs out
everywhere), and is purged by the daily housekeeping.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import CreateIntent, User

COOKIE_NAME = "cc_create"
CREATE_INTENT_MINUTES = 60
_MIN_LEN = 32


def new_anchor() -> str:
    return secrets.token_urlsafe(32)


def valid(anchor: str | None) -> bool:
    return bool(anchor) and len(anchor or "") >= _MIN_LEN and len(anchor or "") <= 128


def _hash(anchor: str) -> str:
    return hashlib.sha256(anchor.encode()).hexdigest()


def made_by(db: Session, anchor: str | None, kind: str) -> User | None:
    """The account this browser's earlier request of this kind made, if it's recent and still
    stands as that kind (a guest still a guest; a registration still the same account)."""
    if not valid(anchor):
        return None
    assert anchor is not None
    since = datetime.now(UTC) - timedelta(minutes=CREATE_INTENT_MINUTES)
    row = db.scalar(
        select(CreateIntent).where(CreateIntent.anchor_hash == _hash(anchor), CreateIntent.kind == kind)
    )
    if row is None:
        return None
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
    if created < since:
        return None
    user = db.get(User, row.user_id)
    if user is None or (kind == "guest" and not user.is_guest):
        return None  # deleted since, or the guest became an account: never resumed as a guest
    return user


def record(db: Session, anchor: str | None, kind: str, user: User) -> None:
    """In the create's own transaction. An older intent of this kind for this browser (expired,
    or for an account that no longer qualifies) is replaced."""
    if not valid(anchor):
        return
    assert anchor is not None
    db.execute(
        delete(CreateIntent).where(CreateIntent.anchor_hash == _hash(anchor), CreateIntent.kind == kind)
    )
    db.add(CreateIntent(anchor_hash=_hash(anchor), kind=kind, user_id=user.id))


def forget(db: Session, anchor: str | None) -> None:
    """A deliberate sign-out: this browser's intents go, so the next start is a new one."""
    if valid(anchor):
        assert anchor is not None
        db.execute(delete(CreateIntent).where(CreateIntent.anchor_hash == _hash(anchor)))


def forget_user(db: Session, user_id: str) -> None:
    """Signed out everywhere: no browser resumes this account's creation."""
    db.execute(delete(CreateIntent).where(CreateIntent.user_id == user_id))


def purge(db: Session, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(minutes=CREATE_INTENT_MINUTES)
    result = db.execute(delete(CreateIntent).where(CreateIntent.created_at < cutoff))
    return int(getattr(result, "rowcount", 0) or 0)
