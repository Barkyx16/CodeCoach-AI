# Interview workflow upgrades (Overnight Upgrades: Interview Workflow, 01–14)

Extends the existing Applications, Interview Kit, Reflections, Stories and Schedule services. No
new tracker, store or route. One additive migration (`a1b2c3d4e5f6`, interview kits only). The
API changes are additive: `scripts/api_compat.py --strict` reports 0 breaking, 9 compatible
additions against the previous `docs/openapi.json`. The design work (purple theme, top bar,
dashboard layout, global CSS) is unchanged; new UI reuses `Button`, the existing `banner` styles
and the conflict pattern already used by stories.

## Brief states

| Brief | State | Evidence |
|---|---|---|
| 01 Reconcile and choose a slice | Done | Read-only inventory of models, services, routes, pages and tests (file:line), spot-checked; the gaps it found are the slice below. |
| 02 Open the right upcoming preparation | Implemented | "Next interview" order is stated and deterministic. The board card links to that interview's kit, and interview-prep schedule entries open the kit. |
| 03 Rescheduling without rewriting history | Implemented (kit), documented (others) | The kit shows the time it was last saved for when the interview moves, and never unticks anything. Event edits refresh the cached kit. Reflection snapshots and stage history are untouched. Schedule slots stay independent (documented). |
| 04 Requirement-to-evidence links | Implemented (labels), already satisfied (links) | Suggested questions say where their requirement came from (pasted posting, added by you, or inferred from the career, "not from the job description"). A 300-character requirement no longer breaks the kit. Story-to-requirement links are existing, learner-chosen and have no match scores. |
| 05 Story changes visible | Implemented | The kit records each chosen story's version and flags edits since, with "I've reread it". Archived chosen stories stay untickable; deleted ones are counted. A reflection whose linked story was deleted can be saved again. |
| 06 Reflection to an explicit story revision | Implemented (minimal) | "Revise this story" from a reflection's linked stories opens the story's own versioned editor (with its stale-save check) and leads back. Nothing is copied or applied. |
| 07 Stale kit saves | Implemented | Kit revision plus 409 `stale_revision`; race-safe through a version column; two simultaneous first saves give one kit and a 409, not a 500. The page keeps edits and offers an explicit overwrite or reload. |
| 08 The printable PDF | Implemented and inspected | Print styles are scoped to the kit page; unsaved changes print only a notice. Real PDFs were produced by Chromium and inspected (text, link annotations, metadata). |
| 09 Accepted next steps | Implemented | Accepting claims the step with a conditional update before creating anything (no second note under concurrency). A removed result is shown as removed, never recreated. |
| 10 Outcome and optional stage change | Implemented | Saved in one transaction, or neither. A repeat adds no history. The page says exactly what changed. |
| 11 Follow-up drafts | Already satisfied; context deferred | Drafts are built on the page, never stored or sent; copy and download are explicit. Adding interview details to drafts needs a product decision (which confirmed details to offer), so it isn't done. |
| 12 Context through deep links | Implemented | Event → kit/reflection, kit ↔ reflection, kit → story, reflection → question/note/story and board → kit all carry a way back. History state holds paths and generic labels only. |
| 13 Export and deletion boundaries | Implemented (dialogs, docs, kit export), deferred (export ids) | Delete dialogs now say kits and reflections go too and what stays. The kit export carries its new provenance. Export ids for joining records need a backup-format version decision. |
| 14 Connected journey and handoff | Done | This document; checks below. |

## What changed, and the reference/snapshot policy

**Live references** (always the current value): a kit's event title, date, time and zone; a kit's
chosen stories (title, short version, archived); the application's next event; a schedule entry's
link.

**Snapshots** (the value at the time, never rewritten): a reflection's role, employer, stage,
event title and date (taken on its first save); application stage history; a kit's
`event_when` (the time it was last saved for) and `story_revisions` (each chosen story's version
when chosen or last marked as reread); a reflection outcome's history.

### Kits (`app/services/kits.py`, `app/models` `InterviewKit`, `KitPage.tsx`, `PrintPack.tsx`, `kit.css`)

- **Conflict-safe saves.** New `revision` column, used as SQLAlchemy's version column, so an
  UPDATE whose revision moved matches no row.
  - `PUT …/kit` takes `expected_revision`. A different current revision is 409 `stale_revision`
    with `{current_revision}`, and nothing changes.
  - A save that loses a race (`StaleDataError`), or two first saves at once (`IntegrityError` on
    the primary key), is the same 409.
  - The page keeps the learner's edits and offers "Save mine over it" (sends the current revision:
    an explicit overwrite) or "Discard mine and load the saved kit".
  - If a refetch shows another tab saved, the page says so before the learner saves.
  - Old clients that don't send `expected_revision` keep the previous last-writer-wins behaviour.
- **Reschedule.** `event_when` (`date|HH:MM|zone`) is recorded on every save. When the event no
  longer matches, `rescheduled_from` gives the old time, and the page names both. Saving the kit
  (on that page, where the notice shows) records the new time. Ticks are never changed.
  - Kits saved before the migration have `event_when = NULL`, so they make no claim.
  - Event edits and deletions invalidate the cached kit and reflection.
- **Stories.** Each story has `revision` and `chosen_revision`.
  - The page lists stories edited after they were chosen, with "Read it" and "I've reread it" (sent
    as `reviewed_story_ids`).
  - Saving for any other reason doesn't mark a change as reread.
  - Archived chosen stories stay in the picker as "(archived)". Deleted ones are counted
    (`missing_stories`) and said, not silently dropped.
  - A save from a page opened before a story was deleted drops that id instead of failing.
    Another account's story id, or one never chosen, is still a 404.
- **Suggestions.** Each suggested question's note names its source by the requirement's `origin`.
  Long requirement text is cut at a word with "…" so the question (≤300) and note (≤200) fit.
- **Printing.**
  - The print rules apply only under `body:has(.print-pack)`. Before this change, `body *
    {visibility: hidden}` was loaded app-wide and printed every other page blank. A Chromium check
    of both rules confirmed it: old rule, other page heading visible = false; new rule = true.
  - With unsaved changes the pack prints only "This kit has unsaved changes, so it isn't printed.
    Save the kit, then print it." This also covers the browser's own Print.
- **Export.** Each kit now also has `revision`, `saved_for_event_time` and
  `story_versions_when_chosen` (null for kits saved before them).

### Reflections (`app/services/reflections.py`, `ReflectionPage.tsx`)

- **Deleted stories.**
  - `story_ids` lists only stories that still exist, and `missing_stories` counts the others.
  - Saving no longer fails with "Story not found" because a linked story was deleted. An id that
    was linked is dropped; anything else unknown or another account's is still refused.
  - Before, a reflection whose story had been deleted couldn't be saved at all.
- **Accepting a step.**
  - Validation runs first. A conditional `UPDATE … WHERE status != 'accepted'` then claims the
    step, so a concurrent second accept waits, finds it accepted and returns the stored result.
  - The note is created in the same transaction (`Notebook.create(commit=False)`).
  - Before, a lookup-then-create let two requests make two notes.
  - `applied_available` says whether the note, schedule entry or bookmark still exists. A note in
    the notebook's bin counts as removed. The page says it was removed and doesn't offer it again.
- **Outcome.**
  - The stage change (`Applications.set_stage(commit=False)`) and the outcome are committed
    together, and a failure rolls both back.
  - Before, the stage was committed first, so a failure left the application moved and the outcome
    unrecorded.
  - The same outcome again, with nothing to move, returns unchanged with no new history entry.
  - The page says one of: "moved to …", "was already at …, so it wasn't moved", "wasn't changed"
    or "Nothing changed". It also refreshes the application's cached pages.
- **Conflict.** The banner adds "Discard mine and load the saved version" next to the existing
  "Save mine as the newest".
- **Links.**
  - The interview kit.
  - "Revise this story" for each linked story.
  - The practice question and note links lead back to the reflection.

### Applications and schedule (`app/services/applications.py`, `app/services/schedule.py`, pages)

- **Next interview.**
  - Order: by the event's own date; on the same date, exactly-timed events by their instant, then
    date-only ones; then by when each was recorded. Before, ties fell to random UUIDs.
  - A date-only event counts until its date has ended everywhere (UTC−12), not by the UTC or server
    date.
  - Undated events are never "next". The schedule's list of interviews to prepare for uses the
    same rule.
- **Links.**
  - The board card shows "Next: title · date (time not known)" and a "Prepare" link to that
    interview's kit.
  - Interview-prep schedule entries link to the kit, not the application.
- **Deletes.** The event, application and story delete dialogs say what is removed with them and
  what stays.

## Migration `a1b2c3d4e5f6`

Additive on `interview_kits`:
- `revision INTEGER NOT NULL DEFAULT 0`
- `event_when VARCHAR(80) NULL`
- `story_revisions JSON/JSONB NULL`

No row is rewritten. The downgrade drops the three columns; kit content stays, but stale-save
protection is lost.

Validated only on a disposable PostgreSQL 16 database (`codecoach_rehearsal_iw`, created and then
dropped):
1. `alembic upgrade head`, then `alembic check`. The first check caught a JSON type mismatch; the
   fix uses the project's JSONB variant, and the next check passed.
2. A kit was seeded at head, then `downgrade -1` and `upgrade head` reproduced a pre-upgrade kit.
   That kit kept its content and ticks, read revision 0 with NULL snapshots, saved to revision 1
   against `expected_revision=0`, and a second stale save was refused.
3. `downgrade base` ran without errors.

No production or shared database was touched.

## Checks run

On the working tree of this document's first commit (local, PostgreSQL 16 and Chromium headless):

| Check | Result |
|---|---|
| Backend lint and types (`ruff check`, `ruff format --check`, `mypy app evals`) | pass |
| New backend tests fail on the previous code | 14 of 14 failed with the service and schema files stashed, then passed restored |
| Kit, reflection, application, schedule, notes, platform and OpenAPI tests on PostgreSQL (`TEST_DATABASE_URL=…/codecoach_test`) | 71 passed, including both kit races |
| Same files on SQLite | pass |
| Full backend suite on SQLite (`ruff`, `mypy app evals`, `pytest`) | 2270 passed, 386 skipped, 2 xfailed (known rubric residuals); lint, format and types clean |
| API compatibility (`scripts/api_compat.py --strict`) | 0 breaking, 9 compatible additions |
| Migration rehearsal (disposable PostgreSQL) | pass (see above) |
| Frontend type check, lint | pass |
| Frontend unit and integration (`npx vitest run`) | 684 passed, 70 files; 11 new (kit 5, reflection 5, board 1) |
| Production build and bundle budgets | pass; shell 298.2 KB / 300 KB, largest lazy chunk 674.5 KB / 700 KB |
| End-to-end: `kit-pdf.spec.ts` (new) and `kit.spec.ts` | 3 passed |
| End-to-end, full suite (`npx playwright test`, nothing else running) | 93 passed, 3 skipped, 0 failed (13.1 min) |
| `explore.spec.ts` scroll flake (see below) | reproduced 1 in 8 under CPU load before the fix; 12 of 12 restored after it; explore and notes specs pass |
| PDF text inspection (`pypdf`, local) | 4 of 4 files pass (below) |
| Print rule before and after (Chromium) | old rule blanks other pages; new rule doesn't |

New tests:

- `backend/tests/test_kits.py`: a stale save is refused and changes nothing; a save that loses a
  race is a conflict; two first saves give one kit and a conflict; a reschedule is shown without
  unticking; a pre-migration kit claims nothing; story edits, archives and deletes are visible; a
  long requirement gives a valid suggestion.
- `backend/tests/test_reflections.py`: a deleted story doesn't block saving; two accepts at once
  create one note; a removed result is shown, not recreated; an outcome and its stage change are
  saved together or not at all; repeating an outcome adds no history.
- `backend/tests/test_applications.py`: the next interview's order. `test_schedule.py`: prep
  entries open the kit.
- `frontend/src/test/integration/kit.test.tsx`: stale save with overwrite; discard and reload;
  reschedule notice; edited, archived and deleted stories; unsaved print notice.
- `frontend/src/test/integration/reflection.test.tsx`: outcome messages; failed outcome; removed
  note; discard after conflict; revise a linked story.
- `frontend/src/test/integration/applications.test.tsx`: the board's "Prepare" link.
- `frontend/e2e/kit-pdf.spec.ts`: the real PDFs.

### A flaky end-to-end test, fixed at the cause

`explore.spec.ts` ("Back keeps the filters and scroll, even after a reload") failed in CI on
`1809217` and once locally under load, and passed when run alone.

- **Cause:** `useScrollMemory` saved positions from scroll events, and its listener was removed in
  a passive effect. When the next page's scroll-to-top was dispatched before that effect ran, the
  list's saved position became 0, so Back had nothing to restore.
- **Diagnosis:** a temporary diagnostic copy of the test logged the saved value per history entry.
  It was 0 in the failing run and 1467 in the passing ones.
- **Fix (`src/hooks/useScrollMemory.ts`):**
  - The listener lives in a layout effect.
  - The exact position is saved when the entry is left.
  - Scroll events are ignored while a Back/Forward visit is still waiting to restore.
- The test itself is unchanged.

## PDF inspection (brief 08)

- **Browser:** Chromium headless from Playwright (`Skia/PDF m153`), through `e2e/kit-pdf.spec.ts`.
  The spec builds a synthetic kit through the UI with sentinel values (`PRIVATE-LINK-SENTINEL`,
  `Sentinel Interviewer`, `PRIVATE-NOTE-SENTINEL`) and calls `page.pdf({ format: "A4" })` four
  times.
- **Checks in CI (raw bytes):** no `/URI` annotation for the sentinel domain, and no sentinel in
  the file or its metadata, with default choices.
- **Text check (local only, `pypdf` 6.17):** extracted text, annotations and metadata of each file,
  checked by a script kept outside the repository.

| File | Expected | Result |
|---|---|---|
| `kit-default.pdf` | Positive controls in (event, "Not sent to anyone", the learner's question, "Still to do"); no sentinel in text, annotations or metadata | PASS: 1 page, no annotations, title "Interview-day kit \| CodeCoach AI" |
| `kit-opted-in.pdf` | The chosen private details print as text; the link isn't clickable | PASS: all three sentinels in text, no annotations |
| `kit-unsaved.pdf` | Only the unsaved notice | PASS: 79 characters, no kit content |
| `other-page.pdf` (`/applications`) | The page's own content, not blank | PASS: 2 pages, 609 characters; its in-app links are annotations, which is expected |

This is one local Chromium's PDF. It doesn't prove paper output, other PDF viewers or other
browsers (WebKit and Firefox aren't installed here).

## Limits and open decisions

- **Export can't be joined back together.** Applications, events, notes, targets and schedule
  entries have no `id` in the account export. The ids that kits, reflections and accepted steps
  refer to point at nothing in the file, and kits and reflections aren't restored. Fixing this
  changes the backup format, which needs a version decision.
- **Schedule prep slots.** A slot isn't moved when its interview moves, and nothing warns when the
  slot now falls after the interview.
- **Reflections don't record story versions**, so "edited since" exists for kits only.
- **Events don't store the "which one" choice for an ambiguous local time** (`fold`), so editing
  such an event asks again.
- **Three unrelated "interview date" fields:** `RoleTarget.interview_date`,
  `PracticeGoal.target_date` and application events. Not reconciled here.
- **Drafts** still use only role and employer. Which confirmed interview details to offer is a
  product decision.
- **No dashboard "next interview" shortcut.** That would change the dashboard design work.
- **The app shell is 298.2 KB gzip of a 300 KB budget.**
- **Browser coverage:** Chromium only, with no screen reader or phone. History state carries paths
  and generic labels only; nothing private goes in URLs.

## Next action and resume

**Highest-priority remaining issue:** the account export can't be joined back together. Records
in it carry no ids, so kits, reflections and accepted steps point at nothing in the file. Next
action: decide whether to add ids under a new export format version. That's the product decision
needed; the code change is additive.

**Then:**
- Prep slots that now fall after their interview.
- Story versions in reflections.
- Storing `fold` for events at an ambiguous time.

**Resume prompt.** Read `docs/INTERVIEW_WORKFLOW.md` and the commit history on
`claude/gallant-galileo-hapob6`, then:
- Verify the branch, HEAD and a clean worktree.
- Check CI for the latest pushed SHA job by job.
- Keep the design files and unrelated edits as they are.
- Pick up the first open item under "Limits and open decisions" that needs no product decision.
- Don't re-run checks that passed unless the code they cover has changed.
