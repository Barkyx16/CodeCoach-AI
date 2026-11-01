"""Load test: measured latency and throughput for docs/PERFORMANCE.md.

    python scripts/loadtest.py api   --base-url http://localhost:8000 --concurrency 10 50 --duration 20
    python scripts/loadtest.py judge --base-url http://localhost:8000 --submissions 40

`api`   Closed-loop clients (each sends its next request as soon as the previous one returns)
        over a realistic mix of read and write endpoints. Reports p50/p95/p99 latency, throughput
        and error rate per endpoint and concurrency level.
`judge` Submits reference solutions as many separate users at once and measures, per submission,
        the time from POST to final verdict (queue wait + sandbox), plus overall throughput.

Results are written as JSON next to this script (results/). Numbers depend entirely on the
hardware and configuration, which are recorded alongside them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

RESULTS = Path(__file__).resolve().parent / "results"
SEED = Path(__file__).resolve().parents[1] / "app" / "seed"

MIX = [  # (weight, name, method, path, body)
    (30, "GET /problems", "GET", "/api/v1/problems?page_size=20", None),
    (25, "GET /problems/{slug}", "GET", "/api/v1/problems/{slug}", None),
    (15, "GET /me/progress", "GET", "/api/v1/me/progress", None),
    (10, "GET /me/recommendations", "GET", "/api/v1/me/recommendations", None),
    (10, "POST /ai/review (offline)", "POST", "/api/v1/ai/review", "review"),
    (5, "GET /me/submissions", "GET", "/api/v1/me/submissions", None),
    (5, "GET /health/ready", "GET", "/health/ready", None),
]
SLUGS = [json.loads(p.read_text())["slug"] for p in sorted((SEED / "problems").glob("*.json"))]


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def summarize(latencies_ms: list[float], errors: int, duration_s: float) -> dict:
    n = len(latencies_ms)
    return {
        "requests": n + errors,
        "errors": errors,
        "error_rate": round(errors / (n + errors), 4) if n + errors else 0,
        "throughput_rps": round((n + errors) / duration_s, 1),
        "p50_ms": round(pct(latencies_ms, 0.50), 1),
        "p95_ms": round(pct(latencies_ms, 0.95), 1),
        "p99_ms": round(pct(latencies_ms, 0.99), 1),
        "mean_ms": round(statistics.fmean(latencies_ms), 1) if n else None,
    }


async def guest(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/guest")
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def api_level(base_url: str, concurrency: int, duration_s: float, review_code: str) -> dict:
    weights = [w for w, *_ in MIX]
    lat: dict[str, list[float]] = defaultdict(list)
    err: dict[str, int] = defaultdict(int)
    reasons: dict[str, int] = defaultdict(int)  # why requests failed: HTTP status or exception type
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency * 2)
    async with httpx.AsyncClient(base_url=base_url, timeout=30, limits=limits) as client:
        headers = await asyncio.gather(*(guest(client) for _ in range(concurrency)))
        # Some activity per user so progress/recommendations have real work to do. Deliberately
        # NOT a submission: that would queue judge jobs and contaminate the judge benchmark.
        for h in headers:
            await client.post(
                "/api/v1/ai/review",
                headers=h,
                json={"problem_slug": random.choice(SLUGS), "source_code": review_code},
            )
        deadline = time.perf_counter() + duration_s

        async def worker(h: dict) -> None:
            while time.perf_counter() < deadline:
                _, name, method, path, body = random.choices(MIX, weights)[0]
                path = path.replace("{slug}", random.choice(SLUGS))
                payload = (
                    {"problem_slug": "two-sum", "source_code": review_code} if body == "review" else None
                )
                t0 = time.perf_counter()
                try:
                    r = await client.request(method, path, headers=h, json=payload)
                    ok = r.status_code < 400
                    if not ok:
                        reasons[f"{name}: HTTP {r.status_code}"] += 1
                except httpx.HTTPError as exc:
                    ok = False
                    reasons[f"{name}: {type(exc).__name__}"] += 1
                ms = (time.perf_counter() - t0) * 1000
                if ok:
                    lat[name].append(ms)
                else:
                    err[name] += 1

        start = time.perf_counter()
        await asyncio.gather(*(worker(h) for h in headers))
        elapsed = time.perf_counter() - start
    every = [v for vs in lat.values() for v in vs]
    return {
        "concurrency": concurrency,
        "duration_s": round(elapsed, 1),
        "overall": summarize(every, sum(err.values()), elapsed),
        "endpoints": {name: summarize(lat[name], err[name], elapsed) for _, name, *_ in MIX},
        "error_reasons": dict(reasons),
    }


async def judge_run(base_url: str, submissions: int) -> dict:
    refs = {slug: (SEED / "reference" / f"{slug}.java").read_text() for slug in SLUGS}
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        users = await asyncio.gather(*(guest(client) for _ in range(submissions)))
        jobs = [(users[i], SLUGS[i % len(SLUGS)]) for i in range(submissions)]

        async def one(h: dict, slug: str) -> tuple[float, str]:
            t0 = time.perf_counter()
            r = await client.post(
                "/api/v1/submissions", headers=h, json={"problem_slug": slug, "source_code": refs[slug]}
            )
            r.raise_for_status()
            sid = r.json()["id"]
            while True:
                d = (await client.get(f"/api/v1/submissions/{sid}", headers=h)).json()
                if d["is_terminal"]:
                    return (time.perf_counter() - t0) * 1000, d["status"]
                await asyncio.sleep(0.25)

        start = time.perf_counter()
        results = await asyncio.gather(*(one(h, s) for h, s in jobs))
        elapsed = time.perf_counter() - start
    times = [t for t, _ in results]
    statuses = defaultdict(int)
    for _, st in results:
        statuses[st] += 1
    return {
        "submissions": submissions,
        "wall_time_s": round(elapsed, 1),
        "throughput_per_min": round(submissions / elapsed * 60, 1),
        "verdicts": dict(statuses),
        "time_to_verdict_ms": {
            "p50": round(pct(times, 0.5)),
            "p95": round(pct(times, 0.95)),
            "min": round(min(times)),
            "max": round(max(times)),
        },
    }


def environment(extra: dict) -> dict:
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cpus": os.cpu_count(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        **extra,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["api", "judge"])
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--concurrency", type=int, nargs="+", default=[10, 50])
    ap.add_argument("--duration", type=float, default=20)
    ap.add_argument("--submissions", type=int, default=24)
    ap.add_argument("--note", default="", help="free-text description of the server setup")
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    if args.mode == "api":
        code = (SEED / "reference" / "two-sum.java").read_text()
        levels = [asyncio.run(api_level(args.base_url, c, args.duration, code)) for c in args.concurrency]
        out = {"environment": environment({"note": args.note}), "levels": levels}
    else:
        out = {
            "environment": environment({"note": args.note}),
            "judge": asyncio.run(judge_run(args.base_url, args.submissions)),
        }
    path = RESULTS / f"{args.mode}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
