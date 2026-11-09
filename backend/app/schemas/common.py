from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

T = TypeVar("T")


def _blank_is_none(value: Any) -> Any:
    return None if isinstance(value, str) and not value.strip() else value


# A request key (`client_request_id`) that is empty or blank means "no key", on every route
# (Volume 8, prompt 2). Stored as-is, "" would be one shared key for every keyless request, so a
# second, different create would come back as the first.
OptionalKey = Annotated[str | None, BeforeValidator(_blank_is_none)]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


KEY_DESCRIPTION_UPDATE = (
    "One key per save (Volume 8, prompt 3). Sent again with the same base revision and content after "
    "its reply was lost, it's answered with `save_replay` instead of a conflict with your own save. "
    "Another entity, base or content under the same key is a 409 `idempotency_key_reused`. Without a "
    "key, a stale save is a conflict, as before."
)


class SaveReplay(APIModel):
    """Set when this save had already been accepted under its key (its first reply was lost)."""

    accepted_revision: int = Field(description="The revision your earlier save produced")
    current_revision: int = Field(
        description="The revision now. Greater than accepted_revision: it was changed after your save "
        "(maybe on another device); what's returned is that newer version, not yours"
    )


def update_key_field() -> Any:
    return Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description=KEY_DESCRIPTION_UPDATE,
    )


def save_replay_field() -> Any:
    return Field(default=None, description="Only on a save recovered by its key: see SaveReplay")


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int = Field(description="Total matching items across all pages")
    page: int
    page_size: int


class ErrorBody(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str
    request_id: str | None = None
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    """Every non-2xx response uses this shape."""

    error: ErrorBody


_ERROR_DESCRIPTIONS = {
    400: "Bad request",
    401: "Missing, invalid, expired or revoked access token",
    404: "Not found (also returned for resources owned by another user)",
    409: "Conflict with current state",
    413: "Payload too large",
    422: "Request validation failed",
    428: "A required precondition (e.g. the revision an edit started from) was missing",
    429: "Rate limit or AI budget exceeded",
    503: "Temporarily unavailable (e.g. the judge queue is full)",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries documenting the shared error envelope."""
    return {c: {"model": ErrorEnvelope, "description": _ERROR_DESCRIPTIONS.get(c, "Error")} for c in codes}
