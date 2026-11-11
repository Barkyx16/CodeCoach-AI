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
   and the last answered question (from `/me/resume`) are listed here too.
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

- **Nothing here means "opened".** The app doesn't record opening these records, so no time claims it.
- **An interview whose clock is running comes first**, then everything else by its time, newest
  first; `limit` is 1–12 (default 6).
- **Titles and times only.** No note body, story text, application notes, kit contents, offer
  terms or transcript is read; a test captures the SQL to check.
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
times only, on SQLite and PostgreSQL); `src/test/integration/continueWork.test.tsx` (destinations
and labels, a finished interview as a result, nothing sent on load, Check result found and not
found, one source failing, a named kind, hide and show, a record deleted elsewhere, another account
signing in) and `progress.test.tsx`; `e2e/continue-work.spec.ts` (real API: a note, a finished
round, an earlier story save checked and opened, Back, axe in dark and light) and
`continue-work-mobile.spec.ts` (fits a phone; hiding sticks through a reload).

## Limits

- Six kinds of record; others (drills, labs, reflections) aren't listed yet.
- Only actions this browser recorded can be checked; one sent from another device isn't known here.
- Hiding is per device, not per account.
