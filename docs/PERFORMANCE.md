# CodeCoach AI — Performance

Measured numbers, with the setup that produced them. Nothing here is projected or estimated.
These describe **one 4-vCPU development VM**; production hardware will differ, so re-measure
before quoting numbers for a deployment.

## Setup
| | |
|---|---|
| Hardware | 1 VM, 4 vCPUs (Intel Xeon @ 2.10 GHz), 16 GB RAM |
| API | `uvicorn app.main:app --workers 4`, Python 3.13, FastAPI, SQLAlchemy 2 |
| Database | PostgreSQL 16 on the same VM |
| Judge | `python -m app.worker` process(es) → runner (`MAX_CONCURRENCY=2`) → Docker + gVisor (`runsc`), JDK 21 |
| Load generator | `backend/scripts/loadtest.py`, **on the same VM** (it competes for the same CPUs, so this is a pessimistic setup) |
| Date | 2026-11-01 |

## API latency and throughput
Closed-loop clients over the endpoint mix below, 20 s per level, judge queue empty.

| Concurrent clients | Requests | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | Errors |
|---|---|---|---|---|---|---|
| 1 | 2,012 | 100 | 9 | 18 | 21 | 0 |
| 10 | 5,091 | 254 | 32 | 86 | 104 | 0 |
| 50 | 4,104 | 204 | 167 | 707 | 1062 | 1 |

**Per endpoint (ms):**

| Endpoint | p50 @ 1 client | p95 @ 1 client | p50 @ 10 clients | p95 @ 10 clients |
|---|---|---|---|---|
| `GET /problems` | 5.4 | 6.8 | 21.1 | 48.4 |
| `GET /problems/{slug}` | 9.5 | 12.1 | 33.0 | 76.2 |
| `GET /me/progress` | 15.9 | 21.4 | 42.3 | 101.6 |
| `GET /me/recommendations` | 13.2 | 17.9 | 41.7 | 88.3 |
| `POST /ai/review (offline)` | 12.8 | 15.9 | 46.6 | 97.1 |
| `GET /me/submissions` | 8.7 | 11.1 | 31.4 | 74.4 |
| `GET /health/ready` | 3.7 | 5.3 | 16.2 | 40.3 |

**Reading it:**
- With one client, every endpoint answers in **under ~22 ms at p95**. That's the latency floor:
  per-request work, without queuing.
- At **10 clients** the box serves **~254 req/s at an overall p95 of 86 ms** with no errors.
  The slowest endpoints are the per-user aggregates (`/me/progress` p95 102 ms, offline review p95 97 ms).
- At **50 clients** the VM is **saturated** (4 API processes, PostgreSQL *and* the load
  generator on 4 vCPUs): throughput stops growing and the tail climbs to ~0.7 s p95 / ~1 s p99.
  Repeated runs at this level varied widely (two extra runs gave 298 and 243 req/s, p50 21 and
  132 ms, p95 ~600 ms each). That's typical of an overloaded machine, so treat the 50-client row
  as a **capacity ceiling for this VM**, not a latency target.
- One request failed in the recorded 50-client run (`POST /ai/review`, about 1 in 4,100). The
  server logged no error, and it didn't reproduce in two further runs (~11,000 requests). The
  load tester now records failure reasons (status code or exception type) to diagnose it if it recurs.

## Judging throughput (gVisor sandbox)
20 different users each submit a reference solution **at the same moment** (a burst), cycling
through all 12 problems the library had at the time (it now has 22). Time to verdict = from POST until the final verdict is visible.

| Judge workers | Throughput | Wall time for 20 | Fastest verdict | p50 time to verdict | p95 time to verdict | Verdicts |
|---|---|---|---|---|---|---|
| 1 | **15.5 / min** | 77.6 s | 4.3 s | 40.8 s | 73.8 s | {'PASSED': 20} |
| 2 | **29.3 / min** | 40.9 s | 4.2 s | 22.5 s | 40.9 s | {'PASSED': 20} |

- **One submission takes ~4 s end to end** (fastest verdict: no queue). Most of that is
  starting a fresh gVisor container plus JVM startup for `javac` and `java`, which is the price
  of a clean sandbox per run.
- A burst's p50/p95 is dominated by **queue wait**: with 20 submissions arriving at once, the
  last one waits behind 19 others.
- **A second worker gave 1.9× the throughput** (15.5 → 29.3/min) and halved the
  median wait. The queue (`FOR UPDATE SKIP LOCKED`) scaled with **no double-judging**: every submission
  judged in that window (the 40 benchmark submissions, plus 2 from the end of a discarded warm-up
  run) had `attempts = 1` and exactly one `solved` event, and the second worker took 10 of the 20.

## Where to go next (not done yet)
- **Judge throughput:** more workers and runner slots (it scales roughly linearly until the
  CPUs are full), or a warm pool of pre-started sandboxes to cut the ~4 s startup.
- **API at higher load:** measure on separate machines for the API, the database and the load
  generator, and profile the per-request overhead (the 1-client floor of 5–16 ms leaves room).
- **Peak memory per submission** isn't measured (the API reports `memory_kb: null`).

## How these were measured

- **Tool:** `backend/scripts/loadtest.py` (async `httpx`, closed-loop clients: each client sends
  its next request as soon as the previous one returns). Raw JSON is in `backend/scripts/results/`.
- **API mix:** 30% problem list, 25% problem detail, 15% progress dashboard, 10% recommendations,
  10% AI review (offline coach), 5% submission history, 5% readiness probe. Every client is a
  separate guest user with some activity, so per-user queries do real work.
- **Judge:** N reference solutions (one per user, cycling through all 12 problems) submitted at
  once. Time to verdict = POST → poll until final status (queue wait + compile + run in gVisor).
- **Hygiene:** each benchmark starts with an **empty judge queue** and nothing else running. A
  first attempt was discarded because the API benchmark had queued placeholder submissions, so
  the worker was compiling Java in gVisor on the same CPUs during the measurement (the script no
  longer creates submissions in API mode).

## Reproduce
```bash
# API (in one terminal)
cd backend && DATABASE_URL=postgresql+psycopg://… AUTH_RATE_LIMIT_PER_MINUTE=100000 \
  uvicorn app.main:app --workers 4
# Judge (needs gVisor): the runner, then one or more workers
cd runner && RUNNER_TOKEN=… uvicorn app.main:app_factory --factory --port 8100
cd backend && EXECUTION_ENABLED=true RUNNER_TOKEN=… python -m app.worker
# Measure
python scripts/loadtest.py api --concurrency 1 10 50 --duration 20
python scripts/loadtest.py judge --submissions 20
```
