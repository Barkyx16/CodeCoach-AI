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
    session_factory: Callable[[], Session], email: str, settings: Settings, sender: EmailSender
) -> None:
    now = datetime.now(UTC)
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email.lower(), User.is_guest.is_(False)))
        if user is None:
            return  # nothing to send; the caller already gave the same answer either way
        latest = db.scalar(
            select(PasswordResetToken.created_at)
            .where(PasswordResetToken.user_id == user.id)
            .order_by(PasswordResetToken.created_at.desc())
            .limit(1)
        )
        if latest is not None and now - _aware(latest) < RESEND_COOLDOWN:
            return
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
        logger.exception("password reset email failed")


def confirm_reset(db: Session, raw: str, new_password: str) -> None:
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(raw)))
    now = datetime.now(UTC)
    if row is None or row.used_at is not None or _aware(row.expires_at) <= now:
        raise AppError(
            "This reset link is invalid or has expired. Request a new one.", code="invalid_reset_token"
        )
    user = db.get(User, row.user_id)
    if user is None:
        raise AppError(
            "This reset link is invalid or has expired. Request a new one.", code="invalid_reset_token"
        )
    user.password_hash = hash_password(new_password)
    user.token_version += 1  # every existing access token stops working
    refresh_tokens.revoke_all(db, user)  # and every refresh cookie
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
