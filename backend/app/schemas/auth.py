from datetime import datetime

from pydantic import EmailStr, Field, field_validator, model_validator

from app.careers import DEFAULT_TRACK, is_track
from app.schemas.common import APIModel


def _password_rules(v: str) -> str:
    if v.strip() != v:
        raise ValueError("password must not start or end with whitespace")
    if v.lower() == v or v.upper() == v or not any(ch.isdigit() for ch in v):
        raise ValueError("password needs upper- and lower-case letters and at least one digit")
    return v


def _track_rule(v: str | None) -> str | None:
    if v is not None and not is_track(v):
        raise ValueError("unknown career track; see GET /api/v1/careers")
    return v


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128, examples=["CorrectHorse42"])
    display_name: str | None = Field(default=None, min_length=1, max_length=40, examples=["Ada"])
    career_track: str | None = Field(
        default=None,
        max_length=64,
        description="The job you're preparing for (a slug from /careers)",
        examples=["registered-nurse"],
    )

    @field_validator("career_track")
    @classmethod
    def _check_track(cls, v: str | None) -> str | None:
        return _track_rule(v)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _password_rules(v)


class UpgradeGuestRequest(RegisterRequest):
    """Same fields and rules as registration; the guest's data is kept."""


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GuestSessionRequest(APIModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    career_track: str | None = Field(default=None, max_length=64)

    @field_validator("career_track")
    @classmethod
    def _check_track(cls, v: str | None) -> str | None:
        return _track_rule(v)


class ChangePasswordRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _password_rules(v)


class VerifyEmailRequest(APIModel):
    token: str = Field(min_length=20, max_length=200)


class VerifyCodeRequest(APIModel):
    code: str = Field(pattern=r"^\s*\d{6}\s*$", description="The 6-digit code from the email")


class ChangeEmailRequest(APIModel):
    new_email: EmailStr
    password: str = Field(min_length=1, max_length=128, description="Your current password")


class PasswordResetRequest(APIModel):
    email: EmailStr


class PasswordResetConfirm(APIModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _password_rules(v)


class AcceptedResponse(APIModel):
    status: str = "accepted"
    message: str


class UpdateProfileRequest(APIModel):
    """Only the fields you send are changed. Send display_name: null to clear the name."""

    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    career_track: str | None = Field(
        default=None, max_length=64, description="Switch the job you're preparing for"
    )

    @field_validator("career_track")
    @classmethod
    def _check_track(cls, v: str | None) -> str | None:
        return _track_rule(v)


class DeleteAccountRequest(APIModel):
    password: str | None = Field(
        default=None, max_length=128, description="Required for email/password accounts; omitted for guests"
    )
    confirm: str = Field(description='Must be the word "DELETE" to prevent accidents', examples=["DELETE"])


class UserOut(APIModel):
    id: str
    email: str | None
    display_name: str | None
    is_guest: bool
    created_at: datetime
    email_verified: bool = Field(description="The owner confirmed this email address")
    career_track: str = Field(description="The job this person is preparing for")
    is_admin: bool = Field(
        default=False, description="Can triage content reports (granted from the command line)"
    )
    pending_email: str | None = Field(
        default=None,
        description="A new address waiting to be confirmed with the code sent to it. Until then, "
        "`email` is still the account's address.",
    )

    @model_validator(mode="before")
    @classmethod
    def _verified_from_model(cls, data: object) -> object:
        # From the ORM model, derive the flag from the timestamp.
        if hasattr(data, "email_verified_at"):
            return {
                "id": data.id,  # type: ignore[attr-defined]
                "email": data.email,  # type: ignore[attr-defined]
                "display_name": data.display_name,  # type: ignore[attr-defined]
                "is_guest": data.is_guest,  # type: ignore[attr-defined]
                "created_at": data.created_at,  # type: ignore[attr-defined]
                "email_verified": data.email_verified_at is not None,
                "career_track": data.career_track or DEFAULT_TRACK,  # type: ignore[attr-defined]
                "is_admin": bool(getattr(data, "is_admin", False)),
                "pending_email": getattr(data, "pending_email", None),
            }
        return data


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut
