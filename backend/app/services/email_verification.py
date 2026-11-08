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
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models import EmailVerificationToken, User
from app.services.email import Email, EmailSender

logger = logging.getLogger("codecoach.email_verification")
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_CODE_ATTEMPTS = 5  # 5 guesses out of 1,000,000 per code; a resend issues a new code
INVALID = (
    "This verification link is invalid or has expired. If you asked for a new code, use the newest "
    "email; otherwise send a new one from Settings."
)
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


def cooldown_remaining(db: Session, user: User, now: datetime | None = None) -> float:
    """Seconds before another code may be sent to this account's current address (0 if now)."""
    now = now or datetime.now(UTC)
    latest = db.scalar(
        select(EmailVerificationToken.created_at)
        .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.email == user.email)
        .order_by(EmailVerificationToken.created_at.desc())
        .limit(1)
    )
    if latest is None:
        return 0.0
    return max(0.0, (RESEND_COOLDOWN - (now - _aware(latest))).total_seconds())


def confirm(db: Session, raw: str) -> User:
    """Verify with the emailed link (works signed out). Claimed atomically: a link works once."""
    now = datetime.now(UTC)
    claimed = db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.token_hash == _hash(raw),
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(EmailVerificationToken.user_id, EmailVerificationToken.email)
        .execution_options(synchronize_session=False)
    ).one_or_none()
    if claimed is None:
        db.rollback()
        raise AppError(INVALID, code="invalid_verification_token")
    user = db.get(User, claimed.user_id)
    if user is None or user.email != claimed.email:  # the email changed since this link was sent
        db.rollback()
        raise AppError(INVALID, code="invalid_verification_token")
    user.email_verified_at = user.email_verified_at or now
    db.commit()
    return user


def _superseded(db: Session, user: User, before: datetime, code: str, settings: Settings) -> bool:
    """Is `code` one of this address's older codes, replaced by a newer email?"""
    older = db.scalars(
        select(EmailVerificationToken.code_hash).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.email == user.email,
            EmailVerificationToken.created_at < before,
        )
    ).all()
    candidates = [_code_hash(key, user.id, code) for key in settings.verification_keys]
    return any(hmac.compare_digest(h, c) for h in older for c in candidates)


def confirm_code(db: Session, user: User, code: str, settings: Settings) -> User:
    """Verify with the 6-digit code from the latest email (signed-in user only).

    Each attempt is counted with one conditional UPDATE before the code is compared, so parallel
    guesses can't share a count and get more than MAX_CODE_ATTEMPTS tries. A code is claimed the
    same way, so it works once."""
    if user.email_verified_at is not None:
        return user
    now = datetime.now(UTC)
    code = code.strip()
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
        raise AppError(
            "This code no longer works (it expired, was replaced, or had too many wrong tries). Send a new one.",
            code="invalid_verification_code",
        )
    token_id, created = row.id, row.created_at
    attempts = db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.id == token_id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.code_attempts < MAX_CODE_ATTEMPTS,
        )
        .values(code_attempts=EmailVerificationToken.code_attempts + 1)
        .returning(EmailVerificationToken.code_attempts)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if attempts is None:  # used, or out of tries (perhaps by a parallel request)
        db.commit()
        raise AppError("Too many wrong codes. Send a new one.", code="too_many_attempts")
    candidates = [_code_hash(key, user.id, code) for key in settings.verification_keys]
    if not any(hmac.compare_digest(row.code_hash, c) for c in candidates):
        superseded = _superseded(db, user, created, code, settings)
        if attempts >= MAX_CODE_ATTEMPTS:
            db.execute(
                update(EmailVerificationToken)
                .where(EmailVerificationToken.id == token_id)
                .values(used_at=now)
                .execution_options(synchronize_session=False)
            )  # too many guesses: this code (and its link) are dead
            db.commit()
            raise AppError("Too many wrong codes. Send a new one.", code="too_many_attempts")
        db.commit()
        if superseded:
            raise AppError(
                "That code was replaced by a newer one. Use the code in the newest email.",
                code="superseded_verification_code",
                details={"attempts_left": MAX_CODE_ATTEMPTS - attempts},
            )
        raise AppError(
            INVALID_CODE,
            code="invalid_verification_code",
            details={"attempts_left": MAX_CODE_ATTEMPTS - attempts},
        )
    claimed = db.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.id == token_id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if cast(CursorResult[Any], claimed).rowcount != 1:
        db.rollback()  # a parallel request used it first: that request verified the address
        db.refresh(user)
        if user.email_verified_at is not None:
            return user
        raise AppError("That code has already been used. Send a new one.", code="invalid_verification_code")
    user.email_verified_at = now
    db.commit()
    return user
