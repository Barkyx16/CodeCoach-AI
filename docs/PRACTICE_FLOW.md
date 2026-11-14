# Practice flow upgrades (Functional Upgrades: Practice Flow, FU01–FU10)

Extends the existing plan (`backend/app/services/roadmap.py`), Today card, schedule and review queue.
No new tables, columns, migrations or endpoints; the API schema (`docs/openapi.json`) is unchanged.
The dashboard design work (purple theme, top bar, Today layout from `DASHBOARD_REDESIGN.md`) is kept:
new pieces reuse `ActivityCard`, `MoreOptions`, `Button`, `Icon` and live in `src/styles/dashboard.css`.

## Brief states

| Brief | State | What the evidence is |
|---|---|---|
| FU01 Map the flow | Done | Mapped below ("How the flow works now") from the code, not the docs. |
| FU02 Use remaining time | Implemented (client) | Today offers one more pending plan activity that fits what's left, only on request. |
| FU03 Plan context through activities | Implemented (client) | The activity page says it's from the plan and, once the server counts it, names the next step. |
| FU04 Completion linked to exact evidence | Implemented (server) | One answer or round completes at most one activity; too-short answers aren't quoted as scores. |
| FU05 Swap by fit | Implemented (server) + already satisfied | Coding swaps never exceed the slot; question swaps already kept skill and level and avoided repeats. |
| FU06 Schedule reliably | Partial | An already-scheduled activity shows its date and links to the entry instead of offering another. No server uniqueness for (kind, ref). |
| FU07 Ended-early interviews | Implemented (client) | Dashboard note for a recent round that ended early or ran out of time, linking to its existing review. |
| FU08 Due review in the plan | Partial | When nothing else fits the time left, Today links to due reviews. The review queue stays its own engine. |
| FU09 Weekly effort | Implemented | Relabelled as a rolling 7 days of estimates; de-duplicated through FU04; window tested. |
| FU10 Journey and handoff | Done | This document; checks below. |

## How the flow works now

- **Today** (`GET /me/plan?minutes=`): the server picks the first pending activity that fits the
  minutes chosen (5, 15 or 30) and a follow-up that fits the rest. The minutes are a budget, not a
  target. The session estimate is what the plan holds.
- **Completion** is reconciled lazily on `GET /me/plan` (`Roadmap._sync`) from evidence recorded
  after the activity was planned: a saved answer (question/retry), a voice turn (voice), a finished
  round (mock/assessment), a lesson event (learn). Completing an activity starts a new plan version
  with new item ids, and the change list says `Done: “title” (label).`
- **Swap** (`POST /me/plan/items/{id}/replace`) keeps skill and level, avoids anything skipped or
  swapped in the last 7 days, and returns 409 `no_alternative` when nothing is left.
- **Schedule** entries reference a plan item by `(kind="plan_item", ref=item id)`. They have
  `client_request_id` idempotency per request, but nothing stops two entries for the same item.
- **Review queue** (`/me/reviews`, ladder 1/3/7/14/30 days) is separate from the plan's own
  "review" activities.
- **Weekly minutes** are the estimated minutes of activities completed in the last 7 days (UTC),
  not timed practice.

## What changed

### FU02: the time that's left (`TodayCard.tsx`, `todayAdded.ts`, `todayMinutes.ts`)

- With 5 or more minutes left after the session estimate, Today says "About N of your M min
  left." and offers **one** button: "Add another activity (title, about N min)". The candidate is
  the first pending activity by plan position that isn't already in Today and fits what's left.
- Nothing is added automatically. An added activity appears under "Added for today" with its own
  actions, and the estimate says "(with N added)".
- When nothing fits: "Nothing else in your plan fits that, and that's fine." plus a link to due
  reviews when there are any (FU08).
- Added activities are remembered per account, plan version and time budget in `sessionStorage`
  (this tab only). A new plan version, e.g. after a completion, starts afresh. The chosen budget is
  remembered in `localStorage` (no learner text).

### FU03: plan context (`planOrigin.ts`, `PlanReturn.tsx`, `useStartActivity.ts`, `Layout.tsx`)

- Starting an activity remembers `{account id, item id, title, target path, from, time}` in
  `sessionStorage` (no learner text; 12-hour expiry). Rounds now carry it too; before, only page
  activities carried a hard-coded "/dashboard" origin.
- On that page only (path match, ignoring `?`/`#`), for that account only, a "From your plan" note
  shows the activity and its "Done when" rule. Once the server has counted it as done (its own
  evidence: the item is done or the change list says `Done: “title”`), the note names the plan's
  next step and links back ("Continue your plan"). Opening the page or reading feedback doesn't
  count. The note can be hidden.

### FU04: one piece of evidence, one activity (`roadmap.py`)

- Before: one spoken answer could complete both "answer out loud" and "answer this question", and
  its minutes were counted twice in the weekly total.
- Now `_sync` collects the evidence already used by done items (`_used_evidence`), matches rounds
  first (assessment, mock, voice) so a round claims the answers inside it, and each match adds its
  answer ids and round id to the used set. Rounds store `answer_ids` in the item's evidence; older
  done items without it are resolved from `InterviewTurn.answer_id`.
- A too-short answer still completes "answer this question" (the learner did it) but is labelled
  "answered (too short to score)", not "scored N/100". Uses the existing `feedback_eligibility`.
- Known limit (unchanged): an activity superseded by a newer plan version stays pending in the old
  version; old versions aren't shown.

### FU05: swap by fit (`roadmap.py`)

- A coding swap is never longer than the activity it replaces (`CODING_MINUTES[difficulty] <=
  item.minutes`).
- The 409 message now says the activity stays: "There's no other activity like this one that fits
  in N minutes right now. This one stays in your plan; you can skip it instead."
- Already satisfied: question swaps keep skill and level and avoid recently skipped or swapped
  targets. Now covered by a test that swaps until nothing is left.

### FU06: scheduling (`ActivityCard.tsx`, `TodayCard.tsx`)

- Today reads the schedule (today to 60 days ahead) and, for an activity with an upcoming entry,
  shows "Scheduled {date}" and puts "Scheduled {date}: view or change" (to `/schedule`) in More
  options instead of "Add to schedule".
- Not done: the server doesn't enforce one entry per (kind, ref). Two tabs, or a second device,
  can still create a duplicate. A fix needs a uniqueness rule and a migration; not authorised here.

### FU07: ended-early interviews (`EndedEarlyNote.tsx`)

- When the latest question round (within 14 days) was ended early or ran out of time, both
  dashboards say so and link to its existing review ("Review it"), which lists the questions not
  reached and lets the learner answer each as a retry. It doesn't call the round complete or offer
  to resume it.

### FU08: due reviews (`TodayCard.tsx`)

- Linked from the "nothing else fits" line and from the rail. The review queue isn't merged into
  the plan: that would be a second scheduling engine for the same answers.

### FU09: weekly effort (`TodayCard.tsx`, `roadmap.py`)

- The rail card is now "Last 7 days": "{n} / {goal} min weekly goal" and "Estimated from N
  finished activities, not timed". Before, "This week" suggested a calendar week.
- The rolling window is tested by moving the clock 8 days forward.

## Checks run

Local, on the working tree of `1809217` (this document's first commit):

| Check | Result |
|---|---|
| Frontend type check (`npm run typecheck`) | pass |
| Frontend lint (`npm run lint`) | pass |
| Frontend unit and integration tests (`npx vitest run`) | 673 passed, 70 files; 13 new in `practiceFlow.test.tsx` |
| Production build and bundle budgets (`npm run build`, `npm run size:check`) | pass; shell 296.4 KB / 300 KB, largest lazy chunk 674.5 KB / 700 KB |
| Backend lint and types (`ruff check .`, `mypy app evals`) | pass (171 files) |
| Backend roadmap tests (`pytest tests/test_roadmap.py`) | pass, including 5 new tests; the two evidence tests fail on the previous code |
| Full backend suite, SQLite (`pytest`) | 2257 passed, 386 skipped, 2 xfailed (the two known rubric residuals) |
| Full backend suite, PostgreSQL 16 (`TEST_DATABASE_URL=…/codecoach_test pytest`) | 2258 passed, 1 failed, 384 skipped, 2 xfailed. The failure was `test_the_code_knows_its_own_migration_head`, because the next pack's migration was added to the working tree while this run was going; the pinned head was updated with that migration |
| End-to-end (Playwright, Chromium, real backend on SQLite) | 91 passed, 3 skipped, 1 failed: `explore.spec.ts` scroll restoration after reload, while the PostgreSQL suite was loading the machine. Re-run alone: 2/2 passed. Not just load: it also failed in CI. A timing race in `useScrollMemory`, fixed in the next pack (see `INTERVIEW_WORKFLOW.md`) |
| CI on `1809217` (run 201) | Frontend, backend (SQLite + PostgreSQL + migrations), runner, Docker, dependency audit and sandbox passed. End-to-end failed: the same `explore.spec.ts` scroll test, a timing race in `useScrollMemory`, root-caused and fixed in the next pack (see `INTERVIEW_WORKFLOW.md`) |

New tests:

- `backend/tests/test_roadmap.py`: one spoken answer completes one activity, not two; a too-short
  answer finishes the activity without quoting a score; swapping never repeats a target and keeps
  the original when nothing is left; a coding swap is never longer than what it replaces; weekly
  minutes are a rolling 7 days counted once.
- `frontend/src/test/integration/practiceFlow.test.tsx`: top-up add, no-fit and under-5-minute
  cases, the due-review link; scheduled and unscheduled activities; the plan note from Today to the
  page, after completion, hidden, for another account and on another page; the ended-early note for
  ended early, out of time, completed and long-past rounds.

## Limits

- Top-up additions are per tab (`sessionStorage`); another device doesn't see them. They're a
  learner's own choice for today, not part of the plan on the server.
- Schedule duplicates are still possible across tabs or devices (FU06).
- The review queue and the plan remain two lists; only links connect them (FU08).
- Chromium only. No screen reader, phone or Safari run for these changes.
- The app shell is 296.4 KB gzip against a 300 KB budget.
