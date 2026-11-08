"""Request IDs and structured (JSON) request logging."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app import tracing

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
access_log = logging.getLogger("codecoach.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for key in (
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "trace_id",
            "span_id",
            "parent_id",
            "span",
            "outcome",
            "attrs",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger("codecoach")
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID (client-supplied if well-formed) and a trace, and log one line per request.

    The trace id comes from the browser's W3C `traceparent` when it is valid, so the browser's
    measurements and these server spans belong to the same trace; otherwise one is started here.
    The response carries both ids (`X-Request-ID`, `X-Trace-ID`).
    """

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        parent = tracing.parse_traceparent(request.headers.get("traceparent"))
        metrics = getattr(request.app.state, "metrics", None)
        store = getattr(request.app.state, "traces", None)
        start = time.perf_counter()
        with tracing.start_trace(
            trace_id=parent[0] if parent else None,
            parent_span_id=parent[1] if parent else None,
            request_id=request_id,
            store=store,
            metrics=metrics,
        ) as trace:
            request.state.trace_id = trace.trace_id
            with tracing.span("http", method=request.method) as http_span:
                try:
                    response = await call_next(request)
                except Exception:
                    # Unhandled: the outer error handler answers 500. Record it here, then re-raise.
                    template = _route_template(request)
                    http_span.set(route=template, status=500)
                    _log_request(request, request_id, trace.trace_id, 500, start, metrics, template)
                    raise
                template = _route_template(request)
                http_span.set(route=template, status=response.status_code)
                if response.status_code >= 500:
                    http_span.outcome = "error"
                elif response.status_code >= 400:
                    http_span.outcome = "rejected"
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace.trace_id
        label = getattr(getattr(request.app.state, "settings", None), "instance_label", None)
        if label:
            response.headers["X-CodeCoach-Instance"] = label
        _log_request(request, request_id, trace.trace_id, response.status_code, start, metrics, template)
        return response


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def _log_request(
    request: Request, request_id: str, trace_id: str, status: int, start: float, metrics, template: str
) -> None:
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    if metrics is not None:
        metrics.observe(request.method, template, status, duration_ms / 1000)
    access_log.info(
        "request",
        extra={
            "request_id": request_id,
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": duration_ms,
        },
    )
