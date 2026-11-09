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
    429: "Rate limit or AI budget exceeded",
    503: "Temporarily unavailable (e.g. the judge queue is full)",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries documenting the shared error envelope."""
    return {c: {"model": ErrorEnvelope, "description": _ERROR_DESCRIPTIONS.get(c, "Error")} for c in codes}
