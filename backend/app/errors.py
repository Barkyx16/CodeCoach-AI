"""Consistent error envelopes: {"error": {"code", "message", "request_id", "details"}}."""

from __future__ import annotations

import logging
import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("codecoach.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: Any | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class GoneError(AppError):
    """The thing existed but has been turned off for good (e.g. a revoked or expired share link)."""

    status_code = 410
    code = "gone"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    @classmethod
    def wait(
        cls, message: str, retry_after: float, *, code: str | None = None, **details: Any
    ) -> RateLimitedError:
        """A 429 that says how long to wait: whole seconds, at least 1, in the body and in a
        Retry-After header."""
        seconds = max(1, math.ceil(retry_after))
        return cls(message, code=code, details={"retry_after_seconds": seconds, **details})


def _retry_after(details: Any) -> str | None:
    """Whole seconds for a Retry-After header, from a 429's details (never less than 1)."""
    value = details.get("retry_after_seconds") if isinstance(details, dict) else None
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(max(1, math.ceil(value)))
    return None


def _envelope(request: Request, status: int, code: str, message: str, details: Any = None):
    request_id = getattr(request.state, "request_id", None)
    body = {"error": {"code": code, "message": message, "request_id": request_id, "details": details}}
    headers = {"X-Request-ID": request_id} if request_id else None
    if status == 401:
        headers = {**(headers or {}), "WWW-Authenticate": "Bearer"}
    if status == 429 and (wait := _retry_after(details)) is not None:
        # Standard header (RFC 9110) as well as the body field, so clients and proxies can back off.
        headers = {**(headers or {}), "Retry-After": wait}
    return JSONResponse(status_code=status, content=body, headers=headers)


def error_response(request: Request, exc: AppError) -> JSONResponse:
    """The standard envelope for an AppError, for routes that must also modify the response
    (e.g. clear a cookie) instead of just raising."""
    return _envelope(request, exc.status_code, exc.code, exc.message, exc.details)


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    429: "rate_limited",
    503: "unavailable",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()
        ]
        return _envelope(request, 422, "validation_error", "Request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return _envelope(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(SQLAlchemyTimeoutError)
    async def _busy(request: Request, exc: SQLAlchemyTimeoutError):
        # Every database connection stayed busy for DB_POOL_TIMEOUT_SECONDS: overloaded. Shed the
        # request with a clear, retryable answer rather than a generic failure. Nothing was done.
        logger.warning(
            "database pool exhausted", extra={"request_id": getattr(request.state, "request_id", None)}
        )
        response = _envelope(
            request, 503, "server_busy", "The server is very busy right now. Please try again in a moment."
        )
        response.headers["Retry-After"] = "2"
        return response

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return _envelope(request, 500, "internal_error", "An unexpected error occurred")
