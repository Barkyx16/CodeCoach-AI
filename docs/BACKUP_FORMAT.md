# Backups: the format, and restoring your own data

"Download my data" (Settings → Your data) gives a JSON file of everything CodeCoach stores about
the account. "Restore from a backup" brings part of such a file back into the account that's
signed in. This is portability of your own practice data, not a way to sign in, move an account
or copy someone else's.

## The format

- One JSON object, UTF-8, at most **5 MB**. No archives, paths or attachments are read, and nothing
  in it is executed.
- `export_version` (an integer) says which format it is. **Version 1** is the only one so far and
  the only one restore reads; any other value is refused with the supported versions listed.
  Older version-1 files that lack newer sections (for example `stories`) are fine: missing
  sections are simply empty.
- `exported_at` (ISO 8601) is informational.
- The file never contains a password, a password hash, a sign-in or refresh token, a share-link
  secret or a provider key. It does contain your email and display name in `profile`, and the
  text you wrote.

## What restore reads

| Section | Restored as | Duplicate when | If the content it points to is missing |
|---|---|---|---|
| `notes` | New notes (title, body, reflection, tags, excerpt, archived). Not pinned. | The same title, body and reflection is already a note | The note is kept; its link to the content is left out. Never relinked to something similar |
| `stories` | New stories (all the STAR fields, versions, competencies, tags), with a first saved version | The same title, situation, action and result | A career that doesn't exist is dropped from the story |
| `bookmarks` | Bookmarks on questions, problems or drills | The same item is already bookmarked | Skipped, with the reason |
| `applications` | Applications with their interview events, and a first stage-history entry "Restored from a backup" | The same employer, role, date applied and link | A time that's ambiguous or invalid in its time zone keeps the date only |

Each record is checked against the same limits as the app's own forms (lengths, `http(s)` links,
allowed stages and kinds). A record that fails is skipped and counted with its reason; unknown
fields inside a record are ignored and counted. Ids, owner ids, revision numbers and timestamps in
the file are never used: restored records get new ids, belong to the signed-in account, and are
dated now.

## What restore never reads

| Section | Why |
|---|---|
| `profile`, `onboarding` | Account details, sign-in and roles are never restored. The account stays exactly as it is, whatever the file says (an `is_admin` in a file changes nothing). |
| `submissions`, `practice_sessions`, `answers`, `ai_interactions`, `drill_attempts`, `whiteboard`, `scenario_attempts`, `learn_events`, `answer_reviews`, plans, goals and the review queue | Practice results and evaluations can't be verified from a file, so an edited backup can't create a passing verdict, a score, progress or readiness. |
| `shares`, `shared_feedback`, `schedule`, sessions | They could share data or start something (links, sessions, reminders). |
| `targets`, `collections`, `interview_kits`, `interview_reflections`, `content_reports` | Not restorable yet (they depend on other records by id); listed in the preview. |
| Anything else | Not recognised, ignored, and listed. |

## How a restore runs

1. **Preview** (`POST /api/v1/me/restore/preview`, the file as the body). Nothing changes. It shows,
   for each restorable section, how many records are in the file, how many are new, how many are
   already in the account, and what's skipped and why; everything that won't be restored; and
   whether this same file was restored before. If the file names a different account, the
   preview says so: only its content can come into yours.
2. **Choose** which sections to restore.
3. **Restore** (`POST /api/v1/me/restore?categories=…`, the same file). The whole batch is
   applied in **one transaction**: if anything fails part-way, nothing is changed and the batch
   is recorded as stopped; it can simply be tried again. The same file with the same choices
   again returns the first batch and adds nothing (`200`); a different file adds only what's not
   already there. Account limits (notes, stories, applications) are checked before anything is
   added.

Nothing is ever overwritten or replaced, so there's no destructive step and no re-authentication.

## Undoing a restore

"Your restores" lists every batch. **Remove what this added** deletes only the records that are
still exactly as they were restored; anything edited since is kept, and anything already deleted
is left alone. The result says how many were removed, kept and already gone. Removing again does
nothing more. Notes are removed with the notebook's own delete.

## Privacy

Restores are owner-only, recorded in the data export (`restores`), and deleted with the account.
The file's content isn't stored: only a fingerprint of the file (to recognise it again) and which
records each batch added.

## Verified, and not

See the V2-10 entry in [RESUME_LIFTER.md](../RESUME_LIFTER.md). Only synthetic test accounts and
files were used; no import was run against real users or a real database.
