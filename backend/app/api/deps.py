"""FastAPI dependencies: database session, settings, and the authenticated user."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import UnauthorizedError
from app.models import User
from app.services.auth import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User | None:
    if credentials is None:
        return None
    claims = decode_access_token(settings.secret_key, credentials.credentials)
    if claims is None:
        raise UnauthorizedError("Invalid or expired access token", code="invalid_token")
    user = db.get(User, claims["sub"])
    if user is None or user.token_version != claims["ver"]:
        # Unknown user, or the token was revoked by logout / password change.
        raise UnauthorizedError("Access token has been revoked", code="invalid_token")
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise UnauthorizedError("Authentication required. Log in at POST /api/v1/auth/login")
    return user
