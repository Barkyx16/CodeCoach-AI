from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


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
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries documenting the shared error envelope."""
    return {c: {"model": ErrorEnvelope, "description": _ERROR_DESCRIPTIONS.get(c, "Error")} for c in codes}
