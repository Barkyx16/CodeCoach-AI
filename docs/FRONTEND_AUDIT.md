# Premium frontend: audit and proposal

Historical baseline: Phase 1 audit. The user subsequently approved implementation.
See [FRONTEND_PROGRESS.md](FRONTEND_PROGRESS.md) for delivered changes and current validation.
The findings below describe the original audited commit, before implementation.

Review the [visual design board](screenshots/frontend-design-proposal.png) and its
[standalone HTML source](FRONTEND_DESIGN_PROPOSAL.html). These are design documentation,
not an implemented product screen.

## Repository baseline

- Repository: `Barkyx16/CodeCoach-AI`.
- Audited upstream commit: `5b9dc7aa5f94e1cafa73965b652e70742cd11ab0`.
- Remote HEAD points to `claude/gallant-galileo-hapob6`; no remote `main` was returned.
- Working branch: `feature/premium-frontend`, created from remote HEAD. Nothing pushed.
- Read the README, architecture, API, database, security and frontend handoff; inspected
  manifests, CI, routes, models, API client, auth, screen components and existing tests.
- No AGENTS.md was found under `/workspace` at audit time.

## Existing architecture

```text
frontend/             React 18, TypeScript, Vite, CSS tokens, TanStack Query
  src/api/            Generated OpenAPI types, typed fetch client, query hooks
  src/auth/           JWT session, expiry, route protection
  src/app/            Router, providers, shared application shell
  src/components/     Buttons, fields, cards, badges, loading/error/empty states
  src/features/       Landing, auth, problems, workspace, dashboard, interviews,
                      history, settings
  src/styles/         Tokens, base, components, layout, feature styles
  e2e/                Playwright tests against an actual FastAPI server
backend/              FastAPI, Pydantic, SQLAlchemy, Alembic
  app/api/routes/     Thin HTTP handlers
  app/services/       Authentication, coaching, interviews, progress, judging
  app/models/         Relational data models
  app/worker.py       Database-backed judge queue worker
runner/               Separate execution service; Docker + gVisor
docs/                 API contract, system design, security, handoff, screenshots
.github/workflows/    Static checks, tests, sandbox integration, image builds
```

PostgreSQL is the deployment database; SQLite is a supported local/test option. Models
include User, Problem, TestCase, Submission, ExecutionResult, AIInteraction, ProgressEvent,
PracticeSession and InterviewTurn. The judge worker sends code to a separate runner with
no database access. The backend compares outputs outside the sandbox.

Authentication uses Argon2id passwords, short-lived bearer JWTs and token-version revocation.
The browser stores tokens in memory and localStorage. This survives refresh but remains an
XSS trade-off, already documented in SECURITY.md. Keep credentials server-side; an HttpOnly
refresh-cookie migration would be a coordinated backend task.

## Implemented features and actual contracts

| Experience | Existing implementation | Actual API families |
| --- | --- | --- |
| Landing and auth | Guest demo, registration, login, expiry handling | `/api/v1/auth/{guest,register,login,me,logout,password}` |
| Library | 12 Java problems, URL filters, topics, pagination | `/api/v1/problems`, `/api/v1/problems/{slug}`, `/api/v1/topics` |
| Workspace | Monaco, resizable desktop panels, mobile tabs, saved drafts, submit/poll/results | `/api/v1/submissions`, `/api/v1/submissions/{id}` |
| Coach | Progressive hints, structured reviews, line highlighting, budgets/history | `/api/v1/ai/{hint,review,usage}`, `/api/v1/me/ai-history` |
| Mock interviews | Server deadline, phased conversation, editor, evaluation, resume/history | `/api/v1/interviews`, `/{id}`, `/{id}/{messages,finish,abandon}` |
| Dashboard | Solved counts, acceptance, streaks, 28-day activity, topic/difficulty bars, recommendations | `/api/v1/me/{progress,recommendations}` |
| History | Submissions, AI feedback, interviews | `/api/v1/me/submissions`, `/api/v1/me/ai-history`, `/api/v1/interviews` |
| Settings | Display name, password, data export, account deletion | PATCH/DELETE `/api/v1/auth/me`, POST `/api/v1/auth/password`, GET `/api/v1/me/export` |

The offline coach is a genuine deterministic backend implementation using curated hints
and static analysis. It must remain visibly identified as built-in/offline. No live Claude
operation has been validated in this audit; no Anthropic binding is configured.

## Gaps and constraints

- **Run examples:** no separate public-test-only run endpoint exists. Submit is implemented;
  a distinct Run Code action needs an agreed backend contract. Do not disguise Submit as Run.
- **Streaming:** coach/interview routes return complete JSON, with no SSE/WebSocket contract.
  Show pending states rather than simulated token streaming.
- **Analytics:** current aggregates and 28-day event counts support the existing dashboard.
  There is no dedicated analytics page or daily accuracy/completion-series endpoint. Event
  counts must not be labelled as solved counts. Longer history can use paginated submissions
  only with an explicit aggregation strategy; otherwise request a backend extension.
- **Editor preferences:** font size, theme, tab size and wrapping controls are absent. They
  can be implemented as local browser preferences; syncing them across devices needs API work.
- **Landing:** workspace preview is static; a footer and richer interactive preview are absent.
  Any demonstration must say it is an example, or use the real guest-session workflow.
- **Navigation/accessibility:** existing skip link, focus styles, live regions, chart table
  view and reduced motion should be preserved. Mobile tabs currently lack arrow-key tablist
  behavior. Browser measurements confirm the authenticated header expands the page to 475 px
  at both 375 and 390 px viewport widths, across landing/dashboard/settings/workspace.
- **Settings:** ProfileCard does not render a general request error, only display-name field
  errors; a network/server failure can leave no visible explanation. Fix with a regression
  test in a later approved implementation phase.
- **Documentation drift:** README's small architecture sketch still says the runner is
  "designed, not built", despite the implemented service and integration tests.
- **Deployment:** deployment, refresh tokens and distributed auth rate limiting remain
  separate work. No claim of production readiness follows from this local audit. (Since then,
  refresh tokens and database-backed rate limits were built: [HARDENING.md](HARDENING.md).)

## Proposed frontend architecture

Keep React, TypeScript, Vite, TanStack Query, locally bundled Monaco, React Router and
react-resizable-panels. Keep the generated OpenAPI contract and the current feature folders.
The product already has the right foundations; replacing them would add migration risk.

Retain plain CSS with tokens rather than introducing Tailwind or shadcn during the restyle.
Add reusable presentation pieces only where repeated: page heading, section heading, metric
card and branded mark. Extract per-feature CSS from features.css gradually as screens are
restyled. Leave server state in Query, auth in its existing context, drafts/preferences in
scoped local storage, and filters in the URL.

Use CSS/SVG for the existing small charts. Consider Recharts only if approved analytics
needs interactive axes/tooltips; introduce Motion only if CSS cannot express a specific
useful interaction. Keep Monaco lazy-loaded. Current initial JS is 101.65 KB gzipped;
the shared editor chunk is 699.35 KB gzipped, downloaded only by editor routes.

Proposed navigation: public landing + auth; signed-in Practice, Dashboard, Interview,
History and account/settings. Add Analytics only once its scope and truthful data sources
are agreed. Preserve all existing routes and deep links.

## Proposed design system

| Role | Proposed value / rule |
| --- | --- |
| Canvas | `#080D18`, near-black navy |
| Surface / raised | `#101A2B` / `#17243A` |
| Border | `#293B55`, thin, with stronger focus borders |
| Primary action | `#2F6FEB` with white text; hover `#2864D6` |
| Inline link / focus | `#8CB8FF` / `#A9CAFF` |
| Primary / secondary text | `#F3F6FC` / `#A8B7CE` |
| Red accent | `#F08086`, restrained danger treatment; never ordinary navigation |
| Charts | Sequential blue ramp, figures beside marks, table alternative |
| Typography | Self-hosted Inter + JetBrains Mono, retaining system fallbacks |
| Type scale | 12/14/16 px UI, 24–32 px page headings, fluid 40–64 px landing headline |
| Spacing | 4 px base; 8/12/16/24/32/48/64 px rhythm |
| Shape | 8–14 px corners; restrained shadow; avoid pill-shaped containers everywhere |
| Motion | 120–180 ms hover/focus transitions; reduced-motion override; no idle effects |
| Brand | Original geometric code mark, precise typography, subtle blue lighting |

The proposed primary button passes 4.5:1 with white text (4.57:1); secondary text against
the proposed surface is 8.57:1. Recheck all variants in implementation. Validate body text
at 4.5:1, large text and controls at 3:1,
chart steps against the final surface, plus real focus and disabled states. Status always
has words/icons as well as color. Match Monaco's literal theme colors to the CSS tokens.

Screen direction: a spacious landing with an authentic workspace example; compact useful
dashboard metrics; a dense, calm coding workspace; a focused interview transcript/editor;
readable history; settings with clear separation of profile, preferences and account actions.
No fabricated statistics, testimonials, pass results or AI replies.

## Proposed first implementation stage (requires design approval)

Phase 2: refine tokens, typography, shared component styling and responsive navigation.
Keep feature behavior and API contracts stable. Add original SVG branding and self-hosted
fonts with licenses. Verify contrast, keyboard access, mobile navigation and reduced motion.
Run frontend lint, types, unit/integration tests, build, API drift check and relevant browser
journeys. Commit the stage separately, then proceed through the requested page phases.

Approval requested by the user's handoff: show the architecture and design system before
major changes. No design implementation is included in this audit commit.

## Validation

| Check | Result in this environment |
| --- | --- |
| Frontend ESLint / TypeScript / generated API drift | Passed |
| Frontend Vitest | 57 passed, 11 files |
| Frontend production build | Passed; initial JS 101.65 KB gzip, editor shared chunk 699.35 KB gzip |
| Frontend production dependency audit | 0 known vulnerabilities reported |
| Backend ruff / formatting / mypy | Passed |
| Backend non-sandbox suite with JDK available | 162 passed, 70 deselected |
| Backend real sandbox integration suite, serial run | 70 passed, 162 deselected |
| Reference solution verifier | All 12 solutions pass every test case |
| Runner ruff / formatting / mypy / unit suite | Passed; 12 unit tests passed, 16 sandbox tests deselected |
| Browser core journeys, system Chromium | 4 passed; judge journey initially skipped with execution disabled |
| Browser judge journey, execution enabled | 1 passed: incorrect/correct Java, public/hidden feedback, dashboard solved count |
| Runner threat-model suite, serial recheck | 15 passed, 1 failed, 12 unit tests deselected; kernel-version string assertion described below |
| Responsive smoke check | Authenticated header overflows at 375/390 px; no document overflow at 768/1440 px on sampled routes |
| Uncaught browser exceptions in responsive sample | None observed |

The first backend run skipped 14 JDK-dependent tests because only a JRE was available.
Installed a workspace-local, official Temurin JDK and verified its published SHA-256;
the complete 162-test run above includes those tests. Initial sandbox runs overlapped and
interfered through shared container cleanup; interrupted results are not counted as passing.
The subsequent serial backend run completed all 70 sandbox tests successfully.

The environment has an actual gVisor executable (`runsc release-20260413.0`), and the Java
sandbox image built successfully. The runner failure is
`tests/test_threat_model.py::test_runs_inside_gvisor_as_nobody`: Java reports
`RESULT=4.4.0|nobody`, but the assertion requires a kernel version containing `gvisor`.
The isolated run completed successfully with the unprivileged user, but the test's OS-string
expectation does not match this installed runtime. This is a test/runtime compatibility issue;
the assertion remains unchanged and is reported as failed. All other 15 threat checks passed
on the serial recheck. The initial happy-path failure did not recur after serializing runs.

All five distinct existing browser journeys passed across the core and execution-enabled
runs. The initially skipped judge journey was subsequently executed successfully; it is not
counted as skipped in the final combined coverage. These passes do not resolve the mobile
header overflow independently observed above.

PostgreSQL parity, live Anthropic requests, production image/deployment validation and a
fresh-task restoration have not been run. SQLite/offline success does not establish these.

## Reusable cloud setup

Installed pinned Python requirements in `/workspace/codecoach-tools/.venv`, the frozen npm
lockfile in `frontend/node_modules`, and checksum-verified Temurin Java 21 in
`/workspace/codecoach-tools/jdk`. The complete install script was executed successfully,
including repeat installation and cached sandbox-image rebuilding. Existing tracked source,
tests, manifests and lockfiles remain unchanged.

Playwright's CDN download was denied by network policy. Used the preinstalled
`/usr/bin/chromium` through a configuration adapter outside the checkout instead. An initially
saved CDN allowlist addition was removed once the installed browser proved sufficient; no new
custom network domains or credentials are needed for the validated core workflow.

Saved `install_script` and `start_skill` in the environment configuration draft. These include
working directories, activation, SQLite/offline API + frontend startup, readiness checks,
the system-browser adapter, test commands and sequential sandbox guidance. The live dev API
passed its database readiness request and a real paginated 12-problem library request.
Draft saving does not publish the environment or validate restoration in another task.

The audit/design documents are committed locally on `feature/premium-frontend`, without a
push. Configuration captures the exact local HEAD. The environment tooling warns that Git
restoration of local-only commits is not reliably supported; fresh-task restoration remains
unverified. Keep the current checkout and review the branch before deciding to publish or
push it. No remote branch or pull request has been created.
