from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings_dep
from app.config import Settings
from app.errors import AppError, ConflictError, RateLimitedError, UnauthorizedError
from app.models import User, new_id
from app.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    GuestSessionRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)
from app.schemas.common import error_responses
from app.services.auth import hash_password, issue_access_token, needs_rehash, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_ERRORS = error_responses(401, 409, 422, 429)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _throttle(request: Request) -> None:
    allowed, retry_after = request.app.state.auth_limiter.hit(_client_key(request))
    if not allowed:
        raise RateLimitedError(
            "Too many attempts. Wait a minute and try again.",
            details={"retry_after_seconds": round(retry_after, 1)},
        )


def _token_response(user: User, settings: Settings) -> TokenResponse:
    token, expires = issue_access_token(
        settings.secret_key,
        user_id=user.id,
        token_version=user.token_version,
        ttl=timedelta(minutes=settings.access_token_ttl_minutes),
    )
    return TokenResponse(access_token=token, expires_at=expires, user=UserOut.model_validate(user))


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
        is_guest=False,
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent registration with the same email
        db.rollback()
        raise ConflictError("An account with this email already exists", code="email_taken") from exc
    return _token_response(user, settings)


@router.post(
    "/login", response_model=TokenResponse, responses=_ERRORS, summary="Log in with email and password"
)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    _throttle(request)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # verify_password runs a full hash comparison even when the user doesn't exist, and the
    # error message is identical either way, so attackers can't probe which emails exist.
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        raise UnauthorizedError("Incorrect email or password", code="invalid_credentials")
    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return _token_response(user, settings)


@router.post(
    "/guest",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
    responses=_ERRORS,
    summary="Start a demo session without an account",
)
def guest(
    request: Request,
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
    )
    db.add(user)
    db.commit()
    return _token_response(user, settings)


@router.get("/me", response_model=UserOut, responses=_ERRORS, summary="The current user")
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Revoke every access token issued to this user",
)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    user.token_version += 1
    db.commit()


@router.post(
    "/password",
    response_model=TokenResponse,
    responses=_ERRORS,
    summary="Change password (revokes other sessions, returns a fresh token)",
)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    _throttle(request)
    if user.is_guest or not verify_password(user.password_hash, body.current_password):
        raise UnauthorizedError("Current password is incorrect", code="invalid_credentials")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    return _token_response(user, settings)


@router.patch("/me", response_model=UserOut, responses=_ERRORS, summary="Update your profile")
def update_me(
    body: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    user.display_name = body.display_name.strip() if body.display_name else None
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _throttle(request)
    if body.confirm != "DELETE":
        raise AppError('Type "DELETE" to confirm.', code="confirmation_required")
    if not user.is_guest and not verify_password(user.password_hash, body.password or ""):
        raise UnauthorizedError("Password is incorrect", code="invalid_credentials")
    # Submissions, results, AI interactions, interview sessions/turns and progress events are
    # removed by ON DELETE CASCADE foreign keys, in the same transaction.
    db.delete(user)
    db.commit()
