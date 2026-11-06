"""Email verification and change-of-email notices.

A verification link proves the user controls the address *currently* on the account: each token
records the email it was sent to, and stops working if the account's email changes. Sending
happens as a background task after the response (same pattern as password reset), with a
one-minute cooldown per account and only the newest link valid.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models import EmailVerificationToken, User
from app.services.email import Email, EmailSender

logger = logging.getLogger("codecoach.email_verification")
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_CODE_ATTEMPTS = 5  # 5 guesses out of 1,000,000 per code; a resend issues a new code
INVALID = "This verification link is invalid or has expired. Send a new one from Settings."
INVALID_CODE = "That code isn't right. Check the latest email, or send a new code."


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _code_hash(secret: str, user_id: str, code: str) -> str:
    # Keyed with the server secret: a 6-digit code has too little entropy to store as a plain hash.
    return hmac.new(secret.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def send_verification(
    session_factory: Callable[[], Session],
    user_id: str,
    settings: Settings,
    sender: EmailSender,
    *,
    cooldown: bool = True,
    raise_errors: bool = False,
) -> bool:
    """Make a fresh code and link and email them. False if there was nothing to send (verified,
    gone, or a code was sent under a minute ago and `cooldown` applies). The outbox retries with
    `cooldown=False` and `raise_errors=True`, so a failed send is retried rather than skipped."""
    now = datetime.now(UTC)
    with session_factory() as db:
        user = db.get(User, user_id)
        if user is None or user.is_guest or not user.email or user.email_verified_at is not None:
            return False
        latest = db.scalar(
            select(EmailVerificationToken.created_at)
            .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.email == user.email)
            .order_by(EmailVerificationToken.created_at.desc())
            .limit(1)
        )
        if cooldown and latest is not None and now - _aware(latest) < RESEND_COOLDOWN:
            return False
        db.execute(
            update(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
            .values(used_at=now)
        )
        raw = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                email=user.email,
                token_hash=_hash(raw),
                code_hash=_code_hash(settings.signing_key, user.id, code),
                expires_at=now + timedelta(hours=settings.email_verification_ttl_hours),
            )
        )
        db.commit()
        to = user.email
    link = f"{settings.app_base_url.rstrip('/')}/verify-email#token={raw}"
    return _deliver(
        sender,
        Email(
            to=to,
            subject=f"{code} is your CodeCoach AI verification code",
            text=(
                f"Your CodeCoach AI verification code is: {code}\n\n"
                'Enter it on the "Check your email" screen, or open this link instead:\n'
                f"{link}\n\n"
                f"The code and the link work once, for {settings.email_verification_ttl_hours} hours.\n"
                "If you didn't create an account, you can ignore this email.\n"
            ),
        ),
        raise_errors=raise_errors,
    )


def notify_email_changed(
    sender: EmailSender, old_email: str, new_email: str, *, raise_errors: bool = False
) -> bool:
    """Tell the previous address, so a hijacked account doesn't change hands silently."""
    return _deliver(
        sender,
        Email(
            to=old_email,
            subject="Your CodeCoach AI email address was changed",
            text=(
                f"The email address on your CodeCoach AI account was changed to {new_email}.\n\n"
                "If you made this change, there's nothing to do. If you didn't, someone may know your "
                "password: reply to this email so we can help you recover the account.\n"
            ),
        ),
        raise_errors=raise_errors,
    )


def _deliver(sender: EmailSender, email: Email, *, raise_errors: bool = False) -> bool:
    try:
        sender.send(email)
    except Exception:  # noqa: BLE001 - delivery failures are logged, never shown to users
        if raise_errors:
            raise  # the outbox records it and tries again later
        logger.exception("email delivery failed")
        return False
    return True


def confirm(db: Session, raw: str) -> User:
    row = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == _hash(raw)))
    now = datetime.now(UTC)
    if row is None or row.used_at is not None or _aware(row.expires_at) <= now:
        raise AppError(INVALID, code="invalid_verification_token")
    user = db.get(User, row.user_id)
    if user is None or user.email != row.email:  # the email changed since this link was sent
        raise AppError(INVALID, code="invalid_verification_token")
    user.email_verified_at = now
    row.used_at = now
    db.commit()
    return user


def confirm_code(db: Session, user: User, code: str, settings: Settings) -> User:
    """Verify with the 6-digit code from the latest email (signed-in user only)."""
    if user.email_verified_at is not None:
        return user
    now = datetime.now(UTC)
    row = db.scalar(
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.email == user.email,
            EmailVerificationToken.used_at.is_(None),
        )
        .order_by(EmailVerificationToken.created_at.desc())
        .limit(1)
    )
    if row is None or _aware(row.expires_at) <= now:
        raise AppError("That code has expired. Send a new one.", code="invalid_verification_code")
    row.code_attempts += 1
    candidates = [_code_hash(key, user.id, code.strip()) for key in settings.verification_keys]
    if not any(hmac.compare_digest(row.code_hash, c) for c in candidates):
        if row.code_attempts >= MAX_CODE_ATTEMPTS:
            row.used_at = now  # too many guesses: this code (and its link) are dead
            db.commit()
            raise AppError("Too many wrong codes. Send a new one.", code="too_many_attempts")
        db.commit()
        raise AppError(
            INVALID_CODE,
            code="invalid_verification_code",
            details={"attempts_left": MAX_CODE_ATTEMPTS - row.code_attempts},
        )
    user.email_verified_at = now
    row.used_at = now
    db.commit()
    return user
