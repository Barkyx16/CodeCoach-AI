"""Prometheus metrics: request counts and latency histograms per route template.

Route *templates* (e.g. /api/v1/problems/{slug}) are used as labels, never raw paths, so a
client can't explode label cardinality by requesting random URLs.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST


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

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        self.requests.labels(method, route, str(status)).inc()
        self.latency.labels(method, route).observe(seconds)

    def render(self) -> bytes:
        return generate_latest(self.registry)
