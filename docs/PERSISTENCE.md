# What saves your work, and where

For every feature that holds work: the authoritative record, what stays only in this browser,
whether another device sees it, what the page's "Saved" means, how conflicting edits are
handled, and export and deletion. Where the data physically lives (SQLite, PostgreSQL, volumes)
is in [STORAGE.md](STORAGE.md).

Rules that hold for every row:
- **Account deletion** (`DELETE /api/v1/auth/me`) deletes the account. Every table below goes with
  it (`ON DELETE CASCADE`). The browser then clears the same private drafts as sign-out.
- **Export** (Settings → Download your data) includes every server record below; v2 adds ids
  and links ([BACKUP_FORMAT.md](BACKUP_FORMAT.md)). Browser-only drafts aren't exported: the
  server never had them.
- **Sign-out** clears this account's private drafts from the browser, after a warning naming
  how many are unsent (`frontend/src/auth/localWork.ts`). Device preferences stay; they aren't
  account data. A test scans the source for draft-like storage keys and fails if one isn't
  cleared.
- **Guest → account** (`POST /auth/upgrade`) keeps the same account id, so every server record and
  every draft stays the person's. Nothing is merged from another account.

## The table

"Server" means the API's database; another device sees it after signing in. "Browser" means
this browser's localStorage only.

| Feature | Authoritative record | Browser-only | Another device? | "Saved" means | Conflicts | Repeat-safe creates |
|---|---|---|---|---|---|---|
| Profile, career choice | server (`users`) | a cache of name and track for the next start-up | yes | "Saved." = the server accepted it | last write wins (one-field settings) | — |
| Coding attempts | server (`submissions`) | — | yes | "Saved, but not run yet." = stored on the server | append-only | request key per send |
| Code editor drafts | **browser** (`codecoach.draft.v1.<account>.<problem>`) | the draft | **no** | "Saved on device" / "Not saved: storage unavailable" | — | — |
| Written answers | server (`practice_answers`) | the unsent draft | answers yes, drafts no | "Draft saved on this device, not sent yet." | answers never change; a revision is a new row | request key + fingerprint |
| Mock interviews | server (sessions, turns, retries) | round, follow-up, chat and retry drafts, keyed by interview | sessions yes, drafts no | "Your typed or spoken draft is saved in this browser." | an answer for a question that isn't current: 409. A different answer to a question answered elsewhere: 409 `question_answered_elsewhere`, and the text stays on screen. A coding message written against an older transcript: 409 `interview_advanced`, and the text stays in the box ([INTERVIEW_CONTINUITY.md](INTERVIEW_CONTINUITY.md)) | one interview in progress at a time, enforced by the database |
| Stories | server (`experience_entries` + revisions) | unsaved edits (with their base revision) | yes | "Saved as version N." (exactly that text) / "Unsaved changes, kept on this device" | `expected_revision`, else 409. **Fixed in this batch:** also on the target page's editor, and atomic under concurrency (row lock) | — |
| Notes | server (`notes`) | a recovery copy while unsaved | yes | "Saved" = on the server; "Offline: saved on this device. Sync pending…" | `base_revision`, else 409 `note_conflict` (pin and archive are deliberately exempt). **Fixed:** atomic under concurrency | **Fixed:** request key per new note (autosave retries no longer duplicate it) |
| Whiteboard | server (draft + attempts) | unsaved edits | yes | "Saved to your account" / "Unsaved changes, kept on this device" | `expected_revision`, else 409. **Fixed:** atomic, and two first saves at once give 409, not 500 | — |
| Reflections | server (reflection + actions) | unsaved edits | yes | "Saved. Only you can see it." | `expected_revision`, else 409. **Fixed:** atomic, the same first-save case. Action edits: last write wins | accepting an action is claimed once |
| Test design | server (`test_design_runs`) | the unsent cases | runs yes | "Your unsent cases were restored from this device." / not run: "these cases weren't run" | a run is never edited; revised cases are a new run | request key |
| Code-review practice | server (`code_review_drafts`, `code_review_attempts`) | unsaved findings (with their base revision) | yes | "Saved to your account" / "Unsaved changes, kept on this device" | `expected_revision`, else 409 with the saved version; reviews sent are append-only | update receipts (request key) |
| Drills | server (`drill_attempts`) | the unsent text | attempts yes | "kept on this device until you send it" | append-only | request key |
| Learn mode | server (`learn_events`) | exercise drafts: **never sent** | progress yes, exercise text no | "Your draft is saved in this browser" | 409 `unit_changed` when the lesson changed | dedupe key |
| Role targets | server (targets, requirements) | — | yes | — | last write wins | — |
| Applications | server (applications, stages, events) | unsaved private notes, with the revision they started from (per account; offered back on return); message drafts aren't stored, by design | yes | "Saved." (only while the form matches what was accepted); "This browser can't keep a copy of unsaved notes" when storage is refused | **private notes:** `notes_expected_revision`, else 409 `notes_conflict` with the saved notes, compared side by side (Volume 8, prompt 5; a notes change without it is 428). Other fields (title, employer, dates, link, next action) are still last write wins and never conflict with the notes; a repeated stage change is a no-op | request key; a notes save's lost reply is recognised by its receipt |
| Schedule | server (settings, entries) | which reminders this tab already showed | yes | "Saved." | moves: last write wins; prep tied to an interview: 409 if the interview changed | request key |
| Interview kits | server (`interview_kits`) | unsaved edits, in memory only (leaving asks first) | yes | "Saved." (exactly that kit) / "Unsaved changes" | `expected_revision` (sent by this app; older clients: last write wins) | one per event |
| Bookmarks, collections, queue | server | — | yes | — | last write wins | bookmark and item: unique |
| Plan, goals, reviews | server | "added to Today" and today's minutes, this tab or browser only | plan yes; those counters no | — | goals: last write wins; a closed activity: 409 | goals: one per career |
| Onboarding | server | a pending "finish the tour" flag | yes | — | last write wins | one per account |
| Scenarios | server | — | yes | "Your place is saved on the server…" | stale step: 409 | resumes the attempt in progress |
| Self-reviews | server | in memory until sent | yes | — | last write wins | one per answer |
| Preferences (display, editor, voice, reflect-first, drill delivery) | **browser** | all of it | **no** | "Saved in this browser." | — | — |

## What "Saved" means (Volume 7, prompt 4)

"Saved" is said only for exactly the text the server accepted. Until this pass, several pages
could say it about text the server never got.

- **A slow save never marks newer edits saved.** The page sends a snapshot. When the response
  arrives, it compares that snapshot with what's on the page now:
  - Unchanged: the page shows the server's copy and says it's saved.
  - Edited in the meantime: the newer edits stay, now unsaved against the new version, and the
    page says "Unsaved changes".
  - Before, stories, kits and reflections replaced the form with the server's copy, which erased
    keys typed during the save.
  - Application details and schedule reminders say "Saved." only while the form still matches
    what was accepted.
  - A "Saved" notice clears on the next edit; on stories, the whiteboard and reflections it used
    to stay up.
- **Sending doesn't erase what was typed meanwhile.** Written answers and drills clear the box only
  if it still holds exactly what was sent.
- **Storage failures are save failures.** When this browser can't keep a copy (private mode,
  storage full), the page says so. It doesn't claim "kept on this device", and it offers Copy:
  notes, reflections, the whiteboard; stories already said so. Before, notes, reflections and the
  whiteboard swallowed the error and still claimed the copy was kept.
- **Leaving.** In-app navigation asks first on the same pages, and under the same condition, as
  the browser's close and reload warning: one guard for the app (`app/LeaveGuard.tsx`). A kit's
  edits live only on the page, so leaving a dirty kit always asks.

## Conflict policy

- **Long-form writing** (notes, stories, whiteboards, reflections, kits) is versioned. A save
  names the revision it started from. If the record moved on (another tab, another device), the
  save is refused with 409. Every 409 `stale_revision` now carries the saved version
  (`details.current`), so every one of these pages shows both versions side by side
  (`components/VersionConflict.tsx`). Notes already did, through their own panel. The page shows
  only the parts that differ and offers three choices:
  - "Keep my version": sends all of it, against the saved revision;
  - "Use the saved version";
  - "Copy my version".

  Nothing is merged automatically: code and assessed prose are never combined without review. A
  conflict is announced once (`role="alert"`).
- **A copy kept on this device is compared before it's used.** Stories, the whiteboard and notes
  record the revision a kept copy was written against; reflections do too now. Restoring a copy
  written against an older revision opens the same comparison. It doesn't silently become the
  text a save would put over the newer version.
- These checks hold when two saves arrive at the same moment. Each takes a row lock
  (`app/db/locking.py`), so the second waits, sees the new revision and gets its 409. Before this
  batch, two simultaneous note saves could both "succeed" with one silently replacing the other.
  `test_two_tabs_saving_a_note_at_once`'s sensitivity half reproduces that without the lock.
- **Short settings and fields** (profile, goals, onboarding, application fields, schedule moves,
  collection names, self-reviews, action edits) are last-write-wins. They are small and
  re-entered in seconds, and the newer value is what the person last chose. That is a
  deliberate limit, not versioning.
- **Creates that might be sent twice** carry a request key: submissions, answers, applications,
  schedule entries, drills and, since this batch, new notes. A retry returns the original.

## Not cross-device (by design or not yet)

- Code editor drafts, unsent answer, drill and interview drafts, learn exercise text, and
  preferences live in this browser only. The pages say so ("on this device", "in this
  browser"). They're cleared when you sign out on this device.
- If storage is unavailable (private mode, full), pages that keep drafts say the draft can't be
  kept, instead of pretending ("Not saved: storage unavailable").
- Drafts written while signed out (`…anon…` keys) aren't tied to an account and aren't cleared
  by a sign-out.
- A session that ends by itself (expiry, sign out everywhere) isn't a sign-out: that account's
  drafts and pending-action records stay in this browser, locked to it, until it signs in again
  (or signs out here). RECOVERY.md "When a session ends" has the whole policy.
- Interview round, chat and retry drafts are keyed by the interview, not the account. Only the
  interview's owner can open it, so they never load into another account's form, and they're
  cleared at any sign-out on the device.
- Browser-only drafts have no cross-device conflict check, because there's nothing to conflict
  with: another device never sees them. The code editor and the interview's code are the
  unsupported editor path for multi-device work: each device keeps its own copy, and the server
  sees code only when it's submitted or sent with a message.

## Tests

| What | Where |
|---|---|
| Same create twice, and four at once: one note; keys are per account | `backend/tests/test_persistence.py` |
| Two tabs saving a note or a story at once: one 200, one 409 (sensitivity halves without the lock) | same, PostgreSQL |
| Two first whiteboard saves at once: 200 and 409, never 500 | same, PostgreSQL |
| An older tab editing a story through the target page: 409, newer text kept | same |
| Sign-out clears every draft key the source uses (a source scan) | `frontend/src/test/integration/offline.test.tsx` |
| Two browser contexts for one account plus another account: refresh, concurrent edits, sign-out, isolation | `frontend/e2e/persistence.spec.ts` |
| Every 409 `stale_revision` carries the saved version (stories, restore, target-page story, whiteboard, reflection, kit); another account gets 404, not the text | `backend/tests/test_conflict_versions.py`, `test_kits.py` |
| A slow save with typing during it: the typing stays and isn't called saved (stories, kits, application details); the next save sends it against the new version | `frontend/src/test/integration/stories.test.tsx`, `kit.test.tsx`, `applications.test.tsx` |
| Conflicts show both versions and keep what each choice promises (stories, kits, whiteboard, reflections) | same files, `whiteboard.test.tsx`, `reflection.test.tsx` |
| Restoring a copy kept against an older version compares first and saves nothing (stories, reflections) | `stories.test.tsx`, `reflection.test.tsx` |
| Storage refused: the page says so and offers Copy (notes, reflections) | `notes.test.tsx`, `reflection.test.tsx` |
| Typing during an answer send stays in the box | `keyedSends.test.tsx` |
| Leaving a dirty kit inside the app asks first, and staying keeps the edits | `kit.test.tsx` |
| Restart survival, roles, backups | [STORAGE.md](STORAGE.md), [BACKUP.md](BACKUP.md) |
