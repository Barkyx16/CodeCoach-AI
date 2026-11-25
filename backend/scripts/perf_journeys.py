"""Real learner journeys under load: a reproducible workload for docs/PERFORMANCE.md.

    # 1. a server on a fresh database (offline AI, limits raised for the benchmark only)
    DATABASE_URL=postgresql+psycopg://… AI_PROVIDER=offline AUTH_RATE_LIMIT_PER_MINUTE=1000000 \\
      PRACTICE_ANSWERS_PER_HOUR=1000000 LOG_LEVEL=WARNING uvicorn app.main:app --workers 2
    # 2. a deterministic synthetic dataset (synthetic accounts and answers only; no real content)
    python scripts/perf_journeys.py seed --base-url http://127.0.0.1:8000 --database-url postgresql+psycopg://…
    # 3. measure
    python scripts/perf_journeys.py run --base-url http://127.0.0.1:8000 --concurrency 1 8 --duration 30 --label baseline

Dataset (fixed seed): 40 learners in three careers, with 0, 60, 600 or 2,500 graded answers each
(12 / 16 / 8 / 4 learners), spread over the last 200 days. Answers are graded by the built-in
offline rubric, never a paid provider.

Workload: closed-loop clients (each sends its next request when the previous one returns),
each signed in as one learner (round-robin, so heavy and light histories are both exercised):
  30% search the question bank      GET /careers/{track}/questions?q=…
  15% career dashboard: progress    GET /careers/{track}/progress
  15% career dashboard: analytics   GET /me/careers/{track}/analytics
  10% career dashboard: plan        GET /me/plan
  15% history                       GET /me/activity?page=1&page_size=20
  15% submit an answer              POST /careers/{track}/questions/{id}/answers
After a warm-up (not counted), every request's latency and outcome is recorded. Errors are
non-2xx responses and exceptions; timeouts (10 s) are counted separately. Results go to
scripts/results/journeys-<label>.json with the machine, commit and database recorded.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESULTS = Path(__file__).resolve().parent / "results"
PASSWORD = "CorrectHorse42-perf"
SEED = 42
CAREERS = ["registered-nurse", "barista", "electrician"]
HISTORY = [0] * 12 + [60] * 16 + [600] * 8 + [2500] * 4  # answers per learner
TERMS = ["patient", "customer", "safety", "team", "conflict", "priority", "mistake", "", "time", "care"]
ANSWERS = [
    "We handled it together as a team and it was fine in the end.",
    "Last winter I noticed a problem during my shift. I checked the details myself, told my lead and "
    "fixed it within the hour; as a result nobody was affected, and I learned to escalate earlier.",
]
MIX = [  # (weight, name)
    (30, "search"),
    (15, "dashboard: progress"),
    (15, "dashboard: analytics"),
    (10, "dashboard: plan"),
    (15, "history"),
    (15, "submit answer"),
]
TIMEOUT_S = 10.0


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo), 2)


def learners() -> list[dict]:
    return [
        {"email": f"perf-{i:03d}@example.com", "career": CAREERS[i % len(CAREERS)], "answers": n}
        for i, n in enumerate(HISTORY)
    ]


# --- seed ------------------------------------------------------------------------------------


def seed(base_url: str, database_url: str) -> None:
    """Accounts through the API (real registration), answers straight into the database."""
    from sqlalchemy import select

    from app.careers.answers import graded_answer
    from app.careers.questions import questions_for
    from app.db.session import make_engine, make_session_factory
    from app.models import User

    rng = random.Random(SEED)
    sessions = make_session_factory(make_engine(database_url))
    now = datetime.now(UTC)
    with httpx.Client(base_url=base_url, timeout=30) as http:
        for person in learners():
            r = http.post(
                "/api/v1/auth/register",
                json={"email": person["email"], "password": PASSWORD, "career_track": person["career"]},
            )
            if r.status_code not in (201, 409):
                raise SystemExit(f"register failed: {r.status_code} {r.text[:200]}")
            questions = questions_for(person["career"])
            with sessions() as db:
                user = db.scalar(select(User).where(User.email == person["email"]))
                assert user is not None
                for i in range(person["answers"]):
                    row = graded_answer(user.id, questions[rng.randrange(len(questions))], ANSWERS[i % 2])
                    row.created_at = now - timedelta(minutes=rng.randrange(200 * 24 * 60))
                    db.add(row)
                db.commit()
    total = sum(p["answers"] for p in learners())
    print(f"seeded {len(HISTORY)} learners and {total} answers (seed {SEED})")


# --- run -------------------------------------------------------------------------------------


async def one_level(
    base_url: str,
    tokens: list[tuple[str, str]],
    questions: dict,
    clients: int,
    duration: float,
    warmup: float,
) -> dict:
    samples: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    timeouts: dict[str, int] = defaultdict(int)
    weights = [w for w, _ in MIX]
    names = [n for _, n in MIX]
    limits = httpx.Limits(max_connections=clients * 2, max_keepalive_connections=clients * 2)
    async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_S, limits=limits) as http:
        start = time.perf_counter()
        measuring_from = start + warmup
        stop = measuring_from + duration

        async def client(index: int) -> None:
            rng = random.Random(SEED * 1000 + index)
            token, career = tokens[index % len(tokens)]
            headers = {"Authorization": f"Bearer {token}"}
            while time.perf_counter() < stop:
                name = rng.choices(names, weights)[0]
                if name == "search":
                    req = http.get(
                        f"/api/v1/careers/{career}/questions",
                        params={"q": rng.choice(TERMS), "page_size": 20},
                        headers=headers,
                    )
                elif name == "dashboard: progress":
                    req = http.get(f"/api/v1/careers/{career}/progress", headers=headers)
                elif name == "dashboard: analytics":
                    req = http.get(f"/api/v1/me/careers/{career}/analytics", headers=headers)
                elif name == "dashboard: plan":
                    req = http.get("/api/v1/me/plan", headers=headers)
                elif name == "history":
                    req = http.get(
                        "/api/v1/me/activity", params={"page": 1, "page_size": 20}, headers=headers
                    )
                else:
                    qid = rng.choice(questions[career])
                    req = http.post(
                        f"/api/v1/careers/{career}/questions/{qid}/answers",
                        json={"answer": ANSWERS[1]},
                        headers=headers,
                    )
                began = time.perf_counter()
                counted = began >= measuring_from
                try:
                    r = await req
                    took = (time.perf_counter() - began) * 1000
                    if counted:
                        if 200 <= r.status_code < 300:
                            samples[name].append(took)
                        else:
                            errors[name][str(r.status_code)] += 1
                except httpx.TimeoutException:
                    if counted:
                        timeouts[name] += 1
                except httpx.HTTPError as exc:
                    if counted:
                        errors[name][type(exc).__name__] += 1

        await asyncio.gather(*(client(i) for i in range(clients)))
    endpoints = {}
    for name in names:
        ok = samples[name]
        bad = sum(errors[name].values()) + timeouts[name]
        endpoints[name] = {
            "requests": len(ok) + bad,
            "ok": len(ok),
            "errors": dict(errors[name]),
            "timeouts": timeouts[name],
            "success_rate": round(len(ok) / (len(ok) + bad), 4) if ok or bad else None,
            "p50_ms": pct(ok, 0.50),
            "p95_ms": pct(ok, 0.95),
            "p99_ms": pct(ok, 0.99),
        }
    everything = [v for vs in samples.values() for v in vs]
    failed = sum(sum(e.values()) for e in errors.values()) + sum(timeouts.values())
    return {
        "clients": clients,
        "duration_s": duration,
        "warmup_s": warmup,
        "requests": len(everything) + failed,
        "ok": len(everything),
        "failed": failed,
        "success_rate": round(len(everything) / (len(everything) + failed), 4)
        if everything or failed
        else None,
        "throughput_rps": round(len(everything) / duration, 1),
        "p50_ms": pct(everything, 0.50),
        "p95_ms": pct(everything, 0.95),
        "p99_ms": pct(everything, 0.99),
        "endpoints": endpoints,
    }


def environment(base_url: str) -> dict:
    def git(*args: str) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=Path(__file__).parent, text=True).strip()
        except Exception:  # noqa: BLE001
            return "unknown"

    return {
        "commit": git("rev-parse", "--short", "HEAD"),
        "uncommitted_changes": bool(git("status", "--porcelain", "--untracked-files=no")),
        "python": platform.python_version(),
        "cpus": os.cpu_count(),
        "machine": platform.platform(),
        "base_url": base_url,
        "database": os.environ.get("PERF_DATABASE_LABEL", "see notes"),
        "dataset": {
            "learners": len(HISTORY),
            "answers": sum(HISTORY),
            "history_sizes": sorted(set(HISTORY)),
            "seed": SEED,
        },
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def run(base_url: str, levels: list[int], duration: float, warmup: float, label: str) -> None:
    from app.careers.questions import questions_for

    questions = {c: [q.id for q in questions_for(c)] for c in CAREERS}
    tokens = []
    with httpx.Client(base_url=base_url, timeout=30) as http:
        for person in learners():
            r = http.post("/api/v1/auth/login", json={"email": person["email"], "password": PASSWORD})
            r.raise_for_status()
            tokens.append((r.json()["access_token"], person["career"]))
    # Heaviest histories first, so even one client exercises a 2,500-answer learner.
    order = sorted(range(len(tokens)), key=lambda i: -HISTORY[i])
    tokens = [tokens[i] for i in order]
    report = {"environment": environment(base_url), "mix": MIX, "levels": []}
    for clients in levels:
        level = asyncio.run(one_level(base_url, tokens, questions, clients, duration, warmup))
        report["levels"].append(level)
        print(
            f"{clients:>3} clients: {level['requests']} requests, {level['throughput_rps']} req/s, "
            f"p50 {level['p50_ms']} ms, p95 {level['p95_ms']} ms, p99 {level['p99_ms']} ms, "
            f"success {level['success_rate']}"
        )
        for name, e in level["endpoints"].items():
            print(
                f"      {name:22s} n={e['ok']:<5} p50 {e['p50_ms']:>8} p95 {e['p95_ms']:>8} p99 {e['p99_ms']:>8}  errors {e['errors'] or 0} timeouts {e['timeouts']}"
            )
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"journeys-{label}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--base-url", default="http://127.0.0.1:8000")
    s.add_argument("--database-url", required=True)
    r = sub.add_parser("run")
    r.add_argument("--base-url", default="http://127.0.0.1:8000")
    r.add_argument("--concurrency", type=int, nargs="+", default=[1, 8])
    r.add_argument("--duration", type=float, default=30)
    r.add_argument("--warmup", type=float, default=5)
    r.add_argument("--label", default="run")
    args = parser.parse_args()
    if args.cmd == "seed":
        seed(args.base_url, args.database_url)
    else:
        run(args.base_url, args.concurrency, args.duration, args.warmup, args.label)


if __name__ == "__main__":
    main()
