# CodeCoach AI

**An AI-assisted Java interview practice platform with a deterministic judge.**
Learners solve curated data-structures-and-algorithms problems in a browser editor, get
progressive AI hints and structured code reviews, and track their progress. Correctness always
comes from test cases, never from the AI.

> **Status: Phases 1–4 of 5 complete.** The full product works end to end: React app →
> FastAPI → PostgreSQL, an AI coach, timed mock interviews, and **real judging of submitted
> Java in an isolated gVisor sandbox**, verified by unit, integration, threat-model and
> real-browser tests in CI.

| Workspace | Mock interview |
|---|---|
| ![Workspace with AI code review](docs/screenshots/premium-workspace.png) | ![Live mock interview](docs/screenshots/premium-interview-live.png) |
| **Interview feedback** | **Dashboard** |
| ![Rubric feedback](docs/screenshots/premium-interview-feedback.png) | ![Progress dashboard](docs/screenshots/premium-dashboard.png) |
| **Judged in the gVisor sandbox** | **Explain my failure** |
| ![Submission passed](docs/screenshots/08-judged-pass.png) | ![Failure explanation](docs/screenshots/10-explain-failure.png) |

## What works today

| Feature | Details |
|---|---|
| Problem library | 22 curated Java problems (10 easy, 12 medium) across arrays, strings, hashing, two pointers, sliding window, stacks, heaps, binary search, greedy and dynamic programming; 176 test cases (public + hidden); search, filters, pagination |
| Verified test data | Every problem ships with a trusted reference solution, and CI compiles and runs all of them against every test case and checks that each problem's starter code fails. New problems' expected outputs come from two independent implementations (a simple Python model and the Java reference) that must agree |
| Accounts | Register and login (Argon2id), guest demo sessions, **15-minute in-memory access tokens with a rotating `HttpOnly` `SameSite=Strict` refresh cookie** (reuse detection revokes stolen sessions; nothing in `localStorage`), logout-everywhere, **forgot-password by email** (pluggable console/file/SMTP sender; no account enumeration), **guest-to-account upgrade that keeps all progress**, automatic deletion of inactive guest accounts, rate limits **shared across API replicas**, password change, brute-force limiting; settings page with profile edit, **full data export** and **account deletion** (cascading, verified on SQLite and PostgreSQL) |
| AI hints | 4-level progressive ladder (nudge → concept → pseudocode → explanation), unlock order enforced by the server |
| AI code review | Structured JSON: complexity, issues with severity, category and line, strengths, next step, confidence |
| Explain my failure | One click on a failed verdict: the root cause (13 categories), a plain-English explanation, the evidence it relied on (failing public test, exception line or compiler message), a link to the line, and next steps. Built only from public test data; cached per submission. Verified with 9 buggy programs in the real sandbox |
| AI providers | `offline` (curated hints + static analysis; free, deterministic) or `anthropic` (Claude via structured outputs) with automatic fallback |
| AI safeguards | Prompt-injection framing, secret redaction, per-user daily budget, input caps, saved history; hidden tests never reach the model |
| AI evaluation | 66 hand-labelled Java samples (labels verified by the real judge) scoring review precision/recall, false alarms, Big-O accuracy and hint spoilers, with two held-out sets for honest generalization numbers ([results](docs/AI_EVALUATION.md)) |
| Code judging | **Run** checks the public tests in seconds without recording an attempt; **Submit** judges against public and hidden tests. Both execute in a **gVisor sandbox** (separate runner service: no network, read-only FS, CPU/memory/PID/time/output limits, non-root, no bind mounts). Postgres-backed job queue with a worker, admission control, bounded retries and crash recovery. 16 threat-model checks run hostile code in the real sandbox in CI |
| Mock interviews | Timed sessions through clarify → approach → code → complexity → test, a server-side clock, an AI interviewer (offline or Claude) that probes vague or brute-force answers, rubric feedback on 5 dimensions with evidence, and saved transcripts |
| Analytics | Solved/attempted by topic and difficulty, streaks, 28-day activity, acceptance rate, weakest topics |
| Recommendations | Explainable next problems: retry unfinished, strengthen weak topics, difficulty ladder |
| Web app | React + TypeScript: landing, auth, problem library (URL-synced filters), resizable 3-panel workspace with Monaco and autosaved drafts, hint ladder, reviews that highlight the flagged line, dashboard (stat tiles, activity heatmap, topic progress), history; mobile layout |
| Engineering | 418 backend tests (SQLite **and** PostgreSQL, incl. 104 that run in the real gVisor sandbox), 33 runner tests, 98 frontend tests, 16 Playwright end-to-end tests against the real backend, plus an opt-in audit that uses all 325 controls on every page (incl. automated **axe-core WCAG 2.1 AA** scans of every main screen on desktop and mobile); ruff, mypy, ESLint, strict TypeScript; API types generated from OpenAPI; Alembic; Docker Compose (db, migrate, api, web + judge profile: sandbox image, runner, worker); GitHub Actions; pip-audit, npm audit, Dependabot; Prometheus metrics, JSON logs, request IDs, health checks; CSP and security headers |

## Architecture

```
React + TypeScript ──HTTPS/JSON──▶ FastAPI (modular monolith) ──▶ PostgreSQL
                                        │
                                        ├──▶ AI provider adapter (offline | Claude)
                                        └──▶ Judge queue → worker → isolated runner (gVisor)
```
Full write-up: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

**Docker (recommended):**
```bash
cp .env.example .env        # optional for local dev
docker compose up --build
```
Open the app at <http://localhost:3000> and the interactive API docs at <http://localhost:8000/docs>.

**With code execution** (Linux host with [gVisor](https://gvisor.dev/docs/user_guide/install/) installed as the `runsc` Docker runtime):
```bash
EXECUTION_ENABLED=true RUNNER_TOKEN=$(openssl rand -hex 32) docker compose --profile judge up --build
```

**Without Docker** (two terminals):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./codecoach.db           # or point at your PostgreSQL
uvicorn app.main:app --reload                          # http://localhost:8000
```
```bash
cd frontend
npm ci
npm run dev                                            # http://localhost:5173
```

**Use Claude for the AI coach (optional):** set `AI_PROVIDER=anthropic` and
`ANTHROPIC_API_KEY=...` in `.env`. Without a key the free offline coach is used.

## Tests and checks

```bash
cd backend
pytest                                    # all backend tests (SQLite); sandbox tests auto-skip without gVisor
TEST_DATABASE_URL=postgresql+psycopg://codecoach:codecoach@localhost:5432/codecoach_test pytest
ruff check . && ruff format --check .     # lint + formatting
mypy app                                  # type check
python scripts/verify_reference_solutions.py   # needs a JDK: proves every test case is correct
pip-audit -r requirements.txt             # known-vulnerability scan
```
```bash
cd frontend
npm run lint && npm run typecheck         # ESLint + strict TypeScript
npm run api:check                         # generated API types match docs/openapi.json
npm test                                  # 98 unit + integration tests (Vitest, MSW)
npm run build                             # production bundle
PYTHON=../backend/.venv/bin/python npm run e2e   # Playwright: real browser + real backend
AUDIT=1 E2E_JUDGE=1 npx playwright test e2e/controls-audit.spec.ts --project=desktop   # ~15 min: uses every control on every page
```
```bash
cd runner
pytest -m "not sandbox"                   # runner unit tests
pytest -m sandbox                         # threat model: hostile Java in the real gVisor sandbox
```
CI runs all of the above on every push and pull request (a dedicated job installs a pinned,
checksum-verified gVisor), plus a migration round-trip and
Docker builds: [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Documentation

| Doc | For |
|---|---|
| [docs/API.md](docs/API.md) | Every endpoint with real examples, the auth flow, error codes, environment variables |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flow, AI design, decisions and trade-offs, roadmap |
| [docs/DATABASE.md](docs/DATABASE.md) | Tables, relationships, indexes, migrations |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Measured API latency/throughput and judge throughput, with the exact setup |
| [docs/AI_EVALUATION.md](docs/AI_EVALUATION.md) | How the AI coach is measured: labelled samples, held-out results, limitations |
| [docs/SECURITY.md](docs/SECURITY.md) | Implemented controls, AI safeguards, sandbox threat model and design |
| [docs/FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md) | Original frontend engineering handoff |
| [docs/FRONTEND_PROGRESS.md](docs/FRONTEND_PROGRESS.md) | Premium frontend changes, architecture decisions, validation and development workflow |
| [docs/openapi.json](docs/openapi.json) | Machine-readable API contract (kept in sync by a test) |
| [RESUME_LIFTER.md](RESUME_LIFTER.md) | How to explain this project in interviews and on a resume |

## Repository layout

```
backend/     FastAPI app, models, services, migrations, tests, Dockerfile
docs/        Architecture, API, database, security, frontend handoff
frontend/    React + TypeScript app, Vitest tests, Playwright e2e, nginx Dockerfile
runner/      Isolated execution service (gVisor sandbox), sandbox image, threat-model tests
.github/     CI workflow and Dependabot
docker-compose.yml, .env.example
```

## Roadmap

1. ✅ Backend foundation
2. ✅ Frontend vertical slice: library → workspace (Monaco) → hints/review → dashboard → history
3. ✅ Mock interviews: timed sessions, interviewer follow-ups, rubric scoring, history
4. ✅ Isolated Java runner: gVisor sandbox, judge worker, threat-model tests
5. Deployment (refresh tokens ✅, shared rate limits ✅, password reset ✅, AI evaluation suite ✅)

## Measured performance

On one 4-vCPU VM (API, PostgreSQL and the load generator together; details in
[docs/PERFORMANCE.md](docs/PERFORMANCE.md)):
- **API:** p50 9 ms / p95 18 ms with one client; ~254 req/s at p95 86 ms with 10 concurrent clients.
- **Judge:** ~4 s from submit to verdict for a single submission in a fresh gVisor sandbox;
  15.5 submissions/min with one worker, **29.3/min with two** (1.9×) with no double-judging.

## Known limitations

Listed honestly in [docs/SECURITY.md §5](docs/SECURITY.md#5-known-gaps-honest-list). No AI
accuracy or performance numbers are claimed until they've been measured. Sandbox residual
risks are listed in [SECURITY.md §4.3](docs/SECURITY.md#43-residual-risks-honest).
