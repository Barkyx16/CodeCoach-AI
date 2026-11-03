"""Prometheus metrics: request counts and latency histograms per route template.

Route *templates* (e.g. /api/v1/problems/{slug}) are used as labels, never raw paths, so a
client can't explode label cardinality by requesting random URLs.
"""

from __future__ import annotations

from collections.abc import Callable

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

# Fixed label values. Anything else a client sends is folded into "other", so labels stay bounded.
ROUND_ACTIONS = ("answer", "skip", "reply", "skip_followup")
UI_ACTIONS = ("answer", "skip", "reply", "skip_followup")
UI_OUTCOMES = ("rendered", "rejected", "server_error", "network_error", "not_rendered", "ignored")


class Metrics:
    content_type = CONTENT_TYPE_LATEST

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "codecoach_http_requests_total",
            "HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.latency = Histogram(
            "codecoach_http_request_duration_seconds",
            "HTTP request latency",
            ["method", "route"],
            registry=self.registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        )
        self.ai_requests = Counter(
            "codecoach_ai_requests_total", "AI coach requests", ["action", "provider"], registry=self.registry
        )
        self.ai_tokens = Counter(
            "codecoach_ai_tokens_total", "Model tokens used", ["direction"], registry=self.registry
        )
        # Server-measured: each traced step (span names are a fixed set chosen in code).
        self.span_duration = Histogram(
            "codecoach_span_duration_seconds",
            "Duration of a traced step on the server",
            ["span", "outcome"],
            registry=self.registry,
            buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
        )
        # One per round action request, counted once: a repeated submit counts as "duplicate".
        self.round_actions = Counter(
            "codecoach_round_actions_total",
            "Interview round actions by outcome (advanced, followup, completed, duplicate, rejected, error)",
            ["action", "outcome"],
            registry=self.registry,
        )
        # Client-measured: from the click to the next state on screen, as the browser reports it.
        self.ui_actions = Counter(
            "codecoach_ui_actions_total",
            "Round actions as the browser saw them",
            ["action", "outcome"],
            registry=self.registry,
        )
        self.ui_latency = Histogram(
            "codecoach_ui_action_seconds",
            "Browser-measured time from a round action to its result on screen",
            ["action", "outcome"],
            registry=self.registry,
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
        )
        self.telemetry_dropped = Counter(
            "codecoach_telemetry_dropped_total",
            "Telemetry that wasn't recorded (by kind); the request itself was unaffected",
            ["kind"],
            registry=self.registry,
        )
        # Judge queue, read from the database at scrape time, so it is right wherever the worker runs.
        self.judge_queued = Gauge(
            "codecoach_judge_queued_jobs", "Code submissions waiting for the judge", registry=self.registry
        )
        self.judge_oldest = Gauge(
            "codecoach_judge_oldest_queued_seconds",
            "Age of the oldest code submission waiting for the judge (0 when none)",
            registry=self.registry,
        )
        self.queue_probe: Callable[[], tuple[int, float]] | None = None

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        self.requests.labels(method, route, str(status)).inc()
        self.latency.labels(method, route).observe(seconds)

    def observe_span(self, name: str, outcome: str, seconds: float) -> None:
        self.span_duration.labels(name, outcome).observe(seconds)

    def round_action(self, action: str, outcome: str) -> None:
        self.round_actions.labels(action if action in ROUND_ACTIONS else "other", outcome).inc()

    def ui_action(self, action: str, outcome: str, seconds: float) -> None:
        action = action if action in UI_ACTIONS else "other"
        outcome = outcome if outcome in UI_OUTCOMES else "other"
        self.ui_actions.labels(action, outcome).inc()
        self.ui_latency.labels(action, outcome).observe(seconds)

    def render(self) -> bytes:
        if self.queue_probe is not None:
            try:
                queued, oldest = self.queue_probe()
                self.judge_queued.set(queued)
                self.judge_oldest.set(oldest)
            except Exception:  # noqa: BLE001 - a scrape must not fail because the database is busy
                self.telemetry_dropped.labels("queue_probe").inc()
        return generate_latest(self.registry)
