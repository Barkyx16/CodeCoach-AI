# Continue your work (Volume 11, prompt 1)

**State: the backend part is built; the dashboard section that uses it is not built yet.** The
dashboard still shows the existing "Continue where you left off" card (`ContinueCard.tsx`, from
`GET /api/v1/me/resume` and this browser's drafts), unchanged.

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
  device (see [YOUR_DATA.md](YOUR_DATA.md)); the dashboard section, when built, lists them
  separately and labels them as such.

## Still to do (the rest of prompt 1)

The dashboard section: in-progress, saved, on-this-device and waiting-for-a-reply groups; a
read-only "Check result" for an earlier uncertain action; a localized message when one source
fails; unavailable destinations; hiding the section; account switching; browser and accessibility
checks.
