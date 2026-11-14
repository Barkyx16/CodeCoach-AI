"""Pre-launch load tests for the production-hardening batch (docs/PERFORMANCE.md "Pre-launch").

Against a running API (synthetic accounts only; never point this at a real deployment):

    python scripts/loadtest_hardening.py catalog   --base-url http://127.0.0.1:8000 --clients 16 --duration 20
    python scripts/loadtest_hardening.py logins    --base-url ... --clients 8 --duration 20
    python scripts/loadtest_hardening.py abuse     --base-url ... --duration 20
    python scripts/loadtest_hardening.py slow-ai   --base-url ... --ai-users 40 --readers 8 --duration 30

`catalog`  anonymous public reads (careers, problem list, question lists): throughput and latency.
           Run once with RESPONSE_CACHE_TTL_SECONDS=0 and once with the default to see the cache.
`logins`   real sign-ins (Argon2id), distinct accounts: what one process can verify per second.
           Needs AUTH_RATE_LIMIT_PER_MINUTE raised on the server, or every client shares a bucket.
`abuse`    one address hammers sign-in with wrong passwords while ordinary readers continue:
           the limits must answer 429 (never 5xx) and readers must not notice.
`slow-ai`  `--ai-users` accounts ask for AI hints at once against a provider that takes ~10 s
           (scripts/serve_slow_ai.py) while `--readers` clients read normally. Shows whether a slow
           provider can starve everyone else of database connections.

Results go to scripts/results/hardening-<scenario>[-label].json with the settings used.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

RESULTS = Path(__file__).resolve().parent / "results"
PASSWORD = "CorrectHorse42"


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo), 1)


class Recorder:
    def __init__(self) -> None:
        self.latency: dict[str, list[float]] = defaultdict(list)
        self.status: dict[str, Counter] = defaultdict(Counter)
        self.extra: dict[str, Counter] = defaultdict(Counter)

    async def call(
        self, client: httpx.AsyncClient, name: str, method: str, url: str, **kw
    ) -> httpx.Response | None:
        start = time.perf_counter()
        try:
            r = await client.request(method, url, **kw)
        except httpx.HTTPError as exc:
            self.status[name][type(exc).__name__] += 1
            return None
        self.latency[name].append((time.perf_counter() - start) * 1000)
        self.status[name][str(r.status_code)] += 1
        return r

    def summary(self, duration: float) -> dict:
        out = {}
        for name in sorted(set(self.latency) | set(self.status)):
            lat = self.latency[name]
            total = sum(self.status[name].values())
            out[name] = {
                "requests": total,
                "per_second": round(total / duration, 1),
                "status": dict(self.status[name]),
                "p50_ms": pct(lat, 0.5),
                "p95_ms": pct(lat, 0.95),
                "p99_ms": pct(lat, 0.99),
                "max_ms": round(max(lat), 1) if lat else None,
                **({"outcomes": dict(self.extra[name])} if self.extra[name] else {}),
            }
        return out


async def register(client: httpx.AsyncClient, email: str, track: str = "registered-nurse") -> str:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Load", "career_track": track},
    )
    if r.status_code == 409:
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


async def until(deadline: float, fn) -> None:
    while time.perf_counter() < deadline:
        await fn()


async def catalog(args, rec: Recorder) -> dict:
    tracks = ["registered-nurse", "customer-service-representative", "software-engineer"]
    paths = [
        ("GET /careers", "/api/v1/careers"),
        ("GET /problems", "/api/v1/problems?page_size=20"),
        ("GET /careers/{t}/questions", None),
        ("GET /problems/counts", "/api/v1/problems/counts"),
    ]
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        deadline = time.perf_counter() + args.duration

        async def one() -> None:
            name, url = random.choice(paths)
            url = url or f"/api/v1/careers/{random.choice(tracks)}/questions?page_size=20"
            r = await rec.call(client, name, "GET", url)
            if r is not None:
                rec.extra[name][r.headers.get("x-cache", "none")] += 1

        await asyncio.gather(*(until(deadline, one) for _ in range(args.clients)))
    return {}


async def logins(args, rec: Recorder) -> dict:
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60) as client:
        emails = [f"login-{i}-{args.tag}@example.com" for i in range(args.clients)]
        for e in emails:
            await register(client, e)
        deadline = time.perf_counter() + args.duration

        def worker(email: str):
            async def one() -> None:
                await rec.call(
                    client,
                    "POST /auth/login",
                    "POST",
                    "/api/v1/auth/login",
                    json={"email": email, "password": PASSWORD},
                )

            return one

        await asyncio.gather(*(until(deadline, worker(e)) for e in emails))
    return {}


async def abuse(args, rec: Recorder) -> dict:
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60) as client:
        token = await register(client, f"reader-{args.tag}@example.com")
        await register(client, f"victim-{args.tag}@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        deadline = time.perf_counter() + args.duration

        async def attacker() -> None:
            await rec.call(
                client,
                "POST /auth/login (wrong password, one address)",
                "POST",
                "/api/v1/auth/login",
                json={"email": f"victim-{args.tag}@example.com", "password": "WrongHorse99"},
            )

        async def reader() -> None:
            await rec.call(client, "GET /me/progress (reader)", "GET", "/api/v1/me/progress", headers=headers)

        await asyncio.gather(
            *(until(deadline, attacker) for _ in range(args.clients)),
            *(until(deadline, reader) for _ in range(2)),
        )
    return {}


async def slow_ai(args, rec: Recorder) -> dict:
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=120, limits=httpx.Limits(max_connections=500)
    ) as client:
        ai_tokens = [await register(client, f"ai-{i}-{args.tag}@example.com") for i in range(args.ai_users)]
        reader = await register(client, f"reader-{args.tag}@example.com")
        deadline = time.perf_counter() + args.duration

        def ai_user(token: str):
            level = {"n": 0}

            async def one() -> None:
                level["n"] = level["n"] % 3 + 1
                r = await rec.call(
                    client,
                    "POST /ai/hint (slow provider)",
                    "POST",
                    "/api/v1/ai/hint",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"problem_slug": "two-sum", "level": level["n"], "source_code": ""},
                )
                if r is not None and r.status_code == 200:
                    rec.extra["POST /ai/hint (slow provider)"][r.json().get("provider", "?")] += 1
                elif r is not None and r.status_code == 409:
                    level["n"] = 0  # hint ladder: start again

            return one

        rh = {"Authorization": f"Bearer {reader}"}

        async def read() -> None:
            name, url = random.choice(
                [
                    ("GET /me/progress (reader)", "/api/v1/me/progress"),
                    ("GET /me/notes (reader)", "/api/v1/me/notes"),
                ]
            )
            await rec.call(client, name, "GET", url, headers=rh)

        await asyncio.gather(
            *(until(deadline, ai_user(t)) for t in ai_tokens),
            *(until(deadline, read) for _ in range(args.readers)),
        )
    return {}


SCENARIOS = {"catalog": catalog, "logins": logins, "abuse": abuse, "slow-ai": slow_ai}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--clients", type=int, default=8)
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--ai-users", type=int, default=40)
    parser.add_argument("--readers", type=int, default=8)
    parser.add_argument("--label", default="")
    parser.add_argument("--note", default="", help="server settings for the record (workers, limits, cache)")
    args = parser.parse_args()
    args.tag = f"{int(time.time())}{random.randint(100, 999)}"
    rec = Recorder()
    started = time.perf_counter()
    asyncio.run(SCENARIOS[args.scenario](args, rec))
    elapsed = time.perf_counter() - started
    result = {
        "scenario": args.scenario,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_s": args.duration,
        "args": {k: v for k, v in vars(args).items() if k not in ("tag",)},
        "machine": {
            "cpus": os.cpu_count(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "results": rec.summary(args.duration),
        "wall_s": round(elapsed, 1),
    }
    RESULTS.mkdir(exist_ok=True)
    name = f"hardening-{args.scenario}{'-' + args.label if args.label else ''}.json"
    (RESULTS / name).write_text(json.dumps(result, indent=2) + "\n")
    for k, v in result["results"].items():
        print(
            f"{k:50s} {v['per_second']:7.1f}/s  p50 {v['p50_ms']:7.1f}  p95 {v['p95_ms']:7.1f}  p99 {v['p99_ms']:7.1f} ms  {v['status']}  {v.get('outcomes', '')}"
        )
    print(f"wrote {RESULTS / name}")


if __name__ == "__main__":
    main()
