# CodeCoach AI

**Interview practice for 110 careers, plus an AI-assisted Java coding platform with a deterministic judge.**
People pick the job they want (nurse, accountant, electrician, software engineer and 100+ more)
and practice 300 interview questions written for that job, with rubric feedback on every answer.
Software engineers also solve curated data-structures-and-algorithms problems in a browser editor,
get progressive AI hints and structured code reviews, and track their progress. Code correctness
always comes from test cases, never from the AI.

> **Status: Phases 1–4 of 5 complete.** The full product works end to end: React app →
> FastAPI → PostgreSQL, an AI coach, timed mock interviews, and **real judging of submitted
> Java in an isolated gVisor sandbox**, verified by unit, integration, threat-model and
> real-browser tests in CI.

| Workspace | Mock interview |
|---|---|
| ![Workspace with AI code review](docs/screenshots/premium-workspace.png) | ![Live mock interview](docs/screenshots/premium-interview-live.png) |
| **Interview feedback** | **Dashboard** |
| ![Rubric feedback](docs/screenshots/premium-interview-feedback.png) | ![Progress dashboard](docs/screenshots/premium-dashboard.png) |
| **Sign in** | **Reset password** |
| ![Sign in](docs/screenshots/11-login.png) | ![Reset password](docs/screenshots/14-reset-password.png) |
| **Settings** | **Settings on a phone** |
| ![Settings grouped into sections](docs/screenshots/18-settings-redesign.png) | ![Settings on a phone](docs/screenshots/19-settings-mobile.png) |
| **Judged in the gVisor sandbox** | **Explain my failure** |
| ![Submission passed](docs/screenshots/08-judged-pass.png) | ![Failure explanation](docs/screenshots/10-explain-failure.png) |

## What works today

| Feature | Details |
|---|---|
| Interview practice for 110 careers | Pick your job at sign-up (changeable in Settings): 110 careers across 12 industries. Each gets **300 questions** (100 easy, 100 medium, 100 hard): fundamentals, behavioral (STAR), scenarios, leadership and motivation, generated from a hand-written profile of that job (its skills, tools, real situations, people and metrics). Write an answer and get feedback: a score, which rubric points you covered, what to add, delivery notes (length, "I" vs "we", numbers) and an outline of a strong answer. Answers and best scores are saved; keyword search; Easy/Medium/Hard tabs |
| Problem library | **300 Java problems: 100 easy, 100 medium, 100 hard** across 26 topics (strings, arrays, dynamic programming, math, matrices, hash maps, greedy, graphs, two pointers, sorting, binary search, stacks, heaps, sliding window, backtracking, bit manipulation, union-find, topological sort and more); 2,391 test cases (1,492 hidden); every problem has a 4-level hint ladder and expected complexity; Easy/Medium/Hard tabs showing 5 at a time with "View more"; keyword search that understands plain descriptions ("reverse words", "dp", "stack brackets") |
| Verified test data | Every problem ships with a trusted reference solution, and CI compiles and runs all of them against every test case and checks that each problem's starter code fails. Expected outputs come from two independent implementations (a deliberately simple, often brute-force Python model and the optimal Java reference) that must agree on every hand-picked and seeded random case; the 278 generated problems are defined in `backend/scripts/problembank/` and rebuilt deterministically |
| Accounts | Register and login (Argon2id), guest demo sessions, **15-minute in-memory access tokens with a rotating `HttpOnly` `SameSite=Strict` refresh cookie** (reuse detection revokes stolen sessions; nothing in `localStorage`), logout-everywhere, **email verification with a 6-digit code** (or link), **change email**, sign out of this device or **all devices**, show/hide password and a live password checklist, **forgot-password by email** (pluggable console/file/SMTP sender; no account enumeration), **guest-to-account upgrade that keeps all progress**, automatic deletion of inactive guest accounts, rate limits **shared across API replicas**, password change, brute-force limiting; settings page with profile edit, **full data export** and **account deletion** (cascading, verified on SQLite and PostgreSQL) |
| AI hints | 4-level progressive ladder (nudge → concept → pseudocode → explanation), unlock order enforced by the server |
| AI code review | Structured JSON: complexity, issues with severity, category and line, strengths, next step, confidence |
| Explain my failure | One click on a failed verdict: the root cause (13 categories), a plain-English explanation, the evidence it relied on (failing public test, exception line or compiler message), a link to the line, and next steps. Built only from public test data; cached per submission. Verified with 9 buggy programs in the real sandbox |
| AI providers | `offline` (curated hints + static analysis; free, deterministic) or `anthropic` (Claude via structured outputs) with automatic fallback |
| AI safeguards | Prompt-injection framing, secret redaction, per-user daily budget, input caps, saved history; hidden tests never reach the model |
| AI evaluation | A versioned harness with release gates in CI: 66 hand-labelled Java samples (labels verified by the real judge) for review precision/recall, false alarms, Big-O and hint spoilers; 40 labelled career answers (registered nurse, development and held-out) for evidence, too-short answers, injected instructions and stability; every request to Claude checked without calling it (untrusted framing, hint ladder, hidden tests, secrets); ten provider failure kinds through the real fallback; reports with commit, dataset hashes and prompt version ([results](docs/AI_EVALUATION.md)) |
| Code judging | **Run** checks the public tests in seconds without recording an attempt; **Submit** judges against public and hidden tests. Both execute in a **gVisor sandbox** (separate runner service: no network, read-only FS, CPU/memory/PID/time/output limits, non-root, no bind mounts). Postgres-backed job queue with a worker, admission control, bounded retries and crash recovery. 16 threat-model checks run hostile code in the real sandbox in CI. Availability is reported truthfully from an authenticated runner probe: **Ready**, **Temporarily unavailable** (Run paused, Submit queues) or **Not configured** (the button says "Save attempt" and offers a code review); submissions are idempotent, polling is bounded, a reload resumes a submission still being judged, and `python -m app.cli judge-check` proves a configured judge works. From a Mac the judge runs on a Linux host reached over an SSH tunnel or HTTPS ([docs/REMOTE_JUDGE.md](docs/REMOTE_JUDGE.md)) |
| Mock interviews | **Career question rounds** for every job: five of that career's questions in interview order, saved on the server (reload-safe, real deadline, one interview at a time), each scored as you go, then results that show completed, skipped and not-reached questions honestly. Coding careers also get timed sessions through clarify → approach → code → complexity → test with an AI interviewer (offline or Claude), rubric feedback on 5 dimensions and saved transcripts |
| Interview formats | Mixed (the original round), Behavioral, Situational, Technical / professional and a **simulated panel**, each offered only when the career's bank can fill it at the chosen level (otherwise it says why, e.g. "no Easy scenarios"; careers without a reviewed panel say so rather than getting generic questions). A preview shows who asks what before you start. Panels (Software Engineer, Registered Nurse) have three generic roles with their own focus; one speaks at a time and is named in text, not only by voice or color. Up to two follow-ups per round are chosen from what an answer left out, never repeating a detail already given, from the role that asked; reply by voice or typing, or skip. The server validates every turn, reloads resume mid-follow-up, and reviews show the speaker, the follow-up and per-role perspectives labelled as simulated ([docs/INTERVIEW_FORMATS.md](docs/INTERVIEW_FORMATS.md)) |
| Interview review | Every finished interview opens a review: real duration, honest status (ended early and time-ran-out sessions say what's missing), one to three "work on next" points whose evidence opens the exact answer, transcript turn or code line, assessment dimensions kept apart (content, structure, reasoning not judged, spoken delivery not measured, code execution not run), and a selectable transcript with recorded times (no fake audio: audio is never kept). Retry any single question: the original answer stays as it was, the retry is graded separately, and the comparison shows what improved, what still needs work and what slipped, comparing scores only when the evaluator and rubric version match. Save questions to a spaced review queue (1, 3, 7, 14, 30 days, advanced only by answering again; snooze or remove; nothing is emailed or pushed) |
| Voice interview studio | Optional voice in both kinds of interview: a readiness screen (microphone permission only on request, a live input-level test, interviewer voice, speed, volume, captions, and what's recorded or sent), push-to-talk with explicit states (ready, listening, processing, interviewer speaking, blocked, error), interim words shown apart from the editable draft, no submitting while the microphone is on, no transcribing the interviewer, drafts kept through errors and reloads, and typing always available. Speech-to-text is the browser's own; CodeCoach never receives or stores audio |
| Simulated interviewer engagement | After each answer: "Following your answer", "Looking for more detail", "Ready to explore further" or "Not enough evidence yet", with a one-sentence reason that refers to the answer (e.g. "you described the situation, but not clearly what you personally did") and the evidence behind it. Deterministic and text-only: never voice, accent or typing vs speaking, never "likes you" or hiring predictions. Hideable during the interview, reviewable after |
| Dashboard | Opens after sign-in. Coding careers see solved problems, streaks and recommendations; other careers see a dashboard built from their own questions: answered and strong answers, progress by difficulty, and what to answer next |
| Question explorer and collections | Search a career's questions by title, skill, tag or wording (exact titles first); filter by difficulty, format, skill and, when signed in, answered / not answered / bookmarked, with counts on every option that already account for the other filters; sort by best match, library order, recently practised or lowest score (nothing claims to be "personalized"). Removable filter chips and a one-line explanation of what's applied; empty results suggest how to widen. Everything lives in the URL, so Back, Forward, reload and shared links show the same list, and returning from a question restores the scroll position even after a reload. Bookmarks update instantly and roll back with a "Try again" if saving fails. Private collections (create, rename, reorder with keyboard-friendly buttons, delete after confirming) hold questions and coding problems, one item in many collections but never twice in one; "Start this collection" practices it as a queue whose "done" marks are kept apart from scores. Retired items stay visible as unavailable with a Remove button, never silently replaced |
| Learn mode | Short, versioned lessons that teach before testing, deliberately scoped: 3 for Software Engineer (hash maps, sliding windows, explaining debugging) and 3 for Registered Nurse (STAR, SBAR, prioritizing), each with an objective, prerequisites, explanation, a worked example (accessible code blocks), common mistakes, a guided exercise (help revealed one step at a time, or a solution only after a spoiler warning, never overwriting your draft), a server-graded comprehension check and a link to real practice. Sources are listed with review status and no guessed links; nursing units state their scope and jurisdiction. Progress records started, read, check attempted, check passed and practised separately per version; the practice plan can schedule a lesson before a retry and counts it only when the check is passed. Reading never solves a problem or validates a skill. Authoring rules in [docs/LEARN_CONTENT.md](docs/LEARN_CONTENT.md) |
| Notebook | Private notes captured where you practise (question, coding problem, lesson or interview review) that keep the source's stable id, version and title, plus an optional snapshot of the question, your answer or your code, labelled as a copy. Title, safely rendered Markdown (no HTML, no images, no unsafe links), tags and a private reflection. Autosave with honest Saving / Saved / Could not save states, a retry, a recoverable copy in this browser after a failed save, saving on navigation, and edit conflicts across tabs or devices shown side by side (keep mine, use the saved version, or keep both) instead of overwriting newer text. Search, filters for career, source and tag, up to 5 pinned notes, archive, and delete with a 10-minute undo. A non-AI "key points" helper suggests your own action sentences and saves nothing until you accept |
| Branching scenarios | Fictional, career-specific situations where your choices change what happens next: an on-call incident for Software Engineers and a two-patient prioritization case for Registered Nurses (stated as the whole set). A briefing gives the role, goal, time estimate and scope; information is revealed step by step; choices are final for the attempt and written responses are checked against the scenario's own points. The server keeps your place and decides every transition from the validated graph (no client can pick an ending; repeated requests are harmless), so you can reload and resume. The debrief shows your path, each decision with its authored rule and the alternatives, strengths, references and a clear "simulated, not a prediction" note; "Try another approach" starts a separate attempt and keeps the original. Authoring format and validation in [docs/SCENARIOS.md](docs/SCENARIOS.md) |
| Practice plan | Optional goals per career (specialty, experience, interview date, weekly time, focus areas, written/voice/coding, self-rated confidence) or skip straight to a starter plan. A 3-question baseline round, then a plan of concrete activities (answer a question, review feedback, retry a weak answer, answer out loud, a mock interview, a coding problem), each with why it was chosen, the skill, minutes and what counts as done. "Today" picks one next action and an optional follow-up for 5, 15 or 30 minutes. Completion comes only from recorded work (reviewing feedback is the one self-reported step, and says so); skipping or swapping never counts as done; new versions list exactly what changed and why. Self-ratings, rubric scores and judged code are shown separately, never as one "readiness" number. Each career has its own plan, so switching careers keeps the old one |
| Prepare for this role | Save target roles from a pasted job description (several at once; one active; archive old ones). Requirements are found by rules, not AI: required and preferred skills, responsibilities, years of experience, tools and competencies, each with the line of the posting it came from, plus clearly labelled suggestions from the career profile. Correct, remove, restore or add requirements. Each one shows its practice coverage from your real answers and judged code, the questions (and, for coding careers, problems) that practise it, and honest gaps, e.g. "a qualification; practice questions can't cover it". A short targeted session and a role mock interview state their scope first and use only your career's questions. Add your own examples (situation, what you did, result) linked to requirements. Editing the posting keeps every requirement and attempt; removed lines are flagged. The pasted text is only ever treated as data |
| History | One timeline for every career: problems opened, code submissions, coaching, written answers and interviews, each with its career, skills and an honest status ("Saved, not judged" when the Linux judge isn't available; written answers are "scored", never "correct"). Filters for career, activity, status, skill or topic, date range and title search live in the URL, and Back (in-app or the browser's) returns to the same filters, page and scroll position. Every row opens its question, answer, submission, feedback or interview |
| Analytics | Per career, never mixed: coding (solved, judged acceptance, topics, interviews) or a career's questions (questions practised, skills covered out of every skill the career's questions practise, completed vs ended-early interviews, weekly answers, and a score trend kept separate per evaluator and rubric version), with date ranges, metric definitions, exact-value tables and "not practised yet" instead of zeros. Older careers can be inspected without changing your setting. "Continue where you left off" on the dashboard resumes real saved work: a running interview (with its real remaining time), an unsent answer, a coding draft or an unsolved problem |
| Recommendations | Explainable next problems: retry unfinished, strengthen weak topics, difficulty ladder |
| Feedback from a person | Share one graded answer with a mentor or practice partner through a private link: tick which sentences to include, optionally the follow-up and the (labelled) automated feedback, add a note, and see the exact reviewer view before making the link. The link's secret lives in the URL fragment (never sent to servers or in Referer headers) and only its hash is stored; links expire (1/7/30 days), can be closed, replaced or turned off at once, and responses are no-store and noindex. Reviewers, signed in or guests (names shown as unverified), answer three prompts and comment on specific sentences; feedback is plain text, stored once per retry, kept apart from AI scores and never changes them. No emails or notifications. In export and deletion ([docs/SHARING.md](docs/SHARING.md)) |
| Installable & offline | Installable where the browser supports it (manifest, real icons, an install button only when offered, honest platform notes). A small service worker caches only the public app shell and this build's files, never API responses (tested). **Save for offline** keeps public lessons, questions and coding problems on the device with dates, versions, sizes and removal; retired items are dropped when back online. Offline, drafts stay on the device and say so ("not sent yet"), feedback/judging/interviews pause with the reason, note edits sync once on reconnect with conflict choice, nothing is replayed automatically, and being offline never signs anyone out. Updates wait for the learner and keep drafts; sign-out deletes the account's drafts from the device after a warning ([docs/OFFLINE.md](docs/OFFLINE.md)) |
| Trustworthy question bank | Every question and coding problem says what it is: career, topic, level, version and labels built only from recorded facts ("Generated…", "Not reviewed by a subject-matter expert", "Reference solution passed all N tests" only when a passing check is recorded for the current tests). **Report an issue** on any question, problem or piece of feedback sends the content id and the version on screen, plus only an excerpt the learner chose; reports are rate-limited, grouped as likely duplicates and shown as plain text, and **Your reports** shows their outcome. Admins (granted only from the command line; every admin route is a 404 to anyone else) triage with an append-only audit trail, publish corrections as new versions (old answers keep their version and score, and learners who answered see what changed) and retire content (no longer used for practice, still readable in history and saved items). `validate-content` gates CI. No expert review is claimed ([docs/CONTENT_QUALITY.md](docs/CONTENT_QUALITY.md)) |
| First session & Help | After sign-up or a guest demo, an optional welcome offers one real, easy item from the learner's own job (a nurse is never introduced through Java), a 5-step tour of that same page, or the library, and says honestly what feedback it will get. The tour is docked, never covers a control, highlights real elements, survives reloads, can be left with Esc and resumed or replayed, and never counts as practice. A career change offers that job's format introduction once. Help answers the core questions (practice, drafts, feedback, voice, history, data) with links to real pages and no promised support channel. Only the learner's choices about the introduction are stored; no answer text ([docs/ONBOARDING.md](docs/ONBOARDING.md)) |
| Story bank | Write real experiences once as Situation, Task, Action, Result and an optional reflection, tagged with competencies; the examples written in a job target are the same stories (one copy, linked by id). Server-side private search, missing sections pointed out without judgment, privacy hints for names or ID numbers, every save kept as a version with conflict-safe saving and restore, unsaved edits recovered after a reload. A built-in writing check (rules, never AI; nothing leaves the server) asks questions and proposes removals side by side, never adding a word or a number. Practise a story on any question: the answer is its own graded record that points at the story, which is never changed ([docs/STORIES.md](docs/STORIES.md)) |
| Application tracker | A private board and sortable list of real applications as the learner records them (saved, applied, interviewing, offer, closed, withdrawn): drag a card or use its keyboard "Move to" menu, append-only stage history with corrections that never rewrites old titles, next actions due in the learner's own time zone, and separate interview events whose times are exact and safe around daylight saving (impossible times refused, repeated ones asked about). Links to a job target and stories, "Prepare for this stage" actions, and thank-you/follow-up drafts from typed facts that can be copied or downloaded and are never sent ([docs/APPLICATIONS.md](docs/APPLICATIONS.md)) |
| Schedule & calendar files | Put existing plan steps, reviews, questions, problems and interview preparation on dates and times you choose, shown in your schedule's IANA time zone (travelling keeps timed entries at the same moment and all-day ones on their date; impossible or repeated daylight-saving times are refused or asked about). An entry is never mistaken for done work, overlaps are explained and never moved, and `.ics` files (stable UID, SEQUENCE, cancellations, escaped and folded, tested) export only what you pick. Reminders are opt-in, respect quiet hours and appear only inside an open tab: nothing is ever sent ([docs/SCHEDULE.md](docs/SCHEDULE.md)) |
| Interview-day kit | For each recorded interview: logistics (format, location, a meeting link that's never fetched, interviewers as you know them), a format-aware checklist where suggestions are labelled and a tick means you ticked it (nothing is "verified"), questions to ask built from your own job target and flagged when the posting may already answer them, the stories to bring, a calm "Before the interview" view, and a print/PDF pack whose preview is exactly what prints, with private details off until chosen ([docs/INTERVIEW_KIT.md](docs/INTERVIEW_KIT.md)) |
| Interview reflections | After a real interview, a private and entirely optional debrief: questions (paraphrased), topics, what felt clear or hard, observations kept apart from interpretations, follow-up commitments and what to practise; guidance on confidentiality; suggested next steps built only from what you wrote and from content that exists (gaps are shown as gaps), each added to your notebook, schedule or Saved only when you choose, never twice; outcomes that move the application only when you ask; private search; readable after archiving ([docs/REFLECTIONS.md](docs/REFLECTIONS.md)) |
| Restore from a backup | Bring your notes, stories, bookmarks and applications back from a CodeCoach backup into the signed-in account: the file is checked and previewed first (new, already here, skipped and why, and what's never restored), you choose what to add, the batch is one transaction, the same file twice adds nothing, ids/roles/results in the file are never trusted, and a restore can be removed later without touching anything you've edited since ([docs/BACKUP_FORMAT.md](docs/BACKUP_FORMAT.md)) |
| Whiteboard practice | System-design prompts for careers that write code (process maps for other careers aren't offered until reviewed content exists): a small, plain-text diagram you can build entirely from a keyboard outline or by dragging, with groups, notes for assumptions, capacity and tradeoffs, undo/redo, zoom, a text equivalent, conflict-safe drafts with recovery on this device, strict JSON import/export, and feedback (only after you explain a decision) that names the components and connections it found and never judges looks or certifies a design ([docs/WHITEBOARD.md](docs/WHITEBOARD.md)) |
| Communication drills | Five short drills (a brief introduction, a concrete example, explaining to a non-specialist, a clarifying question, a follow-up) with prompts from your own career, typed or spoken with an editable transcript; feedback describes what's in your words, measures only what was measured (spoken time only from a timed recording, estimates labelled), never marks down filler sounds, pauses or typing, compares repeats under the same rubric, and can hide delivery measurements; drills can be bookmarked, collected and scheduled ([docs/DRILLS.md](docs/DRILLS.md)) |
| How answers are evaluated | Each question shows its criteria before you answer (qualitative points and fixed checks, labelled apart, without the matching rules); an optional reflection can hold the feedback until you've noted your own view (skipping costs nothing); found points quote your own sentence, a too-short answer shows "not enough to score" instead of a number; your ratings sit beside the coach's as "different perspectives"; private flags on a criterion; and checking again only when the rubric or question changed, recorded beside the original ([docs/RUBRIC_TRANSPARENCY.md](docs/RUBRIC_TRANSPARENCY.md)) |
| Accessibility & reading | **Display & reading** settings kept in the browser: Match device / Light / Dark, a higher-contrast option with its own verified colours (172 computed contrast checks: 4.5:1 standard, 7:1 higher contrast), three text sizes (all sizes in `rem`; the code editor keeps its own), a spacious reading layout and reduced motion, applied before first paint, validated, with a reset and an honest "won't be kept" when storage is blocked. **Focus mode** on question, interview and coding pages hides navigation and extras but never the question, answer, timer, recording status, errors, help or the way out; Esc exits and focus returns. An audit fixed keyboard focus lost after every busy button, a code editor you couldn't Tab out of (now Ctrl+M, shown on screen), screen-reader announcements on every keystroke, focus lost after removals, unlinked errors, wrong page titles and overflow at 320px with large text. Checked with keyboard-only browser journeys, axe in four themes and reflow at 320px; no screen reader was available, which [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md) says along with the other limits |
| Web app | React + TypeScript: landing, auth, problem library (URL-synced filters), resizable 3-panel workspace with Monaco and autosaved drafts, hint ladder, reviews that highlight the flagged line, dashboard (stat tiles, activity heatmap, topic progress), history; mobile layout |
| Engineering | 2,223 backend tests (SQLite **and** PostgreSQL, incl. 384 that run in the real gVisor sandbox), 36 runner tests, 523 frontend tests, 78 Playwright end-to-end tests against the real backend (desktop, phone and the production build with its service worker; the judge journeys run against the real gVisor judge in CI's sandbox job, and an opt-in audit uses every control on every page), a `validate-content` gate over the whole question and problem bank (incl. automated **axe-core WCAG 2.1 AA** scans of every main screen on desktop and mobile); ruff, mypy, ESLint, strict TypeScript; API types generated from OpenAPI; Alembic; Docker Compose (db, migrate, api, web + judge profile: sandbox image, runner, worker); GitHub Actions; pip-audit, npm audit, Dependabot; Prometheus metrics, JSON logs, request IDs, health checks, **W3C trace context from the browser through the API, evaluation and the judge worker, with SLI recording rules, alerts and an admin trace lookup**; CSP and security headers |

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

**Without Docker, one command** (macOS or Linux; needs Python 3.12+ and Node 22.12+ (or 20.19+), on a Mac
`brew install python@3.13 node`):
```bash
./dev.sh
```
It installs what it needs on the first run, starts the API (<http://localhost:8000>) and the site
(<http://localhost:5173>) together and opens the site; `Ctrl+C` stops both. If a tool is missing it
says which one and how to get it. It builds the site first and serves that build, which works in
any browser the app supports; after changing the code, run it again. `./dev.sh --live` serves the
code as you edit it instead, reloading the page on each change and printing the browser's errors
in the terminal. If the page can't start (a content blocker, say), it says so and what to try.

**Without Docker, by hand** (two terminals):
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
python -m scripts.problembank.build       # regenerate the 278 bank problems after editing scripts/problembank/
pip-audit -r requirements.txt             # known-vulnerability scan
```
```bash
cd frontend
npm run lint && npm run typecheck         # ESLint + strict TypeScript
npm run api:check                         # generated API types match docs/openapi.json
npm test                                  # unit + integration tests (Vitest: the app with MSW, plus tooling tests)
npm run build                             # production bundle
PYTHON=../backend/.venv/bin/python npm run e2e   # Playwright: real browser + real backend
AUDIT=1 E2E_JUDGE=1 npm run e2e -- e2e/controls-audit.spec.ts --project=desktop   # ~30 min: uses every control on every page
```
How the e2e servers are owned (`scripts/e2e-run.mjs`, `e2e/global-setup.ts`):
- **Only its own server.** A run refuses an API that isn't this suite's test server. That
  means no `X-CodeCoach-Instance: e2e` header (a developer's server, with real data), or a
  judge setting that doesn't match `E2E_JUDGE` (e.g. an orphan from a run without the judge).
  It says why in seconds and never stops that server: that's for whoever started it.
- **Stops what it started**, and nothing else. Each server records its process group. On
  success, failure, Ctrl+C, SIGTERM or `--max-minutes N`, the run stops exactly those groups,
  never by name or port. A server whose launcher was killed outright stops itself within about
  a second.
- `npm run e2e:owned` lists recorded runs and their servers. `npm run e2e:stop -- <run id>`
  stops a run whose launcher is gone. It refuses a run that's still going.
- **Two runs at once:** `E2E_PORT_OFFSET=10 npm run e2e`. That gives other ports (API 8010,
  runner 8110, web 5183, preview 4183) and its own database and outbox.
- The exit status is Playwright's: 124 for the time limit, 130 for Ctrl+C. An interrupted or
  timed-out run is reported as incomplete, never as passed.
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
| [docs/LEARN_CONTENT.md](docs/LEARN_CONTENT.md) | How Learn units are written, referenced, reviewed and versioned |
| [docs/SCENARIOS.md](docs/SCENARIOS.md) | The branching-scenario format, graph validation and review rules |
| [docs/REMOTE_JUDGE.md](docs/REMOTE_JUDGE.md) | Running code from a Mac: connecting a remote Linux judge safely, states, checks |
| [docs/INTERVIEW_FORMATS.md](docs/INTERVIEW_FORMATS.md) | Interview formats, simulated panels, follow-up rules and how to add a panel |
| [docs/INTERVIEW_KIT.md](docs/INTERVIEW_KIT.md) | The interview-day kit: suggestions and what they're based on, the checklist, questions to ask and the printable pack |
| [docs/REFLECTIONS.md](docs/REFLECTIONS.md) | Reflecting on a real interview: what to write and what to leave out, how next steps are suggested and applied, outcomes and privacy |
| [docs/BACKUP_FORMAT.md](docs/BACKUP_FORMAT.md) | The backup format (version 1), what restore reads and never reads, how a restore runs and how to undo one |
| [docs/WHITEBOARD.md](docs/WHITEBOARD.md) | Whiteboard practice: the diagram format and its limits, keyboard use, saving and recovery, how feedback is built and what it doesn't claim |
| [docs/DRILLS.md](docs/DRILLS.md) | Communication drills: the five drills, typing and speaking, what's measured and what's an estimate, comparisons and limits |
| [docs/RUBRIC_TRANSPARENCY.md](docs/RUBRIC_TRANSPARENCY.md) | How written answers are evaluated: criteria up front, the optional reflection, quoted evidence, insufficient evidence, perspectives, flags and re-evaluation |
| [docs/SCHEDULE.md](docs/SCHEDULE.md) | Scheduling, time zones and daylight saving, calendar files and what reminders can (and can't) do |
| [docs/APPLICATIONS.md](docs/APPLICATIONS.md) | The application tracker: stages and history, board and list, interview times and daylight saving, drafts that are never sent |
| [docs/STORIES.md](docs/STORIES.md) | The story bank: the shared model with job targets, versions, the rule-based writing check, practice and privacy |
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | The optional welcome, the guided tour, Help, and exactly what's recorded about them |
| [docs/CONTENT_QUALITY.md](docs/CONTENT_QUALITY.md) | Content labels and what they're based on, reporting, admin triage, corrections as versions, retirement, the `validate-content` gate and the review process |
| [docs/OFFLINE.md](docs/OFFLINE.md) | What works offline, the service worker and its caches, updates, install, what's stored on the device and when it's cleared |
| [docs/SHARING.md](docs/SHARING.md) | Sharing an answer for feedback: link security, what's shared, retention after revoking, export and deletion |
| [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md) | Display preferences, focus mode, what the accessibility audit fixed, how it's checked and what wasn't |
| [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) | One answer traced from the click through the API, evaluation, database and judge: spans, SLIs, alerts, privacy checklist, runbooks, incidents, measured overhead |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Measured API latency/throughput and judge throughput, with the exact setup |
| [docs/AI_EVALUATION.md](docs/AI_EVALUATION.md) | How the AI coach is measured: datasets and provenance, reproducible runs, release gates, results (rubric v1 → v2), limitations |
| [docs/EVAL_PROTOCOL.md](docs/EVAL_PROTOCOL.md) | The frozen evaluation protocol: set roles and exposure, sealed final set, duplicate checks, metrics with intervals, release rule, label review |
| [docs/SECURITY.md](docs/SECURITY.md) | Implemented controls, AI safeguards, sandbox threat model and design |
| [docs/LAUNCH_READINESS.md](docs/LAUNCH_READINESS.md) | Launch readiness: what each step changed, the defects found, how far each is verified, what's still needed |
| [docs/LAUNCH.md](docs/LAUNCH.md) | The `preflight` command (ready / blocked / optional / unverified), the production-shaped rehearsal, the runbook |
| [docs/EMAIL.md](docs/EMAIL.md) | Sending email for real: SMTP with verified TLS, delivery stages, verification, changing the address, diagnosing problems |
| [docs/VERIFICATION_JOURNEY.md](docs/VERIFICATION_JOURNEY.md) | What the learner sees while confirming an email: masked address, honest delivery states, resend, links that don't work, other tabs |
| [docs/INTERVIEW_CONTINUITY.md](docs/INTERVIEW_CONTINUITY.md) | One interview across tabs and devices: who wins a race, what the other tab is told, the limits |
| [docs/NAVIGATION.md](docs/NAVIGATION.md) | Back, deep links and direct entry: what returns where, what survives a reload or a copied link |
| [docs/RECOVERY.md](docs/RECOVERY.md) | When an action fails: the message and the way on, the server's waits, how a write whose answer was lost is reconciled, and what can't yet be retried safely |
| [docs/STORAGE.md](docs/STORAGE.md) | Where data lives in each setup, what survives what, the production database layout and roles |
| [docs/PERSISTENCE.md](docs/PERSISTENCE.md) | Feature by feature: the saved record, browser-only drafts, what "Saved" means, conflicts |
| [docs/ROW_LEVEL_SECURITY.md](docs/ROW_LEVEL_SECURITY.md) | Database-enforced isolation at runtime: roles, scopes, pooled connections, background work |
| [docs/BACKUP.md](docs/BACKUP.md) | Encrypted server backups, isolated restores, recovery targets vs measured |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Where personal data goes, how long it stays, and what deletion does and can't reach |
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

On one 4-vCPU machine (API, PostgreSQL and the load generator together; details in
[docs/PERFORMANCE.md](docs/PERFORMANCE.md)):
- **Learner journeys (2026-11-03):** search, dashboard, history and answering over a synthetic
  15,760-answer dataset: p95 **129 ms at 8 clients** (446 ms before two query optimizations,
  same workload), 134 req/s, no errors; overload at 64 clients stays bounded with no errors.
- **Problem-browsing mix (2026-11-01, older endpoint mix):** p50 9 ms / p95 18 ms with one client;
  ~254 req/s at p95 86 ms with 10 concurrent clients.
- **Judge:** ~4 s from submit to verdict for a single submission in a fresh gVisor sandbox;
  15.5 submissions/min with one worker, **29.3/min with two** (1.9×) with no double-judging.

## Known limitations

Listed honestly in [docs/SECURITY.md §5](docs/SECURITY.md#5-known-gaps-honest-list). No AI
accuracy or performance numbers are claimed until they've been measured. Sandbox residual
risks are listed in [SECURITY.md §4.3](docs/SECURITY.md#43-residual-risks-honest).
