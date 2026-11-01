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
> that verdict. Submitted Java runs in a gVisor sandbox inside a separate runner service, and
> I test the sandbox by attacking it with hostile code in CI. It's a React and TypeScript
> frontend over a FastAPI and PostgreSQL backend, with a provider-agnostic AI layer that uses
> structured outputs and cost controls, and about 370 automated tests, including real-browser
> end-to-end tests."

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
5. **Security:** submitted code is hostile by assumption. It never runs on the API server.
   A separate runner service starts a fresh **gVisor** container per submission: no network,
   read-only filesystem, CPU/memory/process/time/output limits, non-root, and no host files
   mounted. Comparison against hidden expected outputs happens *outside* the sandbox, so
   untrusted code never sees them.

## 3. Resume bullets (verified, so use these)

- Designed and built **CodeCoach AI**, a full-stack Java interview-practice platform
  (Python/FastAPI, PostgreSQL, SQLAlchemy/Alembic, Docker, GitHub Actions), with
  **30 documented REST endpoints** and an OpenAPI contract kept in sync by automated tests.
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
- Built an **isolated code-execution pipeline**: a Postgres-backed job queue (`SKIP LOCKED`),
  a judge worker with bounded retries and crash recovery, and a separate runner service that
  executes each submission in a fresh **gVisor** sandbox (no network, read-only FS, CPU/memory/
  PID/time/output limits), validated by **16 automated threat-model tests** that run hostile
  code (fork bombs, memory bombs, network and filesystem escapes, result forgery) in CI.
- Load-tested the API and judge and documented the setup: **p95 86 ms at ~254 req/s** (10
  concurrent clients) on a single 4-vCPU VM, and judge throughput that **scaled 1.9×** from one
  to two workers (15.5 → 29.3 submissions/min) with zero double-judging.
- Built an **AI evaluation suite** (52 hand-labelled Java samples whose verdict labels are
  verified by the real judge) measuring review precision/recall, false alarms, Big-O accuracy and
  hint spoiler rate; used it to cut false alarms on the tuning set from 14% to 0%, and reported
  the **held-out** result (80% precision, 50% recall) rather than the optimistic one.
- Built an **"Explain my failure"** AI feature that turns real compiler and JVM output into
  plain-English, line-referenced explanations (13 root-cause categories, a rule-based offline
  engine plus a Claude provider with structured output), grounded only in public test data,
  cached per submission so repeat requests cost nothing, and verified end to end against
  **9 real buggy programs judged in the gVisor sandbox**.
- **Found and fixed a hidden-test data leak** in the judge: compiler errors about the generated
  test driver echoed hidden test inputs to learners. Wrote an allowlist-based redactor (applied
  on write *and* read, so old rows were safe without a migration) and a regression test that
  fails against the real sandbox without the fix.
- Added a **Run vs. Submit** split like real online judges: runs check only the public tests in
  the same gVisor sandbox for fast feedback, never count as attempts or solves, and share the
  judge's abuse limits. Implemented as one `mode` column (with a safe migration) instead of a
  parallel pipeline, plus a public capabilities endpoint so the UI only offers what works.
- Turned one-off accessibility checks into an **automated WCAG 2.1 AA gate** (axe-core in
  Playwright, 11 screens on desktop and mobile, plus real judged results) that runs in CI. It
  immediately caught a label-in-name bug the manual sample missed.
- Built a **React + TypeScript** frontend (Vite, TanStack Query, Monaco editor) with a
  resizable three-panel workspace, autosaved drafts, a progress dashboard and a mobile layout,
  with API types **generated from the OpenAPI contract** so frontend and backend can't drift.
- Wrote **60 frontend unit and integration tests** (Vitest + MSW) and **Playwright end-to-end
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
Containers share the host kernel, so one kernel exploit escapes. I use gVisor, a user-space
kernel that intercepts the sandbox's syscalls, plus defense in depth: no network, read-only
root, a `noexec` size-capped `/tmp`, memory/PID/CPU/time/output limits, no Linux capabilities,
and running as `nobody`. The runner even refuses to start on plain Docker unless you explicitly
mark it as an insecure dev setup. I kept execution off until the design was approved, because
shipping no execution is safer than shipping unsafe execution.

**"How do you know the sandbox actually works?"**
I attack it in CI. A test suite submits hostile Java to the *real* gVisor sandbox: an
infinite loop, a memory bomb, a fork bomb, opening a socket, DNS lookups, writing to the root
filesystem, executing a dropped binary, filling the disk, reading a canary file I plant on the
host, dumping environment variables, flooding output, and forging test results. Each test
asserts the specific control held. CI installs a pinned, checksum-verified gVisor release to run them.

**"How does judging work end to end?"**
The API stores the submission as QUEUED and returns 202 right away. A separate worker claims it
with `SELECT … FOR UPDATE SKIP LOCKED`, so several workers can share the queue without
double-judging. It generates a Java test driver, sends the code and a random nonce to the
runner, and gets back bounded output. The worker compares the results against expected outputs
it never sent into the sandbox. Only infrastructure failures are retried, and a job whose
worker crashed is recovered after a timeout. The frontend polls until the verdict is final.

**"How do you know your AI feedback is any good?"**
I measure it. There's an eval suite of 52 hand-labelled Java samples (correct, buggy, slow,
messy), and even the labels are checked: every sample runs through the real judge, so a
mislabeled sample fails CI. It scores precision and recall of the issues found, false alarms on
clean code, Big-O accuracy, and whether level-1 hints give away the answer. The first run showed
14% false alarms on clean code, which I fixed with general rules (and the eval caught a
regression one of those rules introduced). Then the important part: I'd tuned on that set, so I
wrote a fresh held-out set and measured it without touching anything. It was clearly worse: 80%
precision, 50% recall, and only 50% Big-O accuracy, versus 100% and 95% on the tuning set. That
gap is the honest result. Heuristics overfit, which is the argument for the LLM reviewer, and
the same harness will measure Claude with one command once there's an API key.

**"How fast is it? How does it scale?"**
I measured it and wrote down the setup, because numbers without a setup mean nothing. On one
4-vCPU VM, with the load generator on the same machine, the API does p50 9 ms with a single
client and about 254 requests/s at p95 86 ms with 10 concurrent clients. At 50 clients the box
saturates, and I say that rather than quoting a pretty number. A submission takes about 4
seconds end to end, mostly starting a fresh gVisor sandbox and the JVM. One worker judges 15.5
submissions a minute. Adding a second gave 29.3, which is 1.9×, and I verified in the database
that no submission was judged twice, because that's what `SKIP LOCKED` is supposed to guarantee.

**"Couldn't someone fake passing results by printing them?"**
The driver reads a per-run random nonce from stdin *before* any of their code runs and keeps
it in a local variable, and result lines only count if they carry that nonce. It also writes
through a captured copy of `System.out`, so swapping the stream doesn't work either. I test
that with a real attack. The honest residual risk is deep reflection inside the same JVM,
which could only fake *their own* verdict, and I document it.

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

**"How does 'Explain my failure' work, and how do you stop it leaking hidden tests?"**
It's built from the same public-only view of the result that the submissions API returns: the
verdict, the first failing *public* test, the line in your code where an exception was thrown,
and compiler output that has already been redacted. Hidden tests are only ever counts, so the
AI literally never sees a hidden input, and when only hidden tests fail it suggests *kinds* of
edge cases instead of guessing one. The offline engine maps real `javac` messages (e.g. "cannot
find symbol" on `HashMap` → "add `import java.util.*;`"), exception types and expected-vs-actual
patterns (off by one, overflow, reversed order) to a cause, an explanation and next steps. The
Claude version uses the same schema. One explanation per submission is saved and re-served for
free. I tested it with nine deliberately buggy programs in the real sandbox, so the parsers are
checked against real compiler and JVM output, not text I made up.

**"You used ChatGPT too? How did that work?"**
Yes: two AI tools with separate jobs. I gave ChatGPT the design and layout work on its own
branch, and Claude the backend, systems and features. The branch came back based on an older
commit, so I merged it, resolved the conflicts (keeping both the new design and the feature
built in the meantime), and re-ran every suite before trusting it. Then I *built on* its work:
its accessibility scans had been run by hand, so I made them automated tests in CI, and they
found a bug its sample had missed. The point I'd make: AI output gets the same review and tests
as anyone's code, whichever tool wrote it.

**"Why is Run a mode on submissions instead of its own table or service?"**
A run needs exactly what a submission needs: the queue, the worker, the sandbox, rate limits,
ownership checks and the results view. A `mode` column reuses all of it, and the differences
are small and explicit: the driver is built from public tests only, the worker never marks a
run as solved, and progress queries filter on `mode = submit`. A separate pipeline would have
duplicated the security-critical path, and duplicated security code drifts.

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
12. **A missing production dependency.** Every test passed, but running the stack in
    containers crashed the worker: `httpx` was only a dev dependency. I fixed it and added a CI
    step that imports every container entrypoint with runtime dependencies only.
13. **A broken default quick start.** Making `RUNNER_TOKEN` "required" in Compose broke plain
    `docker compose up`, because Compose interpolates inactive profiles too. I caught it by
    validating both profiles; the services themselves now refuse to start without a token.
14. **The OOM message on the "wrong" stream.** The memory-bomb test failed because the JVM
    prints its out-of-memory notice on stdout, not stderr. The test against the real sandbox
    showed the actual behavior, and the classifier now checks both streams.
15. **A config fix that never applied.** My earlier `env.py` fix for migrations silently
    didn't apply (the text had been reformatted), and the next migration had the same bug. I
    fixed it, verified the output, and added a test that fails if any migration imports app code.
16. **Account deletion that wouldn't have deleted.** SQLite ignores foreign keys unless you
    switch them on per connection, so "delete my account" would have left orphaned data in
    local runs while PostgreSQL cascaded correctly. I turned FK enforcement on, and a test now
    counts every table's rows for the deleted user on both databases.
17. **Signing out sent people to the login page.** After deleting an account, the router
    (which renders navigations as transitions) still had the protected Settings page mounted,
    and its guard redirected to login. The fix is semantic: the auth state records a
    *deliberate* sign-out, so guards send the user home, while an *expired* session still goes
    to login with an explanation.
18. **A contaminated benchmark.** My first judge benchmark looked slow, and the worker logs
    showed `COMPILE_ERROR`s I didn't expect: the *API* benchmark had queued placeholder
    submissions, so the judge was busy compiling Java during both measurements. I discarded both
    runs, changed the load tester so the API benchmark never creates judge work, and
    re-measured on an empty queue. I also investigated a single unexplained error instead of
    rounding it away, and documented that it didn't reproduce.

19. **A data leak found by building a feature.** Writing the failure explainer meant reading real
    `javac` output, and I noticed that when a learner renames the method, the compiler complains
    about the judge's generated `Main.java` and *prints the offending source line*, which is a
    test call containing hidden inputs. Every hidden input of the problem was being shown to the
    learner. I reproduced it, fixed it with an allowlist-based redactor (keep only messages and
    symbol lines that can't contain literals; drop echoed source), applied it on read as well as
    write so old data was covered without a migration, and proved the fix: the real-sandbox test
    fails with `hidden input [-1000000000, -999999999] leaked` when the redactor is turned off.
20. **The throw line isn't the bug line.** The first index-error explanation said "line 5",
    which is where `nums[i]` threw, but the bug was the `<=` in the loop header on line 4. The
    explainer now names the suspicious loop bound separately from the line that threw.

21. **An accessibility bug no human noticed.** The mobile menu button *showed* "Menu" but its
    accessible name was "Open navigation". Voice-control users say what they see ("click Menu"),
    so it wouldn't respond (WCAG 2.5.3). A manual axe sample had passed; making the scan an
    automated test over every screen at phone width caught it. The fix was to *remove* an
    `aria-label`, which is a good reminder that more ARIA isn't always better.
22. **A sandbox test that checked the wrong thing.** The "are we in gVisor?" test looked for the
    word "gvisor" in the kernel version, which changes between gVisor releases (one reported
    `4.4.0`) and fails for no security reason. The property that matters is that the code sees
    a kernel that isn't the host's. I rewrote the test to assert that, and checked it both ways:
    under plain Docker it sees the host kernel and fails; under gVisor it passes.
23. **A review that would have over-trusted a Run.** A code review linked to a *run* would have
    told the AI "Judge verdict: PASSED", though hidden tests never ran. Reviews of runs now say
    "PASSED on public tests only (a Run; hidden tests were not executed)", with a test.

24. **A test that passed for the wrong reason.** CI failed on "History shows the attempt": the
    check found *two* "Two Sum" links. On CI's slower machine, the History page was still loading,
    so the Dashboard was on screen, and the new design had added a second "Two Sum" link to it.
    That meant the old check could have passed while looking at the Dashboard all along. The
    fix waits for the History page and looks inside its table. It's a reminder that a flaky
    failure can be a weak test showing up, and that's worth fixing rather than retrying.

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

1. `EXECUTION_ENABLED=true RUNNER_TOKEN=$(openssl rand -hex 32) docker compose --profile judge up --build`
   (on a Linux machine with gVisor), then open `http://localhost:3000`.
2. Click **Try it now**: a guest session opens *Two Sum* in the three-panel workspace.
3. Paste a nested-loop solution. Note "Draft saved"; refresh, and it's still there.
4. **Get a hint**, then unlock level 2. Explain that level 3 can't be requested early: the
   server enforces the order (show the 409 in `/docs` if asked).
5. **Code review** → it flags O(n²) vs. target O(n); click **line 3** and the editor highlights it.
6. **Run** a buggy version first: public tests only, a "Run · public tests only" badge, and
   nothing recorded. Then **Submit** it: per-test feedback for the public tests, and only a count for the
   hidden ones. Then submit the fix: **PASSED, 7/7, hidden 4/4**, judged in gVisor in a few
   seconds. Explain the sandbox and why expected outputs never enter it.
   Before fixing, click **Explain this failure**: it names the cause, quotes the failing public
   test as evidence and links to the line. Point out it never mentions hidden inputs.
7. **Interview**: start a 15-minute interview. Give a vague answer and watch it probe; give a
   brute-force idea and it asks for better; then finish and walk through the rubric evidence.
8. **Dashboard**: stats, heatmap, topic bars, and the recommendation reasons.
9. Show the GitHub Actions run, especially the **sandbox** job attacking gVisor with hostile code.

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

### Session 2: secure code execution (Phase 4)
**Decision:** you chose the gVisor sandbox (recommended option) over a hosted judge or Firecracker.

**Built and verified:**
- `runner/`: a separate execution service (FastAPI). It runs one fresh gVisor container per
  submission with every isolation flag, sends code over stdin (no bind mounts), caps output,
  enforces a wall-clock limit with `docker kill`, bounds concurrency (503 backpressure),
  authenticates with a bearer token, and refuses to run on plain Docker unless explicitly allowed.
- Sandbox image: JDK 21 + a trusted entrypoint script (compile, then run).
- Test driver hardened: a per-run nonce read before learner code runs, a captured output stream,
  exception type and message per test, per-test timing.
- Judge worker: Postgres queue (`FOR UPDATE SKIP LOCKED`), verdict mapping, infrastructure-only
  retries, crashed-worker recovery, a `solved` progress event.
- Admission control: per-minute rate limit, pending-job cap per user, global queue depth.
- Migration `judge queue`, plus a regression test that fails if any migration imports app code.
- Frontend: live judging states, hidden-test counts, exceptions with messages, "never ran"
  tests, compiler output.
- Docker Compose `judge` profile (sandbox image, runner, worker); CI `runner` and `sandbox` jobs
  (the latter installs pinned gVisor `20260714.0` with checksum verification).
- **Real verification in this environment, with gVisor installed:** 16/16 threat-model tests,
  12/12 reference solutions PASSED through API → worker → runner → gVisor, the Playwright judge
  journey, and the full 7-service Compose stack judging real submissions (PASSED, FAILED,
  TIME_LIMIT).
- Totals: 165 backend tests (passing on SQLite and PostgreSQL), 28 runner tests, 51 frontend
  tests, 5 Playwright journeys.

**Not yet verified / not built:**
- The live Claude API path (still no API key here; fake-client tests only).
- Peak-memory measurement per submission (`memory_kb` stays `null` rather than invented).
- Production deployment on a dedicated gVisor VM (Phase 5).
- The new CI `sandbox` job's first run on GitHub (it installs gVisor on GitHub's runners).

### Session 2 (continued): account & privacy settings
**Built and verified:**
- `PATCH /api/v1/auth/me` (display name), `DELETE /api/v1/auth/me` (password + typed
  confirmation; cascading delete), `GET /api/v1/me/export` (everything about the user except credentials).
- SQLite foreign-key enforcement, so cascades behave the same as on PostgreSQL.
- Settings page: profile, password change (adopts the new token), AI & privacy notice, data
  download, delete account. Accessible header link to it.
- Deliberate sign-out goes home; an expired or revoked session goes to login.
- 7 backend account tests (both databases), 6 new frontend tests, and the Playwright account
  journey now renames and deletes the account in a real browser.
- **CI on GitHub: all 7 jobs green for Phase 4, including the sandbox job that installed gVisor
  on GitHub's runners and attacked it with the threat-model suite.**
- Totals: 172 backend tests (18 in the real sandbox), 28 runner, 57 frontend, 5 Playwright journeys.

### Session 2 (continued): AI evaluation suite + measured performance
**Built and verified:**
- `backend/evals/`: 38 tuning + 14 held-out hand-labelled samples; harness scoring review
  precision/recall/F1, false alarms on clean code, Big-O accuracy, schema validity, hint spoilers,
  relevance and code leaks; provider-agnostic (offline now, Claude with one flag).
- All 52 verdict labels verified by the real gVisor judge (52/52 match).
- Eval-driven analyzer fixes (two-pointer loops, constraint-aware guards, halving loops, linear
  targets, exponential recursion); the eval caught a regression, which got its own test.
- Results: tuning set P 80→100%, R 48→60%, false alarms 14→0%, Big-O 79→95%. **Held-out: P 80%,
  R 50%, false alarms 17% (1 of 6), Big-O 50%**, reported as the honest number.
- `docs/AI_EVALUATION.md`, `docs/PERFORMANCE.md`; `scripts/loadtest.py` with raw results.
- Measured: API p95 18 ms (1 client) / 86 ms at ~254 req/s (10 clients); judge ~4 s per
  submission, 15.5/min (1 worker) → 29.3/min (2 workers), no double-judging.
- Totals now: 232 backend tests (70 in the real gVisor sandbox), 28 runner, 57 frontend,
  5 Playwright journeys.

**Not yet verified / not built:**
- Claude's review quality (run `python -m evals.run --provider anthropic` once a key exists).
- Performance on production hardware (these are single-VM numbers).

### Session 3: "Explain my failure" + a hidden-test leak fix
**Built and verified:**
- `POST /api/v1/ai/explain-failure`: ownership-checked, only for learner-caused verdicts
  (`409 not_judged` / `not_failed` / `judge_error` otherwise), daily budget, saved to AI history,
  and cached per submission (asking again is free).
- Offline explainer (`failure_offline.py`): javac diagnostics (missing symbols and imports,
  `.length` vs `.length()`, lossy conversions, missing returns, syntax, signature changes),
  exceptions (index, null, arithmetic, parsing, stack overflow and more), wrong-answer patterns
  (off by one, overflow, reversed/unordered output, null, flipped booleans, whitespace), time
  and memory limits, and hidden-only failures. Claude provider with the same structured schema.
- The test driver now reports the **line in the learner's code** where an exception was thrown.
- **Security fix:** compile errors about the judge's driver no longer echo hidden test inputs
  (SECURITY.md §4.5). Proven against the real sandbox, with and without the fix.
- Frontend: "Explain this failure" card (cause, confidence, evidence, steps, "Go to line N"),
  clickable exception lines, and failure explanations in History.
- Tests: 45 new unit/API tests, 9 real-sandbox scenarios, 3 new frontend tests; the Playwright
  judge journey now asks for an explanation.
- Totals: 286 backend tests (79 in the real gVisor sandbox), 28 runner,
  60 frontend, 5 Playwright journeys.
- **CI on GitHub: all 7 jobs green**, including the sandbox job running the 9 explain scenarios
  and the judge journey on GitHub's runners with gVisor.

**Not yet verified / not built:**
- Claude's explanations with a live key (fake-client tests only, as for hints and reviews).
- An evaluation set for explanation quality (the 9 sandbox scenarios check cause and line,
  not wording).

### Session 4: merged the design pass, Run vs. Submit, automated accessibility
**Merged and verified ChatGPT's design branch** (`feature/premium-frontend`): new design system,
landing tour, analytics page, editor preferences, accessible tabs, draft fixes. It was based on
an older commit, so it lacked "Explain my failure"; conflicts in the workspace page and README
were resolved keeping both. All its tests plus ours passed after the merge, including the real
gVisor judge journey. The explanation card now scrolls into view in its new scrolling panel.

**Built and verified:**
- **Run mode:** `mode: run` on `POST /submissions` checks the public tests only (hidden inputs
  are not compiled into the driver), never counts as an attempt or solve, is excluded from
  history and stats, shares admission limits, and is refused with `503 execution_disabled`
  when code can't run. Migration `submission mode` (server default, safe on populated tables).
- `GET /api/v1/capabilities`, so the UI only shows Run where it works.
- Frontend **Run** button (Ctrl/⌘ + '), run badge and copy; the real-browser judge journey runs
  before submitting.
- **Automated accessibility gate:** axe-core WCAG 2.1 A/AA scans of 11 screens on desktop and
  mobile, plus judged results and the explanation card, in CI. Fixed the label-in-name bug it
  found and added an `<h1>` to the 404 page.
- Sturdier gVisor isolation test (guest kernel ≠ host kernel; verified under runc and runsc).
- Fixed a CI-only e2e failure: the History check could match the still-visible Dashboard; it
  now waits for the History page and checks inside its table.
- The e2e backend starts from an empty database every run (a stale local `e2e.db` broke after
  the schema change).
- Totals: 297 backend tests (80 in the real gVisor sandbox), 28 runner,
  80 frontend, 11 Playwright tests (incl. 4 accessibility scans).

**Not yet verified / not built:**
- Live Claude responses (still no API key here).
- Production deployment (Phase 5) and branch rename to `main` with required checks.

