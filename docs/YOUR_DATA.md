# Your data: what's stored, where, and clearing this device

Volume 10, prompt 10. One page, **Settings → Privacy & data → See your data** (`/settings/data`),
also "Your data" in the command palette and Help. It describes the app as it's built, from the
code; it isn't a legal certification. The full map is [PRIVACY.md](PRIVACY.md).

## On this device

This account's copies in this browser (prefixes in `auth/localWork.ts`, what each is in
`features/privacy/copyKinds.ts`, loaded with this page only), each shown by what it
is, its size in words (lines for code), when it was kept if the copy records it, and a link to its
page. **Never its content.** Two groups, so a local draft can't be mistaken for a save:

- **Not sent yet: only on this device**: answers, code, lesson and drill answers, quick notes,
  debugging-lab notes, sample-answer marks, work-queue orders, offer-rehearsal turns, untested test
  cases, interview answers, messages and retries. Removing one deletes that text.
- **Unsaved changes: your account keeps the last saved version**: notes, stories, diagrams,
  reflections, code reviews, work samples, offer comparisons, application notes and unfinished
  forms. Removing one leaves the saved version (a new item never saved is gone).

Also listed and removable:

- **Actions waiting for a reply** (`lib/pendingIntents.ts`): kind, problem name where public, and
  when; no content. Removing one means that if its reply was lost, the page can't ask the server
  what happened after a reload, and sending again may save it twice; the review says so.
- **Pages opened recently, for Go to**: a count of names.

Described, not removed here: display, editor and voice settings (device settings); the dashboard's
shortcuts (page ids per account, kept at sign-out; Reset to defaults clears them, [SHORTCUTS.md](SHORTCUTS.md)); public pages
saved for offline (`/offline` removes them); the sign-in cookie (this page can't read it, and
signing out ends it); which account last used the device; this tab's list positions.

Interview drafts are keyed by interview, not account: only the ones for this account's interviews
are listed (read from the interview list, summaries only). Another account's copies are never
listed or removed.

### Removing precisely (`lib/deviceCopies.ts`)

Choose items, **Review removal** (what goes, what stays on the account, the consequence for pending
actions), then **Remove**. Only those keys are removed, from this browser only: nothing else in
storage, not the sign-in, not the account. The result is said in words and focused, including
anything the browser refused.

A page still open with a removed copy (this tab or another) doesn't put it back. Every draft writer
writes through `writeCopy(key, value, since)`, where `since` is the removal count when that page
opened its copy (`useCopySince`). Removals are numbered in order across this browser's tabs
(`codecoach.removed.v2`: key, number and time, never content), so an autosave timer, an effect
re-running after a refetch, or a flush when the tab is hidden is refused once its copy was removed
after the page opened it. The page keeps the text on screen and says it isn't kept on this device
(pages with unsent text warn before leaving). Opening the page again starts a new copy. Sign-out
drops the list; the counter only grows. A test lists every file that writes to storage directly, so
a new draft writer can't bypass this.

If the browser won't let the page use storage (private browsing, blocked site data), it says so
and lists nothing.

## Saved to your account

`GET /api/v1/me/data-summary` (`app/services/data_summary.py`): one `COUNT(*)` per table of the
caller's own rows, grouped as your work, shared and reported, and your account and sign-in, with a
note where it matters (a dictated answer is stored as text and no audio reaches CodeCoach; a deleted
note is kept 10 minutes to undo; shared answers are readable by anyone with a working link; sign-in
records are hashes; an email's content is cleared once sent). No text, title or amount is read to
count (a test captures the statements). Every table holding a learner's rows is placed in exactly one
category (a test fails on a new table that isn't). Owner-only; anonymous callers get 401.

**Every attempt in the export has its id** (Volume 19, prompt 9): the id History and the attempt's
own page name it by, and its conditions (the help before it), so a record in the file can be matched
with the app. Test-design runs now carry theirs too: id, status and its detail, cases, report, when
it was made and judged, the words its list uses (`outcome_text`), its conditions (from the same
function as the bulk route History uses, so the two can't differ) and its comparison with the run
before (`compared`, in the contract's words, or `not_compared`); offer rehearsals carry their id,
which a retry's `parent_id` names. `app/services/export_walk.py` names, for every section, which
field identifies its attempts or why it holds none; a test walks a real export and fails on any
attempt without its id, on an attempt section without its conditions, on any record with
`conditions` but no id, and on a section the walk doesn't name, so a format added later can't be
left out. The practice-labs line here says what each attempt is exported with. Additive: the export
stays version 1 by default and version 2 on request; a backup file still doesn't restore practice
results (test-design runs included) and says so.

The export's `comparison_openings` now say how each was first seen (`source`: `opened`, or
`with_result` when the explanation was shown with a reading's result; Volume 20, prompt 3).

A backup file now brings back which questions you saved for review (Volume 20, prompt 1;
docs/BACKUP_FORMAT.md): each as a new item starting afresh, first due a day after the restore. Their
ladders, due dates, scores, review counts and points stay with the account they came from, and the
restore's preview says so beside the category.

Export, restore and deletion stay where they are: the page links to Settings' **Download my data**,
**Restore from a backup** and **Danger zone** (password and "DELETE"), and Settings now moves focus
to the section a link names. No new way to export or delete.

Deleting the account shows its list first (Volume 14, prompt 6): **Show what would be deleted** in
the Danger zone lists these same counts, read by the same code (`data_summary`), plus the emails
that won't be sent, the links that stop working, the devices signed out, and when copies in
earlier backups age out (docs/LIFECYCLE.md, "Deleting the account"). It reads at phone width.

Suggestions you dismissed with "Not now" are kept with your account too (Volume 15, prompt 2;
docs/FOLLOW_UPS.md, "Not now"): Settings lists them and can offer any of them again, the export
carries them, and deleting the account removes them. A follow-up question's "Not now" and "Your
plan changed" used to be kept in this browser only; on the first signed-in page load they're moved
to the account and cleared from the browser.

## Where your words go when they're processed

- **The AI coach**: with the built-in coach, nothing is sent to an AI provider. With an outside
  provider (`AI_PROVIDER=anthropic`), hints, code reviews, failed-test explanations and the coding
  interviewer send the problem, your code and the interview so far, with secret-looking strings
  removed; each can be checked before it's sent (docs/COACH_CONTEXT.md). CodeCoach keeps the reply,
  never the request. **How long the provider keeps it: not known
  to CodeCoach**, and deleting your account can't erase the provider's copy. Written answers,
  question rounds and the practice labs are checked by fixed rules whichever coach is set.
- **Dictation**: off until you press the microphone; typing works everywhere. The browser turns
  speech into text (Chrome and Edge through their maker's service, Safari possibly on the device);
  **how long that service keeps audio: not known to CodeCoach**. CodeCoach receives only text. The
  page says whether this browser offers dictation.
- **The interviewer's voice**: the browser's voices read questions aloud when that setting is on
  (shown, with a link to change it); some voices are online and receive the question's text.
- **Email**: codes and notices through the configured mail service; a sent email can't be recalled.

No new toggles: the options shown are the ones that already change behaviour.

## Limits

- Counts, not a per-record list: Download my data is the complete copy.
- What the AI provider, the browser's speech service or the mail service keep isn't known to
  CodeCoach and isn't erased by it. Server backups keep a copy until they age out (PRIVACY.md).
- A page open in another tab when its copy is removed keeps the text on screen, unsaved anywhere,
  until it's sent, saved or left; it can't keep a device copy again until it's opened again.
- Interview drafts of another account (left by a session that ended without signing out) aren't
  listed; they're cleared when that account signs out here.
- Removal records over a day old are dropped when the next removal is recorded; a page left open
  longer than that with an older copy could keep it again.
