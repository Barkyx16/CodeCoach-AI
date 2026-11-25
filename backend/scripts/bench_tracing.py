"""Measure what tracing costs (docs/OBSERVABILITY.md, "Measured overhead").

    python scripts/bench_tracing.py

1. One span, with and without the in-memory store and metrics, with the INFO log line filtered
   out and written (to /dev/null).
2. A full round answer through the real app (TestClient, SQLite), trace store on and off.
Numbers depend on the machine; compare runs on the same one.
"""

from __future__ import annotations

import logging
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import tracing  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.metrics import Metrics  # noqa: E402
from app.observability import JsonFormatter  # noqa: E402

N = 20_000


def per_span_us(store: tracing.TraceStore | None, metrics: Metrics | None, write_lines: bool) -> float:
    log = logging.getLogger("codecoach")
    handler = logging.FileHandler(os.devnull)
    handler.setFormatter(JsonFormatter())
    log.handlers[:] = [handler]
    log.propagate = False
    log.setLevel(logging.INFO if write_lines else logging.WARNING)
    with tracing.start_trace(store=store, metrics=metrics, request_id="bench-request-0001"):
        started = time.perf_counter()
        for _ in range(N):
            with tracing.span("evaluate", evaluator="rubric"):
                pass
        return (time.perf_counter() - started) / N * 1e6


def answer_ms(trace_store: int, rounds: int = 60) -> tuple[float, float]:
    with tempfile.TemporaryDirectory() as d:
        settings = Settings(
            environment="test",
            database_url=f"sqlite:///{d}/bench.db",
            secret_key="b" * 48,
            ai_provider="offline",
            auth_rate_limit_per_minute=100_000,
            practice_answers_per_hour=100_000,
            trace_store_max_traces=trace_store,
            _env_file=None,
        )
        with TestClient(create_app(settings)) as c:
            logging.getLogger("codecoach").setLevel(logging.WARNING)
            times = []
            for i in range(rounds):
                token = c.post(
                    "/api/v1/auth/register",
                    json={
                        "email": f"b{i}@example.com",
                        "password": "CorrectHorse42",
                        "career_track": "registered-nurse",
                    },
                ).json()["access_token"]
                h = {"Authorization": f"Bearer {token}"}
                iv = c.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
                started = time.perf_counter()
                r = c.post(
                    f"/api/v1/interviews/{iv['id']}/answers",
                    headers={**h, "traceparent": f"00-{i + 1:032x}-{i + 1:016x}-01"},
                    json={
                        "question_index": 0,
                        "answer": "I checked his vital signs and called the doctor.",
                        "source": "typed",
                    },
                )
                times.append((time.perf_counter() - started) * 1000)
                assert r.status_code == 200, r.text
            measured = times[10:]  # after warm-up
            return statistics.median(measured), statistics.quantiles(measured, n=20)[-1]


def main() -> None:
    print(f"Python {platform.python_version()}, {os.cpu_count()} CPUs")
    print(
        f"span, store + metrics, line filtered: {per_span_us(tracing.TraceStore(), Metrics(), False):.1f} us"
    )
    print(
        f"span, store + metrics, line written:  {per_span_us(tracing.TraceStore(), Metrics(), True):.1f} us"
    )
    print(f"span, no store or metrics, filtered:  {per_span_us(None, None, False):.1f} us")
    for label, store in (("trace store on ", 500), ("trace store off", 0)):
        median, p95 = answer_ms(store)
        print(f"answer request, {label}: median {median:.2f} ms, p95 {p95:.2f} ms (50 answers)")


if __name__ == "__main__":
    main()
