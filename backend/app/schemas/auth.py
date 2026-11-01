from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import APIModel


def _password_rules(v: str) -> str:
    if v.strip() != v:
        raise ValueError("password must not start or end with whitespace")
    if v.lower() == v or v.upper() == v or not any(ch.isdigit() for ch in v):
        raise ValueError("password needs upper- and lower-case letters and at least one digit")
    return v


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128, examples=["CorrectHorse42"])
    display_name: str | None = Field(default=None, min_length=1, max_length=40, examples=["Ada"])

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _password_rules(v)


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GuestSessionRequest(APIModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)


class ChangePasswordRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _password_rules(v)


class UserOut(APIModel):
    id: str
    email: str | None
    display_name: str | None
    is_guest: bool
    created_at: datetime


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut
