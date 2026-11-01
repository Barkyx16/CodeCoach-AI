# Resume Lifter: CodeCoach AI

Your guide to reviewing this project and explaining it with confidence. It's updated at the
end of every build session. **Rule for everything below: only say what's built and verified.**
The "Session log" at the bottom tracks exactly what that is.

---

## 1. The 30-second pitch

> "CodeCoach AI is a Java interview-practice platform I designed and built with AI as my pair
> programmer. Learners solve curated problems in a browser editor and get progressive AI hints
> and structured code reviews. The key design decision is that correctness never comes from
> the AI: a deterministic test judge decides pass or fail, and the AI is an advisor grounded in
> that verdict. The backend is FastAPI and PostgreSQL with JWT auth, Alembic migrations, a
> provider-agnostic AI layer with structured outputs and cost controls, and 100+ tests that
> run on both SQLite and Postgres in GitHub Actions."

## 2. The 2-minute walkthrough (whiteboard order)

1. **Problem:** AI chatbots will happily hand you the answer or tell you wrong code is right.
   For interview prep you want hints that don't spoil it, and a verdict you can trust.
2. **Core idea:** separate *judging* (deterministic test cases) from *coaching* (AI). The AI
   is told the judge verdict and is never allowed to contradict it.
3. **Architecture:** React frontend → FastAPI modular monolith → PostgreSQL. The AI sits
   behind a provider interface, and Java execution goes to a separate sandboxed runner
   service.
4. **Hard parts I solved:**
   - Hints unlock one level at a time, **enforced on the server** so the UI can't be bypassed.
   - AI responses are **schema-constrained JSON** (Pydantic models double as the structured
     output schema), so the frontend always gets the same shape.
   - The **offline coach** (curated hints + static analysis) means the app works with no API
     key, tests are deterministic, and there's a fallback when the AI provider fails.
   - **Test data is verified:** every problem has a reference solution that CI compiles and runs
     against every test case, so a learner never gets a wrong verdict from a typo in the tests.
5. **Security:** I deliberately did *not* run user code yet. Plain Docker isn't a security
   boundary for hostile code, so I wrote a threat model and chose gVisor/Firecracker-style
   isolation before building it.

## 3. Resume bullets (verified, so use these)

- Designed and built **CodeCoach AI**, a full-stack Java interview-practice platform
  (Python/FastAPI, PostgreSQL, SQLAlchemy/Alembic, Docker, GitHub Actions), with
  **20 documented REST endpoints** and an OpenAPI contract kept in sync by automated tests.
- Built an **AI coaching layer** with progressive, server-enforced hint disclosure and
  schema-validated code reviews, behind a provider-agnostic interface with automatic fallback,
  secret redaction, prompt-injection framing and per-user daily cost budgets.
- Implemented **JWT authentication** with Argon2id hashing, token revocation, brute-force
  rate limiting and ownership-based authorization, covered by **100+ pytest tests** that run
  against both SQLite and PostgreSQL in CI.
- Curated a library of **12 Java problems with 88 public and hidden test cases**, and
  automated verification that compiles and runs reference solutions against every case in CI.

*Add after they're built and measured, never before:* runner throughput or latency,
p50/p95 API latency under load, AI hint-quality evaluation scores, frontend test coverage.

## 4. Interview questions you should expect, and how to answer them

**"Did you use AI to build this?"**
Yes, and say it with confidence, because that's the point of the project. "I used Claude as a
pair programmer. I wrote the product blueprint and requirements, made the architecture and
security calls, like refusing to run untrusted code until there's a real sandbox, and reviewed
and tested everything. My skill is directing AI to produce production-quality work and
knowing when its output is wrong." Then give an example of a judgment call from §5. Being
upfront about it is far stronger than being caught hiding it.

**"Why FastAPI instead of Spring Boot, since you know Java?"**
Typed Pydantic models give validation and OpenAPI docs for free, Python has the best AI SDK
ecosystem, and it let me learn a second backend stack. The Java knowledge shows up in the
problem content and the test-driver generator.

**"How do you stop the AI from giving away the answer?"**
Three layers: (1) the server refuses to skip hint levels (HTTP 409); (2) the prompt tells the
model not to write a full solution below level 4, and includes the instructor-written hint
for that level so it stays on track; (3) the response is constrained to a JSON schema with a
single `hint` field.

**"What is prompt injection and how do you handle it?"**
User code could contain text like "ignore your instructions." I keep instructions in the
system prompt, wrap user content in tags labeled as untrusted data, constrain the output to a
schema, and never execute or trust model output for anything security-relevant. At worst a
user misleads their own hint.

**"How does logout work with JWTs? They're stateless."**
Each user has a `token_version` column, and tokens carry it as a claim. Logout increments it,
so every older token fails verification. It's one integer, with no token blacklist table.

**"Why not just run the Java in Docker?"**
Containers share the host kernel; a kernel exploit escapes. For hostile code you want a
stronger boundary: gVisor (a user-space kernel) or a Firecracker microVM, with no network,
CPU/memory/pid limits, and a read-only filesystem. I designed that and left execution off
until it's approved, because shipping no execution is safer than shipping unsafe execution.

**"How do you know your test cases are right?"**
Every problem has a trusted reference solution. A script generates a Java test driver from
the problem's method signature, compiles both, runs every case, and compares the results. It
runs in CI. A second test proves the untouched starter code *fails*, so the tests aren't
trivially passable.

**"How would this scale?"**
Stateless API, so add replicas behind a load balancer; move the in-memory auth rate limiter to
Redis (AI budgets are already in the database, so they're exact across replicas); add a job
queue between the API and runner workers; and cache the problem list. I'd measure before
optimizing, and `/metrics` already exports per-route latency histograms.

**"What would you do differently?"**
Add refresh tokens with an HttpOnly cookie, build the AI evaluation set earlier, and put
topics in a join table instead of JSON once the library grows.

## 5. Judgment calls you can talk about

These are moments where the obvious path was wrong and a deliberate decision was made:

1. **Execution disabled on purpose.** The blueprint and security reasoning said a plain
   Docker sandbox isn't enough, so submissions are stored and queued but never run until the
   isolation design is approved.
2. **Timestamps bug caught before shipping.** Capturing real API output for the docs showed
   SQLite returning timestamps without a timezone. Fixed with a custom `UTCDateTime` column
   type, plus a regression test.
3. **Static-analysis false positive caught.** The reviewer reported O(n) space for code that
   only allocated `new int[0]`. Fixed the rule, plus a test.
4. **Saving AI history vs. data minimization.** The requirements said "save AI feedback" and
   the blueprint said "minimize stored prompts." Resolution: store the structured feedback
   shown to the user, never the prompt that contained their code.
5. **404 instead of 403** for other users' resources, so attackers can't confirm IDs exist.

## 6. Python concepts used here (for a Java developer)

| Python | Java equivalent | Where to look |
|---|---|---|
| Type hints `def f(x: int) -> str` | Static types, but checked by `mypy` instead of the compiler | everywhere; `mypy app` |
| Pydantic `BaseModel` | DTO + Bean Validation (`@NotNull`, `@Size`) | `app/schemas/` |
| FastAPI `Depends(...)` | Spring dependency injection (`@Autowired`) | `app/api/deps.py` |
| SQLAlchemy `Mapped[...]` models | JPA `@Entity` | `app/models/__init__.py` |
| Alembic | Flyway / Liquibase | `backend/migrations/` |
| `Protocol` | `interface` (structural: no `implements` needed) | `app/services/ai/base.py` |
| `@dataclass(frozen=True)` | `record` | `app/services/ai/base.py` |
| `enum.StrEnum` | `enum` | `app/models/__init__.py` |
| Decorators `@router.get(...)` | Annotations `@GetMapping` | `app/api/routes/` |
| `with ...:` context manager | try-with-resources | `app/db/` |
| pytest fixtures | JUnit `@BeforeEach` + parameter injection | `backend/tests/conftest.py` |

**Reading order to understand the code:** `main.py` → `api/routes/problems.py` →
`api/deps.py` → `services/ai/service.py` → `services/ai/offline.py` →
`services/ai/anthropic_provider.py` → `tests/test_ai_coach.py`.

## 7. How to demo it in an interview (5 minutes)

1. `docker compose up --build`, then open `http://localhost:8000/docs`.
2. `POST /api/v1/auth/guest` → copy the token → **Authorize**.
3. `GET /api/v1/problems/two-sum` and point out `hidden_test_count`; the hidden tests aren't in the payload.
4. `POST /api/v1/ai/hint` with level 3 → **409 hint_locked**. Then level 1 works.
5. `POST /api/v1/ai/review` with a nested-loop solution → structured review flags O(n²) at line 3.
6. `GET /api/v1/me/progress` and `/me/recommendations`, showing explainable reasons.
7. Show the CI run and `pytest` passing on Postgres.

---

## Session log

### Session 1: backend foundation (Phase 1)
**Built and verified:**
- FastAPI backend with 20 endpoints: auth, problems, submissions, AI hint/review/usage/history,
  progress, recommendations, health, metrics.
- PostgreSQL schema (9 tables) with an Alembic migration, verified upgrade → check →
  downgrade on PostgreSQL 16.
- 12 problems / 88 test cases; all 12 reference solutions pass every case (JDK 21).
- Offline AI coach plus a Claude provider (structured outputs; tested with a fake client, no
  live API calls made).
- 102 tests passing on SQLite and on PostgreSQL 16; ruff, mypy and pip-audit clean.
- Docker image built and run as non-root; the full `docker compose` stack (db → migrate →
  api) came up healthy.

**Not yet verified / not built:**
- The live Claude API path (no API key in the build environment). Unit-tested with a fake client only.
- GitHub Actions has not run yet. It runs on the first push or pull request.
- Frontend (Phase 2), mock interviews (Phase 3), code execution (Phase 4, awaiting approval).
