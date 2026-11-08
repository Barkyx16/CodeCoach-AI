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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError, ConflictError
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
        address = target_address(user) if user is not None else None
        if user is None or address is None:
            return False
        changing = address == user.pending_email
        latest = db.scalar(
            select(EmailVerificationToken.created_at)
            .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.email == address)
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
                email=address,
                token_hash=_hash(raw),
                code_hash=_code_hash(settings.signing_key, user.id, code),
                expires_at=now + timedelta(hours=settings.email_verification_ttl_hours),
            )
        )
        db.commit()
    link = f"{settings.app_base_url.rstrip('/')}/verify-email#token={raw}"
    hours = settings.email_verification_ttl_hours
    if changing:
        email = Email(
            to=address,
            subject=f"{code} confirms your new CodeCoach AI email",
            text=(
                f"Your CodeCoach AI verification code is: {code}\n\n"
                "Someone signed in to a CodeCoach AI account asked to use this address for it. Enter the "
                'code on the "Check your email" screen, or open this link:\n'
                f"{link}\n\n"
                f"The code and the link work once, for {hours} hours. Until then the account keeps its "
                "current address.\nIf this wasn't you, ignore this email: nothing changes.\n"
            ),
        )
    else:
        email = Email(
            to=address,
            subject=f"{code} is your CodeCoach AI verification code",
            text=(
                f"Your CodeCoach AI verification code is: {code}\n\n"
                'Enter it on the "Check your email" screen, or open this link instead:\n'
                f"{link}\n\n"
                f"The code and the link work once, for {hours} hours.\n"
                "If you didn't create an account, you can ignore this email.\n"
            ),
        )
    return _deliver(sender, email, raise_errors=raise_errors)


def target_address(user: User) -> str | None:
    """Where a verification code goes: a pending new address, else an unverified current one."""
    if user.is_guest:
        return None
    if user.pending_email:
        return user.pending_email
    if user.email and user.email_verified_at is None:
        return user.email
    return None


def notify_change_requested(
    sender: EmailSender, current: str, requested: str, settings: Settings, *, raise_errors: bool = False
) -> bool:
    """Warn the account's current (verified) address the moment a change is asked for, while it
    can still be stopped: a password reset from this address cancels it."""
    reset = f"{settings.app_base_url.rstrip('/')}/forgot-password"
    return _deliver(
        sender,
        Email(
            to=current,
            subject="Someone asked to change your CodeCoach AI email",
            text=(
                f"Someone signed in to your CodeCoach AI account asked to change its email to {requested}.\n\n"
                "If that was you, there's nothing to do: the change happens once the new address is "
                "confirmed.\n\nIf it wasn't you, reset your password now from this address. That cancels "
                f"the change and signs out every device:\n{reset}\n"
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
    address = target_address(user)
    if address is None:
        return 0.0
    latest = db.scalar(
        select(EmailVerificationToken.created_at)
        .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.email == address)
        .order_by(EmailVerificationToken.created_at.desc())
        .limit(1)
    )
    if latest is None:
        return 0.0
    return max(0.0, (RESEND_COOLDOWN - (now - _aware(latest))).total_seconds())


@dataclass
class Confirmed:
    user: User
    # Set when a confirmed code completed an email change and the previous address was verified:
    # that address is told (an unverified one was never proven to be the owner's).
    notify_old: str | None = None


def _complete(db: Session, user: User, address: str, now: datetime) -> Confirmed:
    """Mark `address` verified for `user`: the current address, or a pending new one (which then
    becomes the account's address). Commits."""
    if address == user.pending_email and address != user.email:
        taken = db.scalar(select(User.id).where(User.email == address, User.id != user.id))
        if taken:
            drop_pending(db, user)
            db.commit()
            raise ConflictError(
                "That address now belongs to another account, so the change was cancelled. Your email is unchanged.",
                code="email_taken",
            )
        previous, previous_verified = user.email, user.email_verified_at is not None
        user.email, user.email_verified_at = address, now
        user.pending_email = user.pending_email_at = None
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ConflictError("That address now belongs to another account.", code="email_taken") from None
        return Confirmed(user, previous if previous and previous_verified else None)
    if address == user.email:
        user.email_verified_at = user.email_verified_at or now
        db.commit()
        return Confirmed(user)
    db.rollback()
    raise AppError(INVALID, code="invalid_verification_token")


def confirm(db: Session, raw: str) -> Confirmed:
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
    # The address this link was for must still be the account's address or its pending change.
    if user is None or claimed.email not in (user.email, user.pending_email):
        db.rollback()
        raise AppError(INVALID, code="invalid_verification_token")
    return _complete(db, user, claimed.email, now)


def _superseded(
    db: Session, user: User, address: str, before: datetime, code: str, settings: Settings
) -> bool:
    """Is `code` one of this address's older codes, replaced by a newer email?"""
    older = db.scalars(
        select(EmailVerificationToken.code_hash).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.email == address,
            EmailVerificationToken.created_at < before,
        )
    ).all()
    candidates = [_code_hash(key, user.id, code) for key in settings.verification_keys]
    return any(hmac.compare_digest(h, c) for h in older for c in candidates)


def confirm_code(db: Session, user: User, code: str, settings: Settings) -> Confirmed:
    """Verify with the 6-digit code from the latest email (signed-in user only): the current
    address, or a pending new one.

    Each attempt is counted with one conditional UPDATE before the code is compared, so parallel
    guesses can't share a count and get more than MAX_CODE_ATTEMPTS tries. A code is claimed the
    same way, so it works once."""
    address = target_address(user)
    if address is None:
        return Confirmed(user)  # nothing waiting to be confirmed
    now = datetime.now(UTC)
    code = code.strip()
    row = db.scalar(
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.email == address,
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
        superseded = _superseded(db, user, address, created, code, settings)
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
        db.rollback()  # a parallel request used it first: that request completed it
        db.refresh(user)
        if target_address(user) != address:
            return Confirmed(user)
        raise AppError("That code has already been used. Send a new one.", code="invalid_verification_code")
    return _complete(db, user, address, now)


def drop_pending(db: Session, user: User) -> None:
    """Drop a pending change of address: its codes and links stop working. Doesn't commit, so a
    password reset or change can drop it in the same transaction as the new password."""
    if user.pending_email:
        db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.email == user.pending_email,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        user.pending_email = user.pending_email_at = None


def cancel_pending(db: Session, user: User) -> User:
    """The person cancels a pending change of address. Commits."""
    drop_pending(db, user)
    db.commit()
    return user
