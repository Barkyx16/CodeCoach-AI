# Continue your work (Volume 11, prompt 1)

The dashboard's **Continue your work** section (`features/dashboard/ContinueCard.tsx`, on both the
career and the coding dashboard) replaces "Continue where you left off". It helps you get back to
work; it isn't a score or a plan. Loading it only reads: nothing is sent, started, graded or recorded.

## The four groups, kept apart

1. **An interview in progress** first, with its time left. Its timer runs on the server and can't
   pause; Resume opens it. (From `GET /api/v1/me/resume`, as before.)
2. **Saved to your account**: up to six records from `GET /api/v1/me/recent-work` (below), each with
   its kind, state, the time it really keeps ("saved", "started", "finished"; never "opened") and an
   action: Open, Resume, or See results for an interview that has ended. The last unsolved problem
   and the last answered question (from `/me/resume`) are listed here too; a debugging exercise
   already listed as tried isn't listed again as the last unsolved problem.
3. **Only in this browser**: an unsent answer and a code draft, labelled "Not on your account yet,
   and not on your other devices", plus a count of any other copies with a link to Your data.
4. **Waiting for a reply**: actions sent before a reload whose reply never came (the device's
   pending records, YOUR_DATA.md). **Check result** asks the server what that key made (a read;
   nothing is sent again) and says it arrived (with a link: the story, the note, the problem), never
   arrived, is still being answered, or couldn't be checked. Answered records are forgotten.

- **One source failing keeps the rest:** recent work that can't load says so inside its group with
  Try again; a kind the server couldn't read is named; the interview and drafts still show.
- **Current state:** the list is read again each time the dashboard shows, so a record deleted or
  ended elsewhere drops out or shows its new state; a stale link opens the record's own "no longer
  available" page with its list.
- **Hide** keeps the section to one line ("Show it") on this device (`codecoach.continue.hidden`,
  a display preference); hidden, it fetches nothing.
- **Archived records** (and an archived application's kits) aren't listed: archiving takes a record
  out of active views (ARCHIVE.md).
- **Nothing yet** is said in a sentence; no sample activity is invented.
- **Another account** never sees the previous one's titles: signing out clears the cache, drafts
  and pending records are per account (YOUR_DATA.md).

## `GET /api/v1/me/recent-work?limit=6` (`app/services/recent_work.py`)

A few of the caller's own records, newest first, for a "Continue your work" starting view.

| Type | Title | Time it reports (`at_meaning`) | Extra |
|---|---|---|---|
| `interview` | "Registered Nurse question round", "Coding interview: Two Sum" | `started` while running; `finished` once ended | `state`: `in_progress`, `time_up` (its clock ran out, not yet closed), `finished`, `expired`, `ended_early` |
| `note` | its title, or "Untitled note" | `saved` (last saved to the account) | deleted notes, even in their undo window, aren't listed |
| `story` | its title | `saved` | |
| `kit` | "Interview-day kit: <event> (<employer>)" | `saved` | `id` is the event, `parent_id` the application; `detail` the interview date |
| `application` | "<role> at <employer>" | `saved` | `detail` the stage |
| `offer_comparison` | its title | `saved` | |
| `scenario_run` (Volume 19, prompt 6) | its scenario's title | `last_step` at its last step's time once a step is taken (Volume 20, prompt 6; the card says "last step"); `started` at its start before that | only runs in progress: a finished one has nothing to continue; Resume opens the run at the step it was left on (`/scenarios/attempts/<id>`); `detail` "Exploration" for an exploration run. The last step's time is the one its step recorded, taken from the run in the query; nothing else of the steps is read |
| `test_design_run` (Volume 19, prompt 6) | its exercise's title | `saved` while waiting for the judge or saved without one; `finished` once the judge finished or failed | `detail` in its run list's words ("Waiting for the judge · version 1", "Told apart 2 of 4 faulty versions · version 1", "The judge couldn't run it · …", "Not run: this server can't run code · …"); `parent_id` the exercise; Open shows its report (`/test-design/<slug>?attempt=<id>`). One that's no longer waiting drops out a week after its time (`FINISHED_RUN_DAYS`); one waiting stays |
| `debug_exercise` (Volume 20, prompt 6) | the exercise's title ("Fix: Count Within a Limit") | `tried`: its newest submitted attempt's time | `id` is the exercise's slug; Resume opens the exercise (`/problems/<slug>`). Listed while none of its submitted attempts passed (the plan's rule for "not fixed": a pass is fixed, even if a later attempt fails) and its newest attempt is less than a week old (`TRIED_DAYS`). `detail` is that attempt's verdict in the words the exercise's page uses: "Not fixed yet: 3 of 7 tests pass", "Not fixed yet" (no counts, as when the judge failed), "Queued" or "Running" while it's judged, and "Saved, not checked" on a server that can't run code (the page's debrief heading; with the judge on, the status badge's words while judging) |

- **Nothing here means "opened".** The app doesn't record opening these records, so no time claims it.
- **An interview whose clock is running comes first**, then everything else by its time, newest
  first; `limit` is 1–12 (default 6).
- **Titles and times only.** No note body, story text, application notes, kit contents, offer
  terms or transcript is read, nor a scenario run's steps (only its last step's time, taken in the
  query) or a test-design run's cases or report (a run's result is two numbers taken from its report
  in the query), nor a debugging attempt's code (only its status, its two counts and its time); a
  test captures the SQL to check.
- **What a page can show (`shows`).** Debugging exercises and last-step times are sent only to a
  page that asks: `?shows=debug_exercise,last_step` (unknown values are ignored). A page cached from
  before Volume 20 doesn't ask, so it gets the eight kinds it knows and scenario runs at their start,
  as before, and never a kind its table of paths can't open. The card itself also leaves out any
  kind it has no path for, so a later kind can't break it either.
- **Owner only.** Every query filters by the caller (and PostgreSQL row-level security applies on
  the tables it covers); another account's records are never listed; anonymous callers get 401.
- **One kind failing doesn't take the rest down.** Each kind is read in its own savepoint; one that
  fails is named in `unavailable` (for example `["notes"]`) and the others are still listed. Tested
  on SQLite and PostgreSQL.
- **Server-saved records only.** Copies in a browser and actions waiting for a reply live on the
  device (see [YOUR_DATA.md](YOUR_DATA.md)); the dashboard section lists them separately
  and labels them as such.

## Tests

`tests/test_recent_work.py` (order, times, ownership, deleted records, one kind failing, titles and
times only, on SQLite and PostgreSQL); `tests/test_recent_work_debug.py` (Volume 20, prompt 6, on
both: an exercise tried and not fixed with its verdict and time, the newest attempt speaking for it,
"Saved, not checked" without the judge, a fixed one absent even after a later failure, the week, a
scenario run's last step time and a run with none at its start, a page that doesn't ask getting what
it did, another account's never listed, the read failing named, the SQL reading no code, listed once
and the plan's words unchanged); `src/test/integration/continueWork.test.tsx` (destinations
and labels, a finished interview as a result, nothing sent on load, Check result found and not
found, one source failing, a named kind, hide and show, a record deleted elsewhere, another account
signing in) and `progress.test.tsx`; `e2e/continue-work.spec.ts` (real API: a note, a finished
round, an earlier story save checked and opened, Back, axe in dark and light) and
`continue-work-mobile.spec.ts` (fits a phone; hiding sticks through a reload);
`continueWork.test.tsx` (Volume 20: the exercise's row, path and words, asking with `shows`, listed
once beside the last unsolved problem, "last step" and "started", a later kind left out) and
`e2e/continue-debug.spec.ts` (the real API: an attempt saved on the exercise's page listed in the
debrief's very words, a scenario run at its last step, 360 and 412 pixels wide with axe in both
themes, nothing sent by loading, Resume opening the exercise).

## Limits

- Nine kinds of record (scenario runs and test-design runs since Volume 19, prompt 6; debugging
  exercises since Volume 20, prompt 6); others (drills, reflections) aren't listed yet. A page cached
  from before Volume 19 shows those two without a label until it updates (the response's `type`
  gained two values); one from before Volume 20 never gets the ninth (see `shows`).
- A debugging exercise last tried more than a week ago isn't listed, even if it's still not fixed;
  the plan still suggests its lesson (docs/PLAN_UPDATES.md).
- Only actions this browser recorded can be checked; one sent from another device isn't known here.
- Hiding is per device, not per account.
