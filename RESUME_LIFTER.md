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
> that verdict. It's a React and TypeScript frontend with a Monaco editor on top of a FastAPI
> and PostgreSQL backend, with JWT auth, a provider-agnostic AI layer with structured outputs
> and cost controls, and about 150 automated tests, including real-browser end-to-end tests
> that run in GitHub Actions."

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
  rate limiting and ownership-based authorization, covered by **120+ pytest tests** that run
  against both SQLite and PostgreSQL in CI.
- Curated a library of **12 Java problems with 88 public and hidden test cases**, and
  automated verification that compiles and runs reference solutions against every case in CI.
- Designed a **timed mock-interview engine**: a server-enforced state machine (5 interview
  phases, deadlines, turn limits, one active session per user) driving an AI interviewer behind
  a provider interface, with schema-validated rubric evaluations on 5 dimensions and saved
  transcripts.
- Built a **React + TypeScript** frontend (Vite, TanStack Query, Monaco editor) with a
  resizable three-panel workspace, autosaved drafts, a progress dashboard and a mobile layout,
  with API types **generated from the OpenAPI contract** so frontend and backend can't drift.
- Wrote **48 frontend unit and integration tests** (Vitest + MSW) and **Playwright end-to-end
  tests** that drive a real browser against the real backend; served the production build
  from unprivileged nginx with a **strict Content-Security-Policy**.

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

**"Walk me through the frontend architecture."**
Server state lives in TanStack Query (caching, retries, polling), so there's no Redux. The
only global client state is auth. API types are generated from the backend's OpenAPI spec,
and CI fails if they drift. Monaco is bundled locally and lazy-loaded with the workspace
route, so the landing page ships about 98 KB of gzipped JS, and there's no third-party script,
which keeps the CSP strict. All styling goes through design tokens, so a designer can restyle
the app without touching logic.

**"How did you test the frontend?"**
Three layers. Unit tests for pure logic like draft autosave and date formatting. Integration
tests that render the *whole* app with real routes and providers, with the network mocked at
the fetch level by MSW, so the real API client runs. And Playwright tests in real Chromium
against the real FastAPI backend, which caught bugs the others couldn't. Tests find elements
by role and accessible name, the way users and screen readers do, so restyling doesn't break them.

**"Tell me about a bug you found."**
Pick one from §5. The nginx one is a good story: security headers were configured, but
`curl -I` showed they weren't being sent, because nginx drops server-level `add_header`
directives inside any `location` block that sets its own. I only caught it because I verified
the headers instead of assuming they worked.

**"How does the mock interview work?"**
It's a state machine on the server: clarify → approach → coding → complexity → wrap-up. Each
answer goes to an interviewer behind the same provider interface as the coach, and it returns
a structured reply: a message plus whether to advance the phase. The server owns the clock
(`deadline_at`), so refreshing the page or tampering with client time doesn't help, and an
expired interview is closed and graded on the next request. There's one active interview per
user, a message cap, and a phase auto-advances after three answers so it can't get stuck.
Claude's evaluation must score all five rubric dimensions exactly once or it's rejected and
the offline scorer answers. The final feedback is always produced, even when the daily AI
budget is used up.

**"Why does the offline interviewer exist? Isn't it fake?"**
It's a deliberate product decision. It makes the app free to demo and run without an API key,
gives deterministic behavior to test against, and is the fallback when the AI provider fails.
Every score it gives comes with evidence and is labeled low confidence, so it never pretends
to be more than it is.

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
6. **Security headers that weren't being sent.** The nginx config looked right, but `curl -I`
   showed no CSP. Cause: nginx's `add_header` inheritance rule. Fixed with a shared include
   and verified in a browser.
7. **Monaco loaded on every page.** A manual bundle-chunking rule made the landing page
   preload the 700 KB editor. Removing it let the lazy route split it out, and I verified it
   in the built `index.html`.
8. **An accessibility bug found by a test.** The password field's label wrapped its help
   text, so screen readers would announce the whole hint as the field's name. Fixed with a
   reusable `Field` component that uses `aria-describedby`.
9. **Chart colors validated, not eyeballed.** The first dashboard color pair failed a
   colorblind-safety check, so I switched to a validated one-hue ordinal ramp.
10. **A migration that would have crashed in production.** The autogenerated interview
    migration imported app code it couldn't see (a `NameError` on deploy), added a NOT NULL
    column with no default (fails on any populated table), and created an unnamed foreign key
    (the downgrade fails). I caught all three by testing upgrade, downgrade and re-upgrade on a
    populated Postgres database, then fixed `env.py` so future migrations never import app code.
11. **An empty interview editor.** The draft hook started before the problem's starter code
    loaded and never picked it up. An integration test caught it; the fix adopts late-arriving
    starter code unless the user has already typed.

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

**Frontend concepts (TypeScript/React for a Java developer):**

| Frontend | Closest Java idea | Where |
|---|---|---|
| TypeScript `interface` / generated types | DTO classes generated from an OpenAPI spec | `frontend/src/api/schema.d.ts` |
| React component (a function returning JSX) | A view class whose render output depends only on its inputs | `frontend/src/features/` |
| `useState` / `useEffect` hooks | Fields + lifecycle callbacks | `useDraft.ts` |
| Context (`AuthProvider`) | A request-scoped singleton bean | `frontend/src/auth/` |
| TanStack Query | A caching repository layer with retry policy | `frontend/src/api/queries.ts` |
| MSW in tests | WireMock | `frontend/src/test/server.ts` |
| Playwright | Selenium | `frontend/e2e/` |

## 7. How to demo it in an interview (5 minutes)

1. `docker compose up --build`, then open `http://localhost:3000`.
2. Click **Try it now**: a guest session opens *Two Sum* in the three-panel workspace.
3. Paste a nested-loop solution. Note "Draft saved"; refresh, and it's still there.
4. **Get a hint**, then unlock level 2. Explain that level 3 can't be requested early: the
   server enforces the order (show the 409 in `/docs` if asked).
5. **Code review** → it flags O(n²) vs. target O(n); click **line 3** and the editor highlights it.
6. **Submit**: an honest "saved, not run yet" message. Explain the sandbox decision.
7. **Interview**: start a 15-minute interview. Give a vague answer and watch it probe; give a
   brute-force idea and it asks for better; then finish and walk through the rubric evidence.
8. **Dashboard**: stats, heatmap, topic bars, and the recommendation reasons.
9. Show the GitHub Actions run: backend on Postgres, frontend, Playwright e2e.

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

**Not yet verified / not built (as of the end of session 1):**
- The live Claude API path (no API key in the build environment). Unit-tested with a fake client only.
- GitHub Actions had not run yet.

### Session 1 (continued): frontend vertical slice (Phase 2)
**Built and verified:**
- React 18 + TypeScript + Vite app: landing, register/login/guest, problem library,
  workspace (Monaco, resizable panels, autosaved drafts, Ctrl/⌘+Enter submit), hint ladder
  restored from history, structured review with line highlighting, results panel, dashboard
  (stat tiles, 28-day heatmap with table view, topic and difficulty progress), history, 404,
  and a mobile tab layout.
- API types generated from `docs/openapi.json`, with a drift check.
- 41 Vitest tests passing; 3 Playwright journeys passing in Chromium against the real backend.
- ESLint (0 warnings), strict TypeScript, production build; landing page loads about 98 KB of
  gzipped JS, with Monaco lazy-loaded.
- Production image (nginx-unprivileged) built; the full 4-service compose stack ran; CSP and
  security headers verified with `curl` and in the browser (no console errors).
- Backend copy fixes (pluralization, readable topic names): 103 backend tests passing.

**Not yet verified / not built:**
- The live Claude API path (still unit-tested with a fake client only).
- GitHub Actions: workflows are committed; check the first run's result on GitHub.
- Mock interviews (Phase 3); code execution (Phase 4, awaiting approval of the sandbox design).

### Session 1 (continued): mock interviews (Phase 3)
**Built and verified:**
- Interview state machine (phases, server-side deadline, expiry, abandon, idempotent finish,
  one active interview per user, 30-message cap, auto-advance after 3 answers per phase).
- Offline interviewer and rubric scorer; Claude interviewer and evaluator with structured
  outputs (validated against a fake client; the evaluation must cover all 5 dimensions).
- Alembic migration `mock interviews`: upgrade on a populated DB, downgrade, re-upgrade and
  `alembic check` all verified on PostgreSQL 16.
- 20 new backend tests (123 total, on SQLite and PostgreSQL); 7 new frontend tests (48 total);
  a new Playwright journey covering all five phases with the real editor (4 e2e tests total).
- GitHub Actions: the Phase 2 run was green on all 5 jobs.

**Not yet verified / not built:**
- The live Claude API path for hints, reviews and interviews (fake-client tests only; no API key here).
- Code execution (Phase 4) still awaits approval of the sandbox design in docs/SECURITY.md §4.
