"""What the browser saw of a user action, and the admin lookup that joins it to the server's spans.

The browser reports how each interview-round action ended on screen: rendered, rejected by the
server, a network failure, a success the page never showed, or a click that was ignored. Each
report is a fixed vocabulary plus a duration and the action's trace and request ids. No answers,
no page content, no user, interview or question ids. It goes to this API only (never a third
party), can be switched off (`UI_TELEMETRY_ENABLED=false`), is rate-limited per account and is
dropped, never retried, when over the limit.
"""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends, Path, Request, Response, status
from pydantic import Field

from app.api.deps import get_current_user, require_admin
from app.errors import NotFoundError
from app.models import User
from app.schemas.common import APIModel, error_responses

router = APIRouter(prefix="/api/v1", tags=["telemetry"])

UiAction = Literal["answer", "skip", "reply", "skip_followup"]
UiOutcome = Literal["rendered", "rejected", "server_error", "network_error", "not_rendered", "ignored"]


class UiEvent(APIModel):
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$", description="The action's W3C trace id")
    action: UiAction
    outcome: UiOutcome = Field(
        description="rendered: the next state was on screen; rejected: the server refused it; "
        "server_error: the server failed; "
        "network_error: no answer arrived; not_rendered: the server answered but the screen didn't "
        "change; ignored: the click didn't send anything"
    )
    duration_ms: int = Field(ge=0, le=600_000, description="From the click to the outcome, in the browser")
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{8,64}$")
    status: int | None = Field(default=None, ge=0, le=599, description="HTTP status, 0 for no response")
    error_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,40}$")


class UiEventBatch(APIModel):
    events: list[UiEvent] = Field(min_length=1, max_length=20)


class TraceSpanOut(APIModel):
    span_id: str
    parent_id: str | None
    name: str
    started_at: float = Field(description="Unix time, seconds")
    duration_ms: float
    outcome: str
    attrs: dict[str, str | int | float | bool]
    request_id: str | None
    source: str


class TraceEventOut(APIModel):
    source: str
    action: str
    outcome: str
    duration_ms: int
    request_id: str | None
    status: int | None
    error_code: str | None
    at: float = Field(description="Unix time the server received it, seconds")


class TraceOut(APIModel):
    trace_id: str
    spans: list[TraceSpanOut] = Field(description="Server steps, in start order")
    events: list[TraceEventOut] = Field(description="What the browser reported for this action")


@router.post(
    "/telemetry/ui",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404, 422),
    summary="Report how a round action ended in the browser (outcome and timing only)",
)
def ui_events(body: UiEventBatch, request: Request, user: User = Depends(get_current_user)) -> Response:
    state = request.app.state
    if not state.settings.ui_telemetry_enabled:
        raise NotFoundError("Not found.")
    metrics = state.metrics
    allowed, _ = state.telemetry_limiter.hit(f"ui-telemetry:{user.id}")
    if not allowed:  # over the limit: drop quietly; the browser never retries
        if metrics is not None:
            metrics.telemetry_dropped.labels("ui_rate_limited").inc(len(body.events))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    now = time.time()
    for event in body.events:
        if metrics is not None:
            metrics.ui_action(event.action, event.outcome, event.duration_ms / 1000)
        if state.traces is not None:
            state.traces.add_event(event.trace_id, {"source": "browser", **event.model_dump(), "at": now})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/traces/{lookup}",
    response_model=TraceOut,
    responses=error_responses(401, 403, 404),
    summary="Admin: one action's trace (server spans and browser reports) by trace id or request id",
)
def get_trace(
    request: Request,
    lookup: str = Path(pattern=r"^[A-Za-z0-9._-]{8,64}$"),
    _: User = Depends(require_admin),
) -> TraceOut:
    store = request.app.state.traces
    found = store.get(lookup) if store is not None else None
    if found is None:
        raise NotFoundError(
            "No recent trace with that id on this server. Traces are kept in memory for a limited time.",
            code="trace_not_found",
        )
    return TraceOut.model_validate(found)
