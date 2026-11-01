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
| ![Workspace with AI code review](docs/screenshots/02-workspace-review.png) | ![Live mock interview](docs/screenshots/06-interview-live.png) |
| **Interview feedback** | **Dashboard** |
| ![Rubric feedback](docs/screenshots/07-interview-feedback.png) | ![Progress dashboard](docs/screenshots/03-dashboard.png) |
| **Judged in the gVisor sandbox** | |
| ![Submission passed](docs/screenshots/08-judged-pass.png) | |

## What works today

| Feature | Details |
|---|---|
| Problem library | 12 curated Java problems (10 easy, 2 medium), 88 test cases (public + hidden), search, filters, pagination |
| Verified test data | Every problem ships with a trusted reference solution, and CI compiles and runs all of them against every test case |
| Accounts | Register and login (Argon2id + JWT), guest demo sessions, logout-everywhere, password change, brute-force limiting |
| AI hints | 4-level progressive ladder (nudge → concept → pseudocode → explanation), unlock order enforced by the server |
| AI code review | Structured JSON: complexity, issues with severity, category and line, strengths, next step, confidence |
| AI providers | `offline` (curated hints + static analysis; free, deterministic) or `anthropic` (Claude via structured outputs) with automatic fallback |
| AI safeguards | Prompt-injection framing, secret redaction, per-user daily budget, input caps, saved history |
| Code judging | Submissions are judged against public and hidden tests in a **gVisor sandbox** (separate runner service: no network, read-only FS, CPU/memory/PID/time/output limits, non-root, no bind mounts). Postgres-backed job queue with a worker, admission control, bounded retries and crash recovery. 16 threat-model checks run hostile code in the real sandbox in CI |
| Mock interviews | Timed sessions through clarify → approach → code → complexity → test, a server-side clock, an AI interviewer (offline or Claude) that probes vague or brute-force answers, rubric feedback on 5 dimensions with evidence, and saved transcripts |
| Analytics | Solved/attempted by topic and difficulty, streaks, 28-day activity, acceptance rate, weakest topics |
| Recommendations | Explainable next problems: retry unfinished, strengthen weak topics, difficulty ladder |
| Web app | React + TypeScript: landing, auth, problem library (URL-synced filters), resizable 3-panel workspace with Monaco and autosaved drafts, hint ladder, reviews that highlight the flagged line, dashboard (stat tiles, activity heatmap, topic progress), history; mobile layout |
| Engineering | 165 backend tests (SQLite **and** PostgreSQL, incl. 18 against the real sandbox), 28 runner tests, 51 frontend tests, 5 Playwright end-to-end journeys against the real backend; ruff, mypy, ESLint, strict TypeScript; API types generated from OpenAPI; Alembic; Docker Compose (db, migrate, api, web); GitHub Actions; pip-audit, npm audit, Dependabot; Prometheus metrics, JSON logs, request IDs, health checks; CSP and security headers |

## Architecture

```
React + TypeScript ──HTTPS/JSON──▶ FastAPI (modular monolith) ──▶ PostgreSQL
                                        │
                                        ├──▶ AI provider adapter (offline | Claude)
                                        └──▶ Isolated Java runner (designed, not built)
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
npm install
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
npm test                                  # 51 unit + integration tests (Vitest, MSW)
npm run build                             # production bundle
PYTHON=../backend/.venv/bin/python npm run e2e   # Playwright: real browser + real backend
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
| [docs/SECURITY.md](docs/SECURITY.md) | Implemented controls, AI safeguards, sandbox threat model and design |
| [docs/FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md) | Screens, states, components, tokens and test-safe restyling rules for the design pass |
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
5. Deployment, refresh tokens, Redis-backed limits, AI evaluation suite

## Known limitations

Listed honestly in [docs/SECURITY.md §5](docs/SECURITY.md#5-known-gaps-honest-list). No AI
accuracy or performance numbers are claimed until they've been measured. Sandbox residual
risks are listed in [SECURITY.md §4.3](docs/SECURITY.md#43-residual-risks-honest).
