# CodeCoach AI — Performance

Measured numbers, with the setup that produced them. Nothing here is projected or estimated.
These describe **one 4-vCPU development VM**; production hardware will differ, so re-measure
before quoting numbers for a deployment.

## Pre-launch load tests (2026-11-06)

The **shipped configuration** (the Docker image runs one uvicorn process; nothing measured it
before), on PostgreSQL 16 with the new migrations applied and row-level security enforced. Same
4-vCPU VM, load generator on the same machine (so absolute numbers are pessimistic; the
comparisons are what matter). Tool: `backend/scripts/loadtest_hardening.py`; raw results:
`backend/scripts/results/hardening-*.json`. Synthetic accounts in a disposable database
(created and dropped).

| Scenario | Setting | Result |
|---|---|---|
| Public catalogue, 16 anonymous clients, 20 s | response cache **off** (`RESPONSE_CACHE_TTL_SECONDS=0`) | **41 req/s** in total; p50 99–458 ms, p95 341–884 ms, p99 up to 5.0 s. One process is CPU-bound building these responses |
| Same | cache **on** (default, 60 s) | **565 req/s** (13.8×); p50 12 ms, p95 68–71 ms, p99 ≤ 126 ms; 27 misses in 11,309 requests |
| Sign-ins, 8 accounts, 20 s | per-IP limit raised to measure | **15.9 logins/s**, p50 503 ms, p95 619 ms. Argon2id (64 MiB, 4 lanes) is deliberately costly: this is about what 4 cores verify; more processes on the same cores won't add much |
| Sign-in flood: 8 clients, one address, wrong passwords, 20 s, plus 2 readers | default limits | 1,337 attempts: **8 reached a password check, 1,329 got 429**, 0 errors. Readers: 335 requests, all 200, p95 158 ms (the flood still costs CPU: see below) |
| Slow AI provider (10 s per call), 40 users asking for hints non-stop, plus 8 readers, 30 s | **no cap** | **Breaking point.** Every database connection was held by a waiting AI call: readers got 16 responses in 30 s, **10 of them 503** `server_busy`, p50 15 s; 34 AI requests 503; the pool ran out 44 times |
| Same | **`AI_MAX_CONCURRENT_CALLS=8`** (default) | **0 errors.** Readers: 401 requests, all 200 (p50 ~550 ms, p95 ≤ 1.15 s: the process's CPU was saturated by 55 offline answers/s from clients with no pause). AI: 1,646 answered, 24 by the slow provider (8 at a time), 1,622 at once by the offline coach; the pool never ran out |

What this means for launch:
- **Cache the catalogue** (done): the public pages a new visitor loads are 14× cheaper.
- **A slow or failing AI provider can't take the site down** any more: at most 8 calls per
  process wait on it; the rest get the offline coach immediately, labelled as a fallback.
- **Sign-in is CPU-bound by design.** Budget about 16 sign-ins/s per 4 cores. A launch-day spike
  above that queues (it doesn't fail); add CPU or instances.
- **Rate limits work, but cost CPU.** The flood above still took 67 attempts/s of one process's
  time; readers stayed correct but slower. For volumetric attacks, add an edge limit (proxy/CDN).

### Sizing

- **Processes:** `WEB_CONCURRENCY` (uvicorn reads it; the image defaults to 1). One per core is a
  reasonable start for this mostly-CPU-bound API.
- **Connections:** each process holds up to `DB_POOL_SIZE + DB_MAX_OVERFLOW` (5 + 10). Keep
  `processes × 15 + workers × 4 + headroom` under PostgreSQL's `max_connections` (100 by
  default): e.g. 4 processes = 60 + a worker = 64. Raise `max_connections` or lower the pool
  before adding processes.
- **AI:** `AI_MAX_CONCURRENT_CALLS` (8) per process stays below the pool (15), so AI calls can
  never hold every connection.
- **Edge:** set `FORWARDED_ALLOW_IPS` to the proxy's address, or every client shares the
  proxy's rate-limit bucket.

### Reproduce
```bash
cd backend
# A disposable database, migrated (createdb …; DATABASE_URL=… alembic upgrade head; python -m app.cli seed)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers          # the shipped config
python scripts/loadtest_hardening.py catalog --clients 16 --duration 20     # RESPONSE_CACHE_TTL_SECONDS=0 for "off"
AUTH_RATE_LIMIT_PER_MINUTE=1000000 uvicorn …;  python scripts/loadtest_hardening.py logins --clients 8
uvicorn …;  python scripts/loadtest_hardening.py abuse --clients 8          # default limits
PYTHONPATH=. AUTH_RATE_LIMIT_PER_MINUTE=1000000 AI_DAILY_REQUEST_LIMIT=100000 \
  python scripts/serve_slow_ai.py --delay 10 --cap 1000                     # then --cap 8
python scripts/loadtest_hardening.py slow-ai --ai-users 40 --readers 8 --duration 30
```
No provider is called: `serve_slow_ai.py` uses a fake that sleeps, then answers like the offline
coach, and refuses to run with `ENVIRONMENT=production`.

## Real journeys: search, dashboard, history, answering (2026-11-03)

What learners do most, measured before and after optimizing, with the same workload:
`backend/scripts/perf_journeys.py` (raw results: `backend/scripts/results/journeys-*.json`).

| | |
|---|---|
| Machine | 1 container, 4 vCPUs, Linux 6.18; API, PostgreSQL **and** the load generator share it (pessimistic) |
| API | `uvicorn app.main:app --workers 2`, Python 3.13, `AI_PROVIDER=offline` (no paid provider traffic) |
| Database | PostgreSQL 16, fresh database per run, migrated with Alembic |
| Dataset | deterministic (seed 42), synthetic only: 40 learners in 3 careers with 0, 60, 600 or 2,500 graded answers (12/16/8/4 learners), 15,760 answers over 200 days |
| Workload | closed-loop clients, each signed in as one learner (heaviest first): 30% question-bank search, 15% career progress, 15% career analytics, 10% plan, 15% history, 15% submit an answer |
| Run | 5 s warm-up (not counted), then 30 s per level; 10 s client timeout |
| Code | baseline: commit `afff3c4`; optimized: the same plus the two query changes below |

### Before and after

| Clients | Version | Requests (ok) | Errors | Throughput | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| 1 | baseline | 583 | 0 | 19.4 req/s | 13.7 ms | 181.9 ms | 321.7 ms |
| 1 | optimized | 1,555 | 0 | 51.8 req/s | 14.1 ms | 43.0 ms | 51.1 ms |
| 8 | baseline | 1,899 | 0 | 63.3 req/s | 63.1 ms | 446.1 ms | 712.9 ms |
| 8 | optimized | 4,010 | 0 | 133.7 req/s | 50.6 ms | 128.6 ms | 200.2 ms |

With one client (a learner with 2,500 answers) the overall p95 fell by **76%** (181.9 → 43.0 ms);
with eight clients (mixed histories) by **71%** (446.1 → 128.6 ms), and throughput roughly
doubled. Per endpoint (requests counted, p50 / p95 / p99 in ms):

| Endpoint | 1 client, baseline | 1 client, optimized | 8 clients, baseline | 8 clients, optimized |
|---|---|---|---|---|
| search | 162: 12.2 / 16.8 / 18.5 | 487: 12.3 / 16.6 / 17.7 | 564: 34.1 / 150.0 / 326.9 | 1,225: 35.0 / 70.0 / 89.5 |
| career progress | 99: 8.4 / 11.7 / 13.1 | 246: 8.3 / 10.8 / 12.0 | 268: 31.8 / 163.2 / 393.1 | 601: 33.4 / 70.7 / 91.4 |
| **career analytics** | 87: 131.3 / 308.2 / 335.9 | 251: 37.8 / 51.1 / 52.7 | 299: 178.5 / 546.6 / 721.9 | 617: 69.0 / 128.4 / 160.4 |
| **plan** | 66: 134.3 / 319.5 / 394.9 | 157: 31.6 / 42.4 / 133.3 | 199: 260.1 / 763.8 / 1016.8 | 387: 112.5 / 208.9 / 284.9 |
| history | 85: 18.1 / 22.1 / 23.3 | 215: 18.3 / 22.6 / 24.0 | 281: 70.4 / 336.0 / 498.1 | 578: 65.7 / 116.2 / 136.8 |
| submit an answer | 84: 11.4 / 13.9 / 15.0 | 199: 11.9 / 15.4 / 20.4 | 288: 61.5 / 296.3 / 417.2 | 602: 56.2 / 107.4 / 132.7 |

Only analytics and the plan changed. The other endpoints' single-client latency is the same; at
eight clients they got faster because the two slow endpoints stopped hogging the CPUs.

### What was slow, and why

SQL statements per request were measured at 0, 50, 500 and 2,000 answers for one learner: **no
endpoint's count grows with history** (no N+1). Two endpoints' *time* did, about 10× from 0 to
2,000 answers: career analytics and the plan. Profiling showed why. Both loaded every answer as
a whole ORM row (the answer text and its feedback JSON) to compute counts and best scores.
At 2,000 answers, decoding the feedback JSON alone was ~55 ms of a ~124 ms analytics request.

- **Analytics** now selects only the five values it uses, reading the one feedback field it needs
  (`feedback ->> 'evaluator'` / `json_extract`) in SQL.
- **The plan** reads ids and scores, and loads whole answers only for the one or two weak
  questions whose feedback it quotes.

Both return identical results: 18 analytics and plan responses for empty, small and large
histories, several date ranges, mixed evaluators and other careers were compared byte for byte
before and after, on SQLite and on PostgreSQL.

Query plan for a 2,500-answer learner (PostgreSQL, `EXPLAIN ANALYZE`). Both versions use the
existing index `ix_practice_user_track_question (user_id, track, question_id)` for the lookup;
the whole-row version also spilled its sort to disk:

```
before  Sort Method: external merge  Disk: 4768kB   Execution Time: 17.7 ms   (2,798 rows, whole rows)
after   Sort Method: quicksort  Memory: 389kB        Execution Time: 12.1 ms   (2,798 rows, 5 columns)
        -> Bitmap Index Scan on ix_practice_user_track_question
```

**Considered and not done:** an index on `(user_id, track, created_at)` to avoid the sort. The
in-memory sort is ~2 ms of the 12; most of the time is reading the rows, which that index
wouldn't avoid, and it would add a write per answer. Not justified by these numbers.

### Overload

64 clients for 20 s (8× the knee), same machine:

| Run | Requests | Errors | Throughput | p50 | p95 | p99 | API memory |
|---|---|---|---|---|---|---|---|
| optimized, before the fix below | 2,589 | 4 (0.15%) | 129.2 req/s | 438.7 ms | 1,110 ms | 1,554 ms | 397 → 432 MB |
| optimized, with the fix, fresh database | 2,780 | **0** | 139.0 req/s | 412.8 ms | 1,066 ms | 1,487 ms | |

Throughput plateaus (the four CPUs are saturated), latency rises, memory stays bounded, and the
service answers its readiness check in ~10 ms right after. Work is bounded by uvicorn's thread
pool and the database connection pool, not queued without limit.

The overload run found a **real bug**: two first views of a learner's plan at the same moment both
created plan version 1, and the second answered 500 (a unique-constraint violation); in real use,
two tabs opening the dashboard at once. Now the second uses the version the first saved
(`tests/test_roadmap.py::test_two_tabs_opening_a_new_plan_at_once_both_get_the_same_plan`, which
failed before the fix). The two dropped connections in that run followed those two errors and
went away with them.

**Shedding:** when every database connection stays busy for `DB_POOL_TIMEOUT_SECONDS` (default
10 s; SQLAlchemy's default was 30 s), the request is answered **503 `server_busy` with
`Retry-After: 2`** instead of failing later as a generic 500 (`tests/test_overload.py` exhausts
the real pool and checks the answer arrives within the bound, and that service recovers).

### Budgets (run in CI)

- `tests/test_query_budgets.py`: SQL statements per request for search, progress, analytics,
  history, facets, plan, reviews, resume and submitting an answer must not grow between an empty
  and a 300-answer history, must stay within a recorded budget, and analytics and the plan must
  never load every answer whole again. These fail on the code before the optimization. They
  count statements, not milliseconds, so they don't flake.
- `npm run size:check` (frontend job): the app shell (what `index.html` loads up front) stays within
  300 KB gzipped (today 281.6 KB) and the largest lazy chunk (the code editor) within 700 KB (674.5 KB).

### Frontend

Production build served by `vite preview` on the same machine, cold loads, median of 7
(`frontend/scripts/measure-load.mjs`). These are baseline measurements; nothing was changed here:

| Page | CPU | First contentful paint | DOMContentLoaded | JavaScript (uncompressed) |
|---|---|---|---|---|
| `/` | 1× | 192 ms | 83 ms | 947 KB |
| `/login` | 1× | 180 ms | 88 ms | 947 KB |
| `/` | 4× slower | 564 ms | 263 ms | 947 KB |
| `/login` | 4× slower | 500 ms | 242 ms | 947 KB |

Headless Chrome reported no paint entry in some unthrottled runs; those medians use the runs
that did (5 of 7 and 4 of 7). Most pages are in the entry chunk. Splitting routes out would
shrink it, but the offline mode precaches the app shell, so pages split out wouldn't work offline
until visited. That trade-off needs a decision of its own, so it isn't made here.

### Reproduce, and when comparisons are invalid

```bash
cd backend
DATABASE_URL=postgresql+psycopg://… AI_PROVIDER=offline AUTH_RATE_LIMIT_PER_MINUTE=1000000 \
  PRACTICE_ANSWERS_PER_HOUR=1000000 LOG_LEVEL=WARNING uvicorn app.main:app --port 8300 --workers 2
python scripts/perf_journeys.py seed --base-url http://127.0.0.1:8300 --database-url postgresql+psycopg://…
python scripts/perf_journeys.py run --base-url http://127.0.0.1:8300 --concurrency 1 8 --duration 30 --label mine
```

Compare runs only on the same machine, with the same dataset (seed and sizes), database
version, worker count and nothing else running. The load generator shares the CPUs, so absolute
numbers are pessimistic, and none of this says anything about production scale or real users.
Each run's machine, commit and dataset are recorded in its JSON.

## The written-answer coach on long and dictated answers (2026-11-04, rubric v5)

Local scoring and evidence extraction (`app.careers.grading.grade`, rubric v5 with the
contradiction rule), one question, synthetic answers, median of 5 runs in one process:
Python 3.13, x86_64, 4 CPUs, the development container (not production hardware). The answer
limit is 6,000 characters (API schema and the answer box), unchanged.

| Answer | Characters | Words | Median |
|---|---|---|---|
| short | 187 | 33 | 0.7 ms |
| typical | 1,128 | 198 | 1.5 ms |
| at the limit, typed | 6,000 | 1,054 | 6.2 ms |
| at the limit, dictated (no punctuation) | 5,937 | 1,054 | 17.8 ms |
| at the limit, with contradictions | 6,000 | 1,115 | 16.4 ms |
| at the limit, adversarial ("i asked and i called and …" repeated) | 6,000 | 1,435 | 128 ms (max 152) |
| at the limit, no spaces | 6,000 | 1 | 4.4 ms |

The adversarial case spends its time in the rubric's action patterns over one long unpunctuated
run (about 130 ms in `_covered`; the contradiction rule adds about 12 ms). It is bounded by the
6,000-character limit and well inside the request budget, so no limit was changed and no
regression check was added; a realistic dictated answer at the limit takes under 20 ms.

## The written-answer coach with the grader-instruction boundary (2026-11-04, rubric v6)

Rubric v6 reads each sentence through a folded copy of the text and cuts attack passages out of
run-on sentences. Measured on `f835c25`: rubric v5 (`a3fada4`'s grading.py, loaded from git) and
v6 graded the same synthetic answers in one process, median of 5 runs each, on an idle
development container (Python 3.13, 4 CPUs; not production hardware). The inputs were rebuilt for
this comparison, so compare the two columns with each other, not with the table above.

| Answer | Characters | Words | Rubric v5 | Rubric v6 |
|---|---|---|---|---|
| short | 187 | 33 | 0.8 ms | 1.0 ms |
| typical | 1,086 | 196 | 2.9 ms | 4.0 ms |
| at the limit, typed | 5,487 | 984 | 7.4 ms | 12.1 ms |
| at the limit, dictated (no punctuation) | 5,383 | 1,000 | 19.5 ms | 23.9 ms |
| at the limit, with contradictions | 5,791 | 1,056 | 13.8 ms | 13.7 ms |
| at the limit, an attack in every paragraph | 5,284 | 945 | 6.9 ms | 11.2 ms |
| at the limit, attacks in a dictated answer | 5,179 | 959 | 1.7 ms | 37.2 ms |
| at the limit, adversarial ("i asked and i called and …") | 5,999 | 1,440 | 43.1 ms | 49.3 ms |
| at the limit, spaced-out letters | 5,979 | 2,990 | 18.5 ms | 5.3 ms |
| at the limit, no spaces | 6,000 | 1 | 6.0 ms | 7.7 ms (max 8.1) |

The first v6 draft took about 30 ms for a typed answer at the limit: it searched every sentence
twice and folded plain ASCII character by character. Searching once per sentence and skipping the
fold for ASCII text (which it leaves unchanged) brought that to about 12 ms with the same results
on every career set. The dictated answer full of attacks is the slowest new case because v5
dropped it whole without grading it, while v6 cuts each attack and grades the rest. Every case is
bounded by the 6,000-character limit and stays under 50 ms, so no limit was changed.

## Earlier measurements: the problem-browsing mix (2026-11-01)

The sections below are from before most current features existed, with a different endpoint
mix. They are kept for the judge numbers and for history. Don't read them as current.

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
through all 12 problems the library had at the time (it now has 300). Time to verdict = from POST until the final verdict is visible.

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
  The pre-launch runs above share one machine with their load generator.
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
