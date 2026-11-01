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
                         │              │
               ┌─────────▼───┐  ┌───────▼──────┐
               │ PostgreSQL  │  │ AI provider  │
               │ + job queue │  │ adapter      │
               └──────▲──────┘  │ offline│Claude│
                      │         └──────────────┘
         SKIP LOCKED  │
               ┌──────┴──────┐  HTTPS + token  ┌──────────────┐  docker run --runtime=runsc
               │ judge worker│────────────────▶│   runner     │──────────────▶ ┌──────────────────┐
               │ (judging)   │◀──── output ────│ (no DB creds)│                │ gVisor sandbox    │
               └─────────────┘                 └──────────────┘                │ (one per submit)  │
                                                                               └──────────────────┘
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
        failure_offline.py  Rule-based "explain my failure" (javac messages, exceptions, wrong answers)
        interviewer_offline.py  Rule-based interviewer + explainable rubric scorer
        anthropic_provider.py  Claude via the official SDK, structured outputs
        static_analysis.py     Explainable checks on Java source
        service.py       Policy: auth, unlock order, budgets, sanitizing, fallback, history
      judge/
        harness.py       Generates the Java test driver; parses and compares results (pure)
        backends.py      ExecutionBackend: Disabled | Queued (+ admission control)
        judge.py         Runs a submission through the runner and maps the result to a verdict
        runner_client.py HTTP client for the runner service
    worker.py            Judge worker process: claim → judge → store; retries; crash recovery
runner/                  SEPARATE SERVICE: isolated execution (deploy on its own gVisor VM)
  app/sandbox.py         docker run --runtime=runsc with every isolation flag; output caps; timeouts
  app/main.py            POST /v1/run (bearer token), bounded concurrency
  sandbox-image/         JDK image + trusted entrypoint that receives code over stdin
  tests/                 unit tests + 16 threat-model checks in the real sandbox
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

## 3b. Frontend layout

```
frontend/src/
  api/          client.ts (typed fetch + ApiError), endpoints.ts, queries.ts (TanStack Query),
                schema.d.ts (GENERATED from docs/openapi.json), types.ts (friendly aliases)
  auth/         AuthProvider (token in memory + localStorage, expiry timer, 401 → sign out),
                RequireAuth route guard, session helpers
  app/          router (lazy-loads the workspace), layout, providers
  components/   Button, Badge, Card, Field, Spinner, Loading/Error/Empty states
  features/     landing · auth · problems · workspace (Monaco, drafts, coach, results)
                · dashboard (stat tiles, heatmap, progress bars) · history
  styles/       tokens.css (every visual value) + base/components/layout/features CSS
  test/         MSW mock server, fixtures, full-app integration tests
e2e/            Playwright journeys against the real backend
```

**Frontend decisions**

| Decision | Why |
|---|---|
| Types generated from the OpenAPI spec | The backend contract is the single source of truth; `npm run api:check` fails CI if they drift. |
| TanStack Query for server state | Caching, de-duplication, retries (never for 4xx) and polling, without hand-written effects. Submission polling stops when `execution_enabled` is false. |
| No global state library | Server state lives in the query cache; the only client state is auth (one context) and local UI state. |
| Monaco bundled locally, lazy-loaded | No third-party CDN script (strict CSP) and no Monaco download on the landing page: the initial JS is ~98 KB gzipped; Monaco loads only with the workspace. |
| Plain CSS + design tokens | The design pass can restyle everything by editing tokens and CSS without touching logic. |
| URL as state for filters | Shareable, refresh-safe library views. |
| Drafts in localStorage, scoped per user and problem | Never lose work; no server round-trip per keystroke. |
| Tests by role and name (Testing Library, Playwright) | Tests assert what users see and what screen readers announce, so a restyle doesn't break them. |

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

### 4.2 Mock interview turn
```
POST /api/v1/interviews/{id}/messages {message, code}
 → InterviewService.respond
     1. load + ownership check (404 otherwise); apply expiry if the deadline passed
     2. must be in_progress (409 interview_closed); answer cap (400 turn_limit_reached)
     3. budget check (429); sanitize code; append candidate turn
     4. provider.interview_turn(ctx: phase, transcript, code, static analysis, time left)
        → InterviewerReply {message, advance_phase}   (structured output; offline fallback)
     5. advance phase if asked (forward only; forced after 3 answers in a phase)
     6. append interviewer turn; record cost-only AIInteraction; commit
 → InterviewOut (full state, so the client never has to merge partial updates)
```
Finishing (or expiry, or abandoning) runs `provider.evaluate_interview` once and stores a
schema-validated `InterviewEvaluation`. Claude's evaluation must score every rubric dimension
exactly once or it's rejected and the offline scorer answers.

### 4.3 Submission and judging
```
POST /api/v1/submissions
  → validate size + problem → backend.admit(): per-minute rate, pending-job cap, queue depth
  → Submission(QUEUED, attempts=0) → 202 {id, status: QUEUED, execution_enabled: true}

worker (separate process), loop:
  claim oldest QUEUED  (SELECT … FOR UPDATE SKIP LOCKED → RUNNING, attempts+1)
  build Main.java from ALL test inputs + fresh 128-bit nonce
  POST runner /v1/run {Solution.java, Main.java, nonce}
     runner: docker run --runtime=runsc --network=none --read-only … (fresh container)
             stdin = nonce + base64 tar → javac → java Main (reads nonce first)
             ← {status, stdout ≤64 KB, compile_output, duration}
  harness.judge_cases(expected outputs, stdout, nonce)    ← comparison happens OUTSIDE the sandbox
  verdict precedence: COMPILE_ERROR > TIME_LIMIT > MEMORY_LIMIT > RUNTIME_ERROR > FAILED > PASSED
  store ExecutionResult (public detail only) + status; PASSED → progress event "solved"
  runner down / sandbox error → re-queue (bounded) → INTERNAL_ERROR after JUDGE_MAX_ATTEMPTS
  every 30 s: RUNNING jobs older than JUDGE_STALE_AFTER_S are recovered (worker crashed)

client polls GET /submissions/{id} every 1.5 s until is_terminal
```

## 5. AI design

| Concern | How it's handled |
|---|---|
| Vendor lock-in | `CoachProvider` protocol; offline and Anthropic implementations are interchangeable. |
| Consistent output | Pydantic models (`HintContent`, `CodeReview`, `FailureExplanation`) are the API contract **and** the structured-output schema sent to Claude (`messages.parse(output_format=...)`). |
| Grounding | Every prompt carries the instructor-written hint for that level, the expected complexity, static-analysis findings and the judge verdict. Failure explanations are grounded in the first failing **public** test, the exception's line in the learner's code, and the redacted compiler output, and must quote that evidence. |
| Hidden tests | The explainer is built from `public_result_view`, the same public-only view the submissions API returns, so the AI can't see (or leak) hidden inputs. |
| Repeat requests | One explanation per submission; asking again returns the saved one without spending budget. |
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
| gVisor sandbox in a separate runner service | Plain Docker on the API host; hosted judge; Firecracker | Docker alone shares the host kernel. gVisor gives a user-space kernel at low cost; a separate runner with no DB credentials limits the blast radius. Firecracker is stronger but much more infrastructure. |
| Postgres as the job queue (SKIP LOCKED) | Redis, RabbitMQ | One less service to run. The queue is transactional with the data, and SKIP LOCKED lets several workers share it safely. Revisit at very high volume. |
| Code sent over stdin, no bind mounts | Bind-mount a temp dir | Nothing from the host filesystem is ever visible in the sandbox, and it works even when the runner itself is containerized. |
| Comparison outside the sandbox | Compare inside the JVM | Hidden expected outputs never reach untrusted code. |
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
| 2. Frontend vertical slice | ✅ done | React + TS app: library, workspace (Monaco), coach panel, dashboard, history, e2e tests |
| 3. Mock interviews | ✅ done | Interview state machine, server-side clock, AI interviewer (offline/Claude), rubric evaluation, history, UI, e2e test |
| 4. Isolated runner | ✅ done | gVisor runner service, judge worker, threat-model tests, judge e2e, CI sandbox job |
| 5. Production | planned | Deployment, managed Postgres, Redis rate limits, refresh tokens, AI eval suite |
