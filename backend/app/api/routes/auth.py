import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Header, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.careers import DEFAULT_TRACK
from app.config import Settings
from app.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    RateLimitedError,
    UnauthorizedError,
    error_response,
)
from app.models import User, new_id
from app.schemas.auth import (
    AcceptedResponse,
    ChangeEmailRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    GuestSessionRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UpgradeGuestRequest,
    UserOut,
    VerifyCodeRequest,
    VerifyEmailRequest,
)
from app.schemas.common import error_responses
from app.services import email_verification, outbox, password_reset
from app.services import refresh as refresh_tokens
from app.services.auth import hash_password, issue_access_token, needs_rehash, verify_password
from app.services.rate_limit import client_key

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_ERRORS = error_responses(401, 409, 422, 429)


def _throttle(request: Request) -> None:
    allowed, retry_after = request.app.state.auth_limiter.hit(f"auth:{client_key(request)}")
    if not allowed:
        raise RateLimitedError.wait("Too many attempts. Wait a minute and try again.", retry_after)


def _account_key(email: str) -> str:
    # Hashed: the counter table never holds addresses. Unknown addresses are counted the same
    # way as registered ones, so a 429 here doesn't reveal whether an account exists.
    return "login-fail:" + hashlib.sha256(email.lower().encode()).hexdigest()[:40]


def _check_account_failures(request: Request, email: str) -> None:
    """Many wrong passwords for one address (from any number of addresses) pause sign-in to
    it for a while. Password reset still works, and the per-IP limit still applies."""
    allowed, retry_after = request.app.state.login_failure_limiter.peek(_account_key(email))
    if not allowed:
        raise RateLimitedError.wait(
            "Too many wrong passwords for this account. Wait a few minutes, or reset your password.",
            retry_after,
            code="account_throttled",
        )


def _send_email(
    request: Request,
    background: BackgroundTasks,
    db: Session,
    settings: Settings,
    kind: str,
    *,
    user_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Record the email as a durable job, then try it right after the response. If that try
    fails (or this process stops first), the background jobs loop retries it (services/outbox.py)."""
    job = outbox.enqueue(db, kind, user_id=user_id, payload=payload)
    db.commit()
    background.add_task(
        outbox.run, request.app.state.session_factory, job.id, settings, request.app.state.email_sender
    )


def _token_response(user: User, settings: Settings) -> TokenResponse:
    token, expires = issue_access_token(
        settings.signing_key,
        user_id=user.id,
        token_version=user.token_version,
        ttl=timedelta(minutes=settings.access_token_ttl_minutes),
    )
    return TokenResponse(access_token=token, expires_at=expires, user=UserOut.model_validate(user))


def _set_refresh_cookie(response: Response, raw: str, settings: Settings) -> None:
    response.set_cookie(
        refresh_tokens.COOKIE_NAME,
        raw,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=refresh_tokens.COOKIE_PATH,  # only ever sent to the auth endpoints
        httponly=True,  # page scripts can't read it
        secure=settings.cookie_secure,
        samesite="strict",  # never sent on cross-site requests
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        refresh_tokens.COOKIE_NAME,
        path=refresh_tokens.COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _start_session(db: Session, user: User, response: Response, settings: Settings) -> TokenResponse:
    """New sign-in: a fresh refresh-token family in the cookie, an access token in the body."""
    raw = refresh_tokens.issue(db, user, settings)
    db.commit()
    _set_refresh_cookie(response, raw, settings)
    return _token_response(user, settings)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
    responses=_ERRORS,
    summary="Create an account and get an access token",
)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    _throttle(request)
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("An account with this email already exists", code="email_taken")
    user = User(
        email=email,
        auth_provider_id=f"password:{new_id()}",
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        career_track=body.career_track or DEFAULT_TRACK,
        is_guest=False,
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent registration with the same email
        db.rollback()
        raise ConflictError("An account with this email already exists", code="email_taken") from exc
    _send_email(request, background, db, settings, "verify_email", user_id=user.id)
    return _start_session(db, user, response, settings)


@router.post(
    "/login", response_model=TokenResponse, responses=_ERRORS, summary="Log in with email and password"
)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    _throttle(request)
    _check_account_failures(request, body.email)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # verify_password runs a full hash comparison even when the user doesn't exist, and the
    # error message is identical either way, so attackers can't probe which emails exist.
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        request.app.state.login_failure_limiter.hit(_account_key(body.email))
        raise UnauthorizedError("Incorrect email or password", code="invalid_credentials")
    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return _start_session(db, user, response, settings)


@router.post(
    "/guest",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
    responses=_ERRORS,
    summary="Start a demo session without an account",
)
def guest(
    request: Request,
    response: Response,
    body: GuestSessionRequest | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    if not settings.allow_guest_sessions:
        raise AppError("Guest sessions are disabled", code="guest_disabled")
    _throttle(request)
    user = User(
        auth_provider_id=f"guest:{new_id()}",
        is_guest=True,
        display_name=(body.display_name if body else None) or "Guest",
        career_track=(body.career_track if body else None) or DEFAULT_TRACK,
    )
    db.add(user)
    db.commit()
    return _start_session(db, user, response, settings)


@router.post(
    "/upgrade",
    response_model=TokenResponse,
    responses=_ERRORS,
    summary="Turn the current guest account into a full account, keeping all of its data",
)
def upgrade_guest(
    body: UpgradeGuestRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    _throttle(request)
    if not user.is_guest:
        raise ConflictError("This is already a full account.", code="not_a_guest")
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("An account with this email already exists", code="email_taken")
    user.email = email
    user.password_hash = hash_password(body.password)
    user.auth_provider_id = f"password:{new_id()}"
    user.is_guest = False  # no longer subject to guest retention
    if body.display_name:
        user.display_name = body.display_name
    if body.career_track:
        user.career_track = body.career_track
    user.last_login_at = datetime.now(UTC)
    refresh_tokens.revoke_all(db, user)  # the guest session's cookie is replaced below
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent registration with the same email
        db.rollback()
        raise ConflictError("An account with this email already exists", code="email_taken") from exc
    _send_email(request, background, db, settings, "verify_email", user_id=user.id)
    return _start_session(db, user, response, settings)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses=error_responses(401, 403),
    summary="Exchange the refresh cookie for a new access token (rotates the cookie)",
)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    cc_refresh: str | None = Cookie(default=None),
    x_requested_with: str | None = Header(default=None),
    x_refresh_attempt: str | None = Header(
        default=None,
        description=(
            "A random key (22-64 URL-safe characters) the app keeps for this refresh attempt until "
            "it learns the outcome. If the response is lost, presenting the same cookie with the same "
            "key shortly afterwards returns the same new session instead of ending it."
        ),
    ),
) -> TokenResponse:
    # CSRF defence in depth (the cookie is already SameSite=Strict): require a custom header,
    # which a cross-site page can't send without a CORS preflight that our allowlist rejects,
    # and refuse any Origin that isn't one of ours.
    origin = request.headers.get("origin")
    if x_requested_with != "codecoach" or (origin and origin not in settings.cors_origins):
        raise ForbiddenError("Refresh must come from the CodeCoach app.", code="csrf_rejected")
    # Its own, generous bucket: every open tab refreshes, so the sign-in limit would be too tight.
    # The app treats a 429 here as "try again later", never as signed out.
    allowed, retry_after = request.app.state.refresh_limiter.hit(f"refresh:{client_key(request)}")
    if not allowed:
        raise RateLimitedError.wait("Too many session refreshes. Try again in a moment.", retry_after)
    try:
        attempt = refresh_tokens.valid_attempt_key(x_refresh_attempt)
        user, raw = refresh_tokens.rotate(db, cc_refresh, settings, attempt=attempt)
    except UnauthorizedError as exc:
        failed = error_response(request, exc)
        if exc.code != "refresh_race":  # a racing tab still holds a valid cookie: keep it
            _clear_refresh_cookie(failed, settings)
        return failed  # type: ignore[return-value]
    db.commit()
    _set_refresh_cookie(response, raw, settings)
    return _token_response(user, settings)


@router.post(
    "/verify-email",
    response_model=UserOut,
    responses=error_responses(400, 422),
    summary="Confirm an email address with the emailed link (no sign-in needed)",
)
def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    _throttle(request)
    return _after_confirm(request, background, db, settings, email_verification.confirm(db, body.token))


def _after_confirm(
    request: Request,
    background: BackgroundTasks,
    db: Session,
    settings: Settings,
    done: email_verification.Confirmed,
) -> User:
    """An email change just completed: tell the previous (verified) address."""
    if done.notify_old and done.user.email:
        _send_email(
            request,
            background,
            db,
            settings,
            "email_changed",
            user_id=done.user.id,
            payload={"old": done.notify_old, "new": done.user.email},
        )
    return done.user


@router.post(
    "/verify-email/code",
    response_model=UserOut,
    responses=_ERRORS,
    summary="Confirm your email with the 6-digit code from the email (5 tries per code)",
)
def verify_email_code(
    body: VerifyCodeRequest,
    request: Request,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    _throttle(request)
    done = email_verification.confirm_code(db, user, body.code, settings)
    return _after_confirm(request, background, db, settings, done)


@router.post(
    "/verify-email/resend",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
    responses=_ERRORS,
    summary="Send a new verification link to your current email",
)
def resend_verification(
    request: Request,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AcceptedResponse:
    _throttle(request)  # the email itself is also limited per account (one a minute)
    if user.is_guest or not user.email:
        raise ConflictError("Guest accounts have no email to verify.", code="not_applicable")
    address = email_verification.target_address(user)
    if address is None:
        raise ConflictError("This email is already verified.", code="already_verified")
    wait = email_verification.cooldown_remaining(db, user)
    if wait > 0:
        raise RateLimitedError.wait(
            f"A code was sent less than a minute ago. You can ask for another in {int(wait) + 1} seconds.",
            wait,
            code="resend_cooldown",
        )
    _send_email(request, background, db, settings, "verify_email", user_id=user.id)
    return AcceptedResponse(
        message=f"A new code is on its way to {address}. It replaces the one before, so use the newest email."
    )


@router.post(
    "/email",
    response_model=UserOut,
    responses=_ERRORS,
    summary="Ask to change your email (needs your password); it changes once the new address confirms",
)
def change_email(
    body: ChangeEmailRequest,
    request: Request,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    """Nothing changes yet: the new address gets a code, and the account keeps its current
    address (for sign-in and recovery) until that code or link is used. A verified current
    address is warned at once, and a password reset from it cancels the change."""
    _throttle(request)
    if user.is_guest or not verify_password(user.password_hash, body.password):
        raise UnauthorizedError("Password is incorrect", code="invalid_credentials")
    new_email = body.new_email.lower()
    if new_email == user.email:
        if user.pending_email:
            email_verification.cancel_pending(db, user)
        raise ConflictError("That's already your email.", code="same_email")
    if db.scalar(select(User.id).where(User.email == new_email)):
        raise ConflictError("An account with this email already exists", code="email_taken")
    if user.pending_email and user.pending_email != new_email:
        email_verification.drop_pending(db, user)  # the earlier request's codes stop working
    user.pending_email, user.pending_email_at = new_email, datetime.now(UTC)
    db.commit()
    _send_email(request, background, db, settings, "verify_email", user_id=user.id)
    if user.email and user.email_verified_at is not None:
        _send_email(
            request,
            background,
            db,
            settings,
            "email_change_requested",
            user_id=user.id,
            payload={"current": user.email, "requested": new_email},
        )
    return user


@router.delete(
    "/email/pending",
    response_model=UserOut,
    responses=error_responses(401),
    summary="Cancel a pending change of email (its codes and links stop working)",
)
def cancel_email_change(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    return email_verification.cancel_pending(db, user)


@router.post(
    "/password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
    responses=error_responses(422, 429),
    summary="Email a password reset link (same answer whether or not the account exists)",
)
def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AcceptedResponse:
    _throttle(request)
    # The lookup and the email happen after the response is sent: the reply and its timing are
    # identical for registered and unknown addresses (a job is recorded either way).
    _send_email(
        request, background, db, settings, "password_reset", payload={"email": str(body.email).lower()}
    )
    return AcceptedResponse(
        message="If an account exists for that email, we've sent a link to reset the password."
    )


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 422, 429),
    summary="Set a new password with a reset link (signs out every session)",
)
def confirm_password_reset(
    body: PasswordResetConfirm,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    _throttle(request)
    password_reset.confirm_reset(db, body.token, body.new_password)
    _clear_refresh_cookie(response, settings)


@router.get("/me", response_model=UserOut, responses=_ERRORS, summary="The current user")
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Sign out of this device (ends this session's refresh cookie)",
)
def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    cc_refresh: str | None = Cookie(default=None),
) -> None:
    row = refresh_tokens.find(db, cc_refresh)
    if row is not None and row.user_id == user.id:
        refresh_tokens.revoke_family(db, row.family_id)
        db.commit()
    # The access token in this tab is discarded by the client and expires within 15 minutes.
    _clear_refresh_cookie(response, settings)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Sign out of every device (revokes all access and refresh tokens)",
)
def logout_all(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    user.token_version += 1  # every access and refresh token issued so far stops working
    refresh_tokens.revoke_all(db, user)
    db.commit()
    _clear_refresh_cookie(response, settings)


@router.post(
    "/password",
    response_model=TokenResponse,
    responses=_ERRORS,
    summary="Change password (revokes other sessions, returns a fresh token)",
)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    _throttle(request)
    if user.is_guest or not verify_password(user.password_hash, body.current_password):
        raise UnauthorizedError("Current password is incorrect", code="invalid_credentials")
    user.password_hash = hash_password(body.new_password)
    # A pending change of address may have been asked for by whoever had the old password; its
    # emailed link works signed out, so ending their session alone wouldn't stop it.
    email_verification.drop_pending(db, user)
    user.token_version += 1  # other sessions end
    refresh_tokens.revoke_all(db, user)
    db.commit()
    return _start_session(db, user, response, settings)  # this session continues


@router.patch("/me", response_model=UserOut, responses=_ERRORS, summary="Update your profile")
def update_me(
    body: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    # Partial update: a field that wasn't sent is left alone (so changing the track keeps the name).
    if "display_name" in body.model_fields_set:
        user.display_name = body.display_name.strip() if body.display_name else None
    if body.career_track:
        user.career_track = body.career_track
    db.commit()
    return user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Permanently delete your account and all of your data",
)
def delete_me(
    body: DeleteAccountRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    _throttle(request)
    if body.confirm != "DELETE":
        raise AppError('Type "DELETE" to confirm.', code="confirmation_required")
    if not user.is_guest and not verify_password(user.password_hash, body.password or ""):
        raise UnauthorizedError("Password is incorrect", code="invalid_credentials")
    # Submissions, results, AI interactions, interview sessions/turns and progress events are
    # removed by ON DELETE CASCADE foreign keys, in the same transaction.
    db.delete(user)  # refresh tokens are removed by ON DELETE CASCADE too
    db.commit()
    _clear_refresh_cookie(response, settings)
