"""Traces: follow one user action through the browser, the API, evaluation, the database and the judge.

A trace is one user action (submit an answer, run code). Its id comes from the browser's W3C
`traceparent` header when the browser sends one, so the page's own measurements and the server's
steps line up; otherwise the server starts one. Inside a request, `span()` records a named step:
its duration, its outcome and a few attributes. Each span is written as one structured log line
(logger `codecoach.trace`) and kept, for a while, in a small in-memory store that an admin can
look up by trace id or request id (GET /api/v1/admin/traces/{id}). Background work (the judge
worker) carries the trace id on the job row and continues the same trace.

What is recorded, and what never is:
- span names are a fixed set chosen in code; attributes pass an allowlist (`ALLOWED_ATTRS`) and
  must be short strings, numbers or booleans: operation outcomes, formats, languages, codes;
- never request or response bodies, answers, code, transcripts, job documents, tokens, cookies,
  emails, names or user ids. Interview, question and submission ids are not attributes either.
Recording is best effort: a failure to record is counted (`codecoach_telemetry_dropped_total`)
and never fails or slows the request beyond the work already done.
"""

from __future__ import annotations

import logging
import re
import secrets
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import SQLAlchemyError

from app.errors import AppError

if TYPE_CHECKING:
    from app.metrics import Metrics

trace_log = logging.getLogger("codecoach.trace")

TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")
TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_ZERO_TRACE = "0" * 32
_ZERO_SPAN = "0" * 16

# Attribute keys a span may carry. Anything else is dropped before it is logged or stored.
ALLOWED_ATTRS = frozenset(
    {
        "route",
        "method",
        "status",
        "action",
        "result",
        "format",
        "evaluator",
        "language",
        "verdict",
        "error_code",
        "attempt",
        "provider",  # "anthropic" or "offline": which coach answered
        "queue_wait_ms",
        "duplicate",
    }
)
_MAX_ATTR_LEN = 64


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def parse_traceparent(value: str | None) -> tuple[str, str] | None:
    """(trace id, parent span id) from a W3C traceparent header, or None if it isn't valid."""
    if not value:
        return None
    match = TRACEPARENT.match(value.strip().lower())
    if not match or match.group(1) == _ZERO_TRACE or match.group(2) == _ZERO_SPAN:
        return None
    return match.group(1), match.group(2)


def clean_attrs(attrs: dict[str, Any]) -> dict[str, str | int | float | bool]:
    out: dict[str, str | int | float | bool] = {}
    for key, value in attrs.items():
        if key not in ALLOWED_ATTRS or value is None:
            continue
        if isinstance(value, bool | int | float):
            out[key] = value
        else:
            out[key] = str(value)[:_MAX_ATTR_LEN]
    return out


def categorize(exc: BaseException) -> tuple[str, str | None]:
    """A low-cardinality outcome for an exception, and the app's error code if it has one."""
    if isinstance(exc, AppError):
        return ("rejected" if exc.status_code < 500 else "error"), exc.code
    if isinstance(exc, SQLAlchemyError):
        return "db_error", None
    if isinstance(exc, TimeoutError):
        return "timeout", None
    return "error", None


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    started_at: float  # unix seconds
    duration_ms: float
    outcome: str
    attrs: dict[str, str | int | float | bool] = field(default_factory=dict)
    request_id: str | None = None
    source: str = "server"


class TraceStore:
    """Recent traces in memory, bounded by count, spans per trace and age. Thread-safe."""

    def __init__(self, max_traces: int = 500, max_spans: int = 200, ttl_seconds: float = 3600.0):
        self.max_traces = max_traces
        self.max_spans = max_spans
        self.ttl = ttl_seconds
        self._lock = threading.Lock()
        self._traces: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._by_request: OrderedDict[str, str] = OrderedDict()

    def _entry(self, trace_id: str, now: float) -> dict[str, Any]:
        entry = self._traces.get(trace_id)
        if entry is None:
            entry = {
                "spans": deque(maxlen=self.max_spans),
                "events": deque(maxlen=self.max_spans),
                "seen": now,
            }
            self._traces[trace_id] = entry
        entry["seen"] = now
        self._traces.move_to_end(trace_id)
        while len(self._traces) > self.max_traces:
            self._traces.popitem(last=False)
        return entry

    def add_span(self, record: SpanRecord) -> None:
        now = time.time()
        with self._lock:
            self._entry(record.trace_id, now)["spans"].append(record)
            if record.request_id:
                self._by_request[record.request_id] = record.trace_id
                self._by_request.move_to_end(record.request_id)
                while len(self._by_request) > self.max_traces * 4:
                    self._by_request.popitem(last=False)

    def add_event(self, trace_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            self._entry(trace_id, time.time())["events"].append(event)
            request_id = event.get("request_id")
            if request_id:
                self._by_request.setdefault(request_id, trace_id)

    def get(self, lookup: str) -> dict[str, Any] | None:
        """A trace by its id, or by the id of any request in it."""
        now = time.time()
        with self._lock:
            trace_id = lookup if lookup in self._traces else self._by_request.get(lookup)
            entry = self._traces.get(trace_id) if trace_id else None
            if entry is None or now - entry["seen"] > self.ttl:
                return None
            spans = sorted(entry["spans"], key=lambda s: s.started_at)
            return {
                "trace_id": trace_id,
                "spans": [asdict(s) for s in spans],
                "events": sorted(entry["events"], key=lambda e: e.get("at", 0)),
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._traces)


@dataclass
class _Context:
    trace_id: str
    request_id: str | None
    store: TraceStore | None
    metrics: Metrics | None
    span_stack: list[str] = field(default_factory=list)


_current: ContextVar[_Context | None] = ContextVar("codecoach_trace", default=None)


def current_trace_id() -> str | None:
    ctx = _current.get()
    return ctx.trace_id if ctx else None


@contextmanager
def start_trace(
    *,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    request_id: str | None = None,
    store: TraceStore | None = None,
    metrics: Metrics | None = None,
) -> Iterator[_Context]:
    """Make this the current trace for the duration (a request, or one background job)."""
    if trace_id is None or not TRACE_ID.match(trace_id) or trace_id == _ZERO_TRACE:
        trace_id = new_trace_id()
    ctx = _Context(trace_id, request_id, store, metrics, [parent_span_id] if parent_span_id else [])
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)  # never let one request's or job's trace leak into the next


class Span:
    """A step being timed. Set `result`/attrs as the outcome becomes known."""

    def __init__(self, name: str, attrs: dict[str, Any]):
        self.name = name
        self.attrs = dict(attrs)
        self.outcome: str | None = None

    def set(self, **attrs: Any) -> None:
        self.attrs.update(attrs)


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Span]:
    """Time a named step inside the current trace. Outside a trace it only runs the block."""
    ctx = _current.get()
    handle = Span(name, attrs)
    if ctx is None:
        yield handle
        return
    span_id = new_span_id()
    parent = ctx.span_stack[-1] if ctx.span_stack else None
    ctx.span_stack.append(span_id)
    started_wall = time.time()
    started = time.perf_counter()
    outcome = "ok"
    try:
        yield handle
    except BaseException as exc:
        outcome, code = categorize(exc)
        if code:
            handle.attrs.setdefault("error_code", code)
        raise
    finally:
        ctx.span_stack.pop()
        record_span(
            ctx,
            SpanRecord(
                trace_id=ctx.trace_id,
                span_id=span_id,
                parent_id=parent,
                name=name,
                started_at=started_wall,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                outcome=handle.outcome or outcome,
                attrs=clean_attrs(handle.attrs),
                request_id=ctx.request_id,
            ),
        )


def record_span(ctx: _Context, record: SpanRecord) -> None:
    """Log, store and measure a finished span. Never raises."""
    try:
        trace_log.info(
            "span",
            extra={
                "trace_id": record.trace_id,
                "span_id": record.span_id,
                "parent_id": record.parent_id,
                "span": record.name,
                "duration_ms": record.duration_ms,
                "outcome": record.outcome,
                "attrs": record.attrs,
                "request_id": record.request_id,
            },
        )
        if ctx.store is not None:
            ctx.store.add_span(record)
        if ctx.metrics is not None:
            ctx.metrics.observe_span(record.name, record.outcome, record.duration_ms / 1000)
    except Exception:  # noqa: BLE001 - telemetry must never break practice
        if ctx.metrics is not None:
            with suppress(Exception):
                ctx.metrics.telemetry_dropped.labels("span").inc()


def current_metrics() -> Metrics | None:
    ctx = _current.get()
    return ctx.metrics if ctx else None


@contextmanager
def answer_save(kind: str) -> Iterator[Span]:
    """A traced, counted career answer save (span ``answer.save``). Set ``result`` on the yielded
    span (created, replayed, replayed_concurrent, key_conflict, key_unverifiable); a refusal or
    failure without one is counted by its category. Counted exactly once per request."""
    result = "error"
    try:
        with span("answer.save", action=kind) as handle:
            try:
                yield handle
            except BaseException as exc:
                result = str(handle.attrs.get("result") or categorize(exc)[0])
                raise
            result = str(handle.attrs.get("result") or "created")
    finally:
        metrics = current_metrics()
        if metrics is not None:
            try:
                metrics.answer_save(kind, result)
            except Exception:  # noqa: BLE001
                metrics.telemetry_dropped.labels("answer_save").inc()


@contextmanager
def round_action(action: str, fmt: str | None = None) -> Iterator[Span]:
    """A traced, counted interview round action. Set `result` on the yielded span
    (advanced, followup, completed, duplicate); a failure is counted by its category instead.
    Counted exactly once per request."""
    outcome = "error"
    try:
        with span("round.action", action=action, format=fmt) as handle:
            try:
                yield handle
            except BaseException as exc:
                outcome = categorize(exc)[0]
                raise
            outcome = str(handle.attrs.get("result") or "ok")
    finally:
        metrics = current_metrics()
        if metrics is not None:
            try:
                metrics.round_action(action, outcome)
            except Exception:  # noqa: BLE001
                metrics.telemetry_dropped.labels("round_action").inc()
