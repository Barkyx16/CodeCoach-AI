# CodeCoach AI

**An AI-assisted Java interview practice platform with a deterministic judge.**
Learners solve curated data-structures-and-algorithms problems in a browser editor, get
progressive AI hints and structured code reviews, and track their progress. Correctness always
comes from test cases, never from the AI.

> **Status: Phase 1 of 5 (backend foundation) complete.** The API, database, AI coach,
> analytics, tests, Docker setup and CI are built and verified. The React frontend is next.
> Running submitted Java is deliberately **disabled** until an isolated sandbox is approved;
> see [docs/SECURITY.md](docs/SECURITY.md#4-secure-java-execution-design-not-yet-built-needs-approval).

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
| Submissions | Asynchronous job API with the full judge status model (queued; execution disabled) |
| Analytics | Solved/attempted by topic and difficulty, streaks, 28-day activity, acceptance rate, weakest topics |
| Recommendations | Explainable next problems: retry unfinished, strengthen weak topics, difficulty ladder |
| Engineering | 102 pytest tests on SQLite **and** PostgreSQL, ruff, mypy, Alembic, Docker Compose, GitHub Actions, pip-audit, Prometheus metrics, JSON logs, request IDs, health checks |

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
Then open <http://localhost:8000/docs> for interactive API docs.

**Without Docker:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./codecoach.db           # or point at your PostgreSQL
uvicorn app.main:app --reload
```

**Use Claude for the AI coach (optional):** set `AI_PROVIDER=anthropic` and
`ANTHROPIC_API_KEY=...` in `.env`. Without a key the free offline coach is used.

## Tests and checks

```bash
cd backend
pytest                                    # 102 tests (SQLite)
TEST_DATABASE_URL=postgresql+psycopg://codecoach:codecoach@localhost:5432/codecoach_test pytest
ruff check . && ruff format --check .     # lint + formatting
mypy app                                  # type check
python scripts/verify_reference_solutions.py   # needs a JDK: proves every test case is correct
pip-audit -r requirements.txt             # known-vulnerability scan
```
CI runs all of the above on every push and pull request, plus a migration round-trip and a
Docker build: [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Documentation

| Doc | For |
|---|---|
| [docs/API.md](docs/API.md) | Every endpoint with real examples, the auth flow, error codes, environment variables |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flow, AI design, decisions and trade-offs, roadmap |
| [docs/DATABASE.md](docs/DATABASE.md) | Tables, relationships, indexes, migrations |
| [docs/SECURITY.md](docs/SECURITY.md) | Implemented controls, AI safeguards, sandbox threat model and design |
| [docs/FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md) | Screens, states, components and tokens for the design pass (arrives with the frontend) |
| [docs/openapi.json](docs/openapi.json) | Machine-readable API contract (kept in sync by a test) |
| [RESUME_LIFTER.md](RESUME_LIFTER.md) | How to explain this project in interviews and on a resume |

## Repository layout

```
backend/     FastAPI app, models, services, migrations, tests, Dockerfile
docs/        Architecture, API, database, security, frontend handoff
frontend/    React + TypeScript app (Phase 2)
.github/     CI workflow and Dependabot
docker-compose.yml, .env.example
```

## Roadmap

1. ✅ Backend foundation
2. ⏳ Frontend vertical slice: library → workspace (Monaco) → hints/review → dashboard
3. Mock interviews: timed sessions, interviewer follow-ups, rubric scoring, history
4. Isolated Java runner: **awaiting approval of the sandbox design**
5. Deployment, refresh tokens, Redis-backed limits, AI evaluation suite

## Known limitations

Listed honestly in [docs/SECURITY.md §5](docs/SECURITY.md#5-known-gaps-honest-list). Most
importantly, submissions are queued but not judged yet, and no AI accuracy or performance
numbers are claimed until they've been measured.
