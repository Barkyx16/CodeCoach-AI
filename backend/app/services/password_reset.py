"""Forgot-password flow.

request_reset: looks up the account and emails a single-use link. It runs as a background task
after the API has already answered "202, if an account exists we sent a link", so neither the
response nor its timing reveals whether an email is registered. One email per account per minute
stops it being used to flood someone's inbox.

confirm_reset: a valid, unused, unexpired token sets the new password and ends every session
(access tokens via token_version, refresh tokens revoked). The token is marked used, along with
any other outstanding links for the account.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models import PasswordResetToken, User
from app.services import email_verification
from app.services import refresh as refresh_tokens
from app.services.auth import hash_password
from app.services.email import Email, EmailSender

logger = logging.getLogger("codecoach.password_reset")
RESEND_COOLDOWN = timedelta(seconds=60)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def request_reset(
    session_factory: Callable[[], Session],
    email: str,
    settings: Settings,
    sender: EmailSender,
    *,
    cooldown: bool = True,
    raise_errors: bool = False,
) -> bool:
    """Make a fresh single-use link and email it. False if there was nothing to send (no such
    account, or a link was sent under a minute ago and `cooldown` applies)."""
    now = datetime.now(UTC)
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email.lower(), User.is_guest.is_(False)))
        if user is None:
            return False  # nothing to send; the caller already gave the same answer either way
        latest = db.scalar(
            select(PasswordResetToken.created_at)
            .where(PasswordResetToken.user_id == user.id)
            .order_by(PasswordResetToken.created_at.desc())
            .limit(1)
        )
        if cooldown and latest is not None and now - _aware(latest) < RESEND_COOLDOWN:
            return False
        # Only the newest link works.
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
        raw = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash(raw),
                expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
            )
        )
        db.commit()
        to = user.email or ""
    # A URL fragment never reaches servers, proxies or Referer headers.
    link = f"{settings.app_base_url.rstrip('/')}/reset-password#token={raw}"
    try:
        sender.send(
            Email(
                to=to,
                subject="Reset your CodeCoach AI password",
                text=(
                    "Someone (hopefully you) asked to reset the password for this CodeCoach AI account.\n\n"
                    f"Choose a new password here (the link works once, for {settings.password_reset_ttl_minutes} "
                    f"minutes):\n{link}\n\n"
                    "If you didn't ask for this, ignore this email: your password hasn't changed.\n"
                ),
            )
        )
    except Exception:  # noqa: BLE001 - delivery failures are logged, never shown to the requester
        if raise_errors:
            raise  # the outbox records it and tries again later
        logger.exception("password reset email failed")
        return False
    return True


def confirm_reset(db: Session, raw: str, new_password: str) -> None:
    now = datetime.now(UTC)
    # Claimed with one conditional UPDATE: two requests with the same link can't both use it.
    user_id = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == _hash(raw),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.user_id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    user = db.get(User, user_id) if user_id else None
    if user is None:
        db.rollback()
        raise AppError(
            "This reset link is invalid or has expired. Request a new one.", code="invalid_reset_token"
        )
    # Resetting from the account's address proves control of it: a pending change of address
    # (perhaps asked for by whoever had the password) is cancelled.
    email_verification.drop_pending(db, user)
    user.password_hash = hash_password(new_password)
    user.token_version += 1  # every existing access token stops working
    refresh_tokens.revoke_all(db, user)  # and every refresh cookie
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
