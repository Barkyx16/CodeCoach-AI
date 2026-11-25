# Premium frontend implementation

The design direction was approved by the user after the Phase 1 audit. Implementation lives
on `feature/premium-frontend`, based on upstream `5b9dc7a`. Backend code, runner code,
dependency declarations, lockfiles and generated API types are unchanged.

## Delivered behavior

| Area | Changes |
| --- | --- |
| Design system | Deep navy surfaces, contrast-checked blue actions, restrained red, local Inter/JetBrains Mono variable fonts with licenses, original SVG branding, matching Monaco colors |
| Navigation | Mobile disclosure menu, account access on small screens, Escape/outside-click dismissal, visible focus, route titles and focus on the new page content |
| Landing | Responsive hero, keyboard-accessible interactive product tour, real guest entry, practice loop, mock-interview introduction and footer. Tour content is explicitly an example |
| Authentication | Refined forms, shared onboarding layout, guest request errors, saved-session authentication wired before initial data queries |
| Dashboard | Compact completion indicator, practice/interview shortcuts, recent database-backed attempts, topic summary with a link to the complete breakdown |
| Analytics | Protected `/analytics` route using existing progress, recommendation and interview APIs; activity chart/table, difficulty/topic results, acceptance rate and interview history |
| Workspace | Editor controls for theme, font size, indentation and wrapping; controls work in the real Monaco editor. Settings persist locally and apply to interviews too |
| Drafts | Flush pending edits on navigation, page hide and visibility change. Keep drafts scoped by user/problem. Report storage failures rather than claiming success |
| Accessibility | Reusable ARIA tabs with arrows/Home/End, associated panels and roving focus for tour/workspace/coach/history; readable chart values, focus handling, reduced-motion behavior |
| Interviews | Prevent send/finish/abandon races, stop sending after wrap-up or message exhaustion, surface problem-load errors with retry, show loading/error/empty history states |
| Settings/history | Profile save errors, clearly identified local editor preferences, storage failure feedback, horizontally contained history tables |

The additional detail pass refines the library's challenge rows, status marks, search and
progress sidebar; adds workspace breadcrumbs, file chrome, numbered examples and result
headings; and keeps desktop workspace panels within the viewport with independent scrolling.
Settings has a real profile summary and a lightweight theme/font preview with keyboard
scrolling. Interview setup, phase indicators, transcripts, recorded timestamps and feedback
share the same visual language. Inline auth links have an underline so they do not rely on
color alone. Search input now stays synchronized when the URL changes.

## Product screenshots

These are captured from the running application. The workspace pass result, coach review,
dashboard statistics and interview feedback came from real backend operations using the
built-in coach and gVisor judge; they are not fabricated preview data.

| Landing | Coding workspace |
| --- | --- |
| [Desktop](screenshots/premium-landing.png) · [Mobile](screenshots/premium-landing-mobile.png) | [Java, real results and coach](screenshots/premium-workspace.png) |
| **Problem library** | **Dashboard and analytics** |
| [Library and recommendations](screenshots/premium-problems.png) | [Dashboard](screenshots/premium-dashboard.png) · [Analytics](screenshots/premium-analytics.png) |
| **Account** | **Interview** |
| [Settings and editor appearance](screenshots/premium-settings.png) | [Live interview](screenshots/premium-interview-live.png) · [Feedback](screenshots/premium-interview-feedback.png) |

## Engineering choices

- Keep the existing React/TypeScript, Query, Router, Monaco and CSS-token architecture.
  There are no new npm runtime dependencies or additional backend endpoints.
- Server data stays in TanStack Query. Editor preferences use a small context and local
  browser storage; code drafts remain scoped separately for privacy on shared machines.
- Authentication initialization uses a layout effect so child query subscriptions cannot
  race the saved-token setup. Logout clears the token ref immediately.
- Draft persistence keeps a pending record with its own storage key. Cleanup can safely
  save the previous user's/problem's edit without overwriting the next draft.
- Charts remain lightweight CSS/SVG. Analytics does not derive fictional daily accuracy or
  completion trends from generic activity events. Its period and event definitions are visible.
- Monaco and the interview/analytics routes remain lazy loaded. The final entry plus shared
  preload JS is about 110 KB gzip; the editor implementation stays out of the landing bundle.

## Validation

- 75 frontend unit/integration tests across 14 files pass, including regression tests for
  storage failure, early navigation, guest/profile errors, direct protected-page startup,
  editor preferences, analytics, keyboard tabs and interview closed/error states.
- ESLint, strict TypeScript, generated API drift check and production build pass.
- `npm audit --omit=dev --audit-level=moderate` reports zero known production vulnerabilities.
- Seven real-backend Playwright journeys cover guest practice, account creation/login/profile
  and deletion, mobile navigation, workspace keyboard tabs, five-phase interviews, Monaco
  settings/drafts/protected-page refresh/analytics, and real sandbox Java judging.
- Real judging checks both incorrect and correct submissions, public/hidden results, and
  database-backed dashboard solved counts. All browser tests can run together with
  `CI=true E2E_JUDGE=1` using the system Chromium adapter described below.
- Automated axe-core WCAG 2 A/AA and 2.1 AA scans found no reported violations in 21 sampled
  views: eight product pages on desktop/mobile, login/register on both, and the light editor
  preview at 20 px. No overflow was found in those views. A separate 42-view check covers
  320/375/768/1024/1280/1440 px layouts and desktop workspace height, also without overflow.
  No uncaught browser errors were observed in the product capture or main page sample.
  These checks supplement keyboard tests; they are not a full accessibility certification.
  *After merge (session 4):* these scans are now automated in `e2e/a11y.spec.ts` and run in CI.
  Scanning the mobile header found one issue the sample missed: the menu button showed "Menu"
  but was named "Open navigation" (WCAG 2.5.3). Fixed; the 404 page also gained an `<h1>`.
- The initial audit already ran all 232 backend tests successfully. No backend or runner
  source changed in this implementation, so those unrelated suites were not repeated.
- One pre-existing runner assertion still expects `gvisor` in the reported kernel version;
  this installed `runsc release-20260413.0` reports `4.4.0`. Its serial audit result remains
  15 threat tests passed, one failed; see FRONTEND_AUDIT.md. Isolation was not weakened.
  *Resolved after merge (session 4):* the test now asserts the sandbox kernel is not the host
  kernel, which holds for every gVisor release and fails under plain runc (checked both ways).

Intermediate failures were investigated: select controls needed separate labels for exact
accessible names; the History browser selector needed scoping after adding a second history
link; an interview fixture needed a handler; reused development servers hit the auth rate
limit. The final browser run uses fresh test servers, retaining all behavior assertions.

## Development environment

The cloud configuration draft contains the tested install and startup instructions. Dependencies
live in `/workspace/codecoach-tools/.venv` and `frontend/node_modules`; the local verified JDK
is `/workspace/codecoach-tools/jdk/jdk-21.0.9+10`. `/usr/bin/chromium` is supplied by the base
environment. The adapter at `/workspace/codecoach-tools/playwright.config.ts` retains repository
tests/projects while choosing that browser and external artifact paths.

For the prepared interactive stack, run:

```sh
/workspace/codecoach-tools/.venv/bin/python /workspace/codecoach-tools/dev.py
```

The launcher starts the runner, SQLite API/embedded worker and frontend, checking readiness.
It requires Docker's gVisor runtime and the sandbox image. An internal runner token is generated
in memory and never written into application source or logs. This is local development with
the real built-in offline coach, not a production deployment or a live Claude validation.
The cloud install script recreates the helper; the helper itself lives outside the checkout.

Stop only development services you started before running browser tests with `CI=true`, so
the tests cannot reuse a service with different execution or rate-limit settings. Run sandbox
suites sequentially because runner startup cleans shared sandbox container labels.

## Remaining scope

- A separate Run Code/public-cases-only action requires a backend contract. Submit performs
  real judging when the deployment has execution enabled; disabled deployments remain honest.
- Streaming AI, cross-device preference synchronization, long-term daily accuracy series,
  production deployment and refresh cookies are separate backend/deployment work.
- Live Anthropic and PostgreSQL parity were not revalidated here. No external AI key is exposed
  to the browser or needed for the built-in coach.
- GitHub API requests are denied by the cloud network proxy. `api.github.com` has been added
  to the environment draft for review; saving a draft does not apply/publish the change or
  establish GitHub API permissions. A draft pull request cannot yet be created through `gh`.

Review the prepared branch and cloud settings before publication. Publication and restoration
in a new task remain unverified.
