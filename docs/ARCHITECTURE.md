# CodeCoach AI — Architecture

## 1. What the system does

A learner opens a Java interview problem, writes a solution in a browser editor, asks an AI
coach for hints or a code review, and submits for judging against public and hidden test
cases. Their progress, attempts and AI feedback are saved and analyzed to recommend what to
practice next.

The design principle running through every component: **correctness comes from deterministic
code, and AI is an advisor layered on top.** The AI can never mark a solution correct.

## 2. System context

```
                      ┌──────────────────────────────┐
  Browser             │  React + TypeScript (Vite)   │  Monaco editor, dashboards
                      └──────────────┬───────────────┘
                                     │ HTTPS · JSON · Bearer JWT
                      ┌──────────────▼───────────────┐
                      │        FastAPI backend       │  modular monolith
                      │  api → services → models/db  │
                      └──┬──────────────┬─────────┬──┘
                         │              │         │
               ┌─────────▼───┐  ┌───────▼──────┐  │ enqueue (future)
               │ PostgreSQL  │  │ AI provider  │  │
               │ users, ...  │  │ adapter      │  │
               └─────────────┘  │ offline│Claude│ ┌▼───────────────────────────┐
                                └──────────────┘ │ Isolated Java runner       │
                                                 │ (separate service; designed│
                                                 │  in SECURITY.md, not built) │
                                                 └────────────────────────────┘
```

## 3. Backend layout (modular monolith)

```
backend/
  app/
    main.py              App factory: wiring, middleware, CORS, routers, startup
    config.py            Settings from environment variables (pydantic-settings)
    errors.py            AppError hierarchy + one handler → the shared error envelope
    observability.py     Request IDs, JSON logs, per-route latency metrics
    metrics.py           Prometheus registry
    cli.py               `seed` and `openapi` commands
    api/
      deps.py            Dependency injection: DB session, settings, current user
      routes/            Thin HTTP layer: health, auth, problems, submissions, ai, me
    schemas/             Pydantic request/response models (the API contract)
    models/              SQLAlchemy ORM models (the data model)
    services/            Business logic. No HTTP types in here.
      auth.py            Argon2id password hashing, JWT issue/verify
      progress.py        Analytics + explainable recommendations
      rate_limit.py      Sliding-window limiter (auth brute-force protection)
      ai/
        base.py          Provider-neutral interface (CoachProvider protocol)
        offline.py       Curated hint ladder + static analysis (no key, deterministic)
        anthropic_provider.py  Claude via the official SDK, structured outputs
        static_analysis.py     Explainable checks on Java source
        service.py       Policy: auth, unlock order, budgets, sanitizing, fallback, history
      judge/
        harness.py       Generates the Java test driver; parses and compares results (pure)
        backends.py      ExecutionBackend interface (currently: Disabled)
    db/                  Engine/session factory, seed loader
    seed/problems/*.json Curated problem library (version-controlled content)
    seed/reference/*.java Trusted reference solutions (CI proves the tests are right)
  migrations/            Alembic migrations
  scripts/               verify_reference_solutions.py
  tests/                 pytest suite (runs on SQLite and PostgreSQL)
```

**Why a modular monolith?** One deployable keeps the system simple to run, test and debug,
while hard module boundaries (routes → services → models) keep it easy to split later. The
only part that *must* be a separate service is the Java runner, for security rather than
scale. That matches the blueprint principle: no microservices without a demonstrated need.

**Layering rule:** routes translate HTTP to service calls and nothing more. Services hold
all policy and never import FastAPI request types, so they can be unit-tested directly and
reused by a future worker process.

## 4. Key request flows

### 4.1 Hint request
```
POST /api/v1/ai/hint {problem_slug, level, source_code}
 → deps.get_current_user        verify JWT signature, expiry, token_version
 → CoachService.hint
     1. load problem                            404 if unknown
     2. unlock check: level ≤ highest_used + 1   409 hint_locked otherwise
     3. budget check: AI calls in the last 24h   429 rate_limited
     4. sanitize code: strip NULs, redact secrets, cap length
     5. static analysis → findings (grounding facts)
     6. provider.hint(ctx)  → on ProviderError → OfflineCoach (fallback)
     7. persist AIInteraction (response JSON, tokens, latency) + ProgressEvent
 → HintResponse (identical shape for every provider)
```

### 4.2 Submission (today and planned)
```
POST /api/v1/submissions → validate size + problem → Submission(QUEUED)
  → ExecutionBackend.enqueue()      today: DisabledExecutionBackend (no execution)
  → 202 {id, status: QUEUED, execution_enabled: false}

Planned (after the SECURITY.md design is approved):
  enqueue → job queue → runner worker (sandbox) → compile Solution.java + generated Main.java
          → run with CPU/memory/time/pid limits, no network, read-only FS
          → bounded stdout → harness.judge_cases() → ExecutionResult + status → client polls
```

## 5. AI design

| Concern | How it's handled |
|---|---|
| Vendor lock-in | `CoachProvider` protocol; offline and Anthropic implementations are interchangeable. |
| Consistent output | Pydantic models (`HintContent`, `CodeReview`) are the API contract **and** the structured-output schema sent to Claude (`messages.parse(output_format=...)`). |
| Grounding | Every prompt carries the instructor-written hint for that level, the expected complexity, static-analysis findings and the judge verdict. |
| Spoilers | Progressive disclosure is enforced **server-side** (409 for skipped levels), not just hidden in the UI. Below level 4 the model is told never to write a full solution. |
| Prompt injection | System prompt defines the tutor role; problem, code and analysis are fenced in tags and declared untrusted; model output is never executed; output is schema-validated. |
| Cost | Per-user daily budget enforced from the database; `effort=low`; input length cap; the offline provider is the default. |
| Reliability | Typed SDK errors, refusals and truncation become `ProviderError`, and the offline coach answers instead (`provider: "offline (fallback)"`). |
| Privacy | Secrets are redacted before any model call; prompts (which contain code) are not stored. Only the feedback shown to the user is saved. |

The offline coach isn't a mock. It's a real, deterministic product path: curated hints plus
static analysis. It makes the app free to demo and keeps CI tests independent of any network
or API key.

## 6. Key decisions and trade-offs

| Decision | Alternatives | Why |
|---|---|---|
| FastAPI + Pydantic v2 | Django REST, Flask | Typed request/response models produce OpenAPI automatically; async-ready. |
| PostgreSQL (JSONB) + SQLAlchemy 2 + Alembic | MongoDB | Relational data (users ↔ submissions ↔ problems) with real constraints; JSONB for flexible content like examples and signatures. |
| Tests run on SQLite and Postgres | Postgres only | Fast feedback locally; CI proves Postgres parity. A `UTCDateTime` type keeps timestamps identical on both. |
| JWT + `token_version` revocation | Server-side sessions, refresh tokens | Stateless verification with real logout/"log out everywhere" for one integer column. Refresh tokens are a future step. |
| Argon2id | bcrypt | Current OWASP first choice; memory-hard. |
| Problems seeded from JSON in Git | Admin UI | Content changes are code-reviewed, diffable, and verified in CI against reference solutions. |
| Execution disabled until a sandbox is approved | Run Java in Docker on the API host | Docker alone is not a security boundary for hostile code. Shipping no execution is safer than shipping unsafe execution. |
| In-memory auth rate limiter | Redis | Correct for a single instance; documented upgrade path. AI budgets already use the database, so they're exact across instances. |

## 7. Observability

- **Logs:** one JSON line per request (`request_id`, `method`, `path`, `status`, `duration_ms`).
- **Request IDs:** accepted from `X-Request-ID` (validated) or generated, then returned in the
  header and inside every error body, so a user's bug report maps to a log line.
- **Metrics:** `/metrics` (Prometheus): `codecoach_http_requests_total{method,route,status}`
  and `codecoach_http_request_duration_seconds` (histogram, p50/p95 via PromQL). Labels use
  route *templates*, so arbitrary URLs can't explode cardinality.
- **Health:** `/health` (liveness) and `/health/ready` (database round-trip; 503 when down).
  The Docker image has a `HEALTHCHECK`.

## 8. Roadmap

| Phase | Status | Scope |
|---|---|---|
| 1. Backend foundation | ✅ done | Auth, problems, submissions (queued), AI hint/review, progress, recommendations, migrations, Docker, CI |
| 2. Frontend vertical slice | next | React + TS app: library, workspace (Monaco), coach panel, dashboard |
| 3. Mock interviews | planned | Interview sessions as a state machine, timed turns, rubric scoring, history |
| 4. Isolated runner | **awaiting design approval** | See SECURITY.md §4 |
| 5. Production | planned | Deployment, managed Postgres, Redis rate limits, refresh tokens, AI eval suite |
