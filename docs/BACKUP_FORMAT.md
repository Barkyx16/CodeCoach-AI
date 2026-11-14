# Backups: the format, and restoring your own data

"Download my data" (Settings → Your data) gives a JSON file of everything CodeCoach stores about
the account. "Restore from a backup" brings part of such a file back into the account that's
signed in. This is portability of your own practice data, not a way to sign in, move an account
or copy someone else's.

## The format

- One JSON object, UTF-8, at most **5 MB**. No archives, paths or attachments are read, and nothing
  in it is executed.
- `export_version` (an integer) says which format it is. **Version 1** is the default and the only
  one restore reads; version 2 (below) adds links between records and is refused by restore, like
  any other value, with the supported versions listed and nothing changed.
  Older version-1 files that lack newer sections (for example `stories`) are fine: missing
  sections are simply empty.
- `exported_at` (ISO 8601) is informational.
- The file never contains a password, a password hash, a sign-in or refresh token, a share-link
  secret or a provider key. It does contain your email and display name in `profile`, and the
  text you wrote.

## Version 2: the same data, with links between records (opt-in)

Settings → Your data → "Include links between records" (or `GET /api/v1/me/export?version=2`)
downloads version 2. It's the version 1 document with every section and field unchanged, plus:

- `export_version: 2` and an `identities` note (scope, restore support, the link states).
- An `id` on the records others point to: applications, their `events`, `target_roles` and their
  `requirements`, `stories` (already had one), `notes`, `schedule.entries`, `accepted_actions`,
  `interview_kits` and `interview_reflections` (each identified by its interview event's id),
  reflection `actions`, and `bookmarks` (`question:career/id`, made from fields already there).
- A `links` object on the records that point to others, each link a typed reference:

```json
{"type": "story", "id": "6f1c…", "state": "present"}
```

| Record | `links` |
|---|---|
| application | `target`, `stories[]` |
| interview kit | `event`, `stories[]` (each with `version_when_chosen`: a number, or `"unknown"` for kits saved before versions were kept), `actions[]`: the accepted improvements on its checklist |
| interview reflection | `application`, `event`, `stories[]` |
| reflection step (`actions[]`) | `created`: the note, schedule entry or bookmark it made, or `null` if it wasn't accepted |
| schedule entry | `activity`: the interview event, a question/problem/drill, a plan/review item, or an accepted action |
| accepted action | `source`: the interview it came from (`not_exported`); `occurrences[]`: its schedule entries |
| note | `source`: the lesson, question, problem or practice session it was written from |

| `state` | Meaning |
|---|---|
| `present` | The target is in this file, with that type and id |
| `missing` | The target isn't in the account any more (deleted, or a note in the bin), or isn't this account's. The link is kept as history; nothing is made up to fill it |
| `public` | Library content (question, problem, lesson, drill) named by its public id |
| `not_exported` | The account's own record in a section without ids in this format (plan activities, review queue, practice sessions) |
| `unknown` | Not recorded |

**Identity scope.** An id is the record's id in this account: unique per type within one file,
opaque, not stable across accounts, and never a credential or proof of ownership. `present` is
decided from the file's own contents, and a link to another account's record is `missing` (its
existence isn't revealed).

**Consistency.** The file is read in one database session, but on PostgreSQL a concurrent edit
can appear in one section and not another: it isn't a point-in-time snapshot. Links never claim
a target the file doesn't contain.

**Check a file** (read-only): `python -m app.cli check-export codecoach-data-v2.json`. It reports
missing or duplicate ids, unknown types or states, malformed links, links that say `present`
but point nowhere (`dangling`) or to another kind of record (`wrong_type`), and links that say a
target isn't here when it is (`inconsistent_state`). It can't tell whose a file is, and it changes
nothing.

| | Version 1 | Version 2 |
|---|---|---|
| Default download | yes | opt-in |
| All data and fields | yes | yes (the same fields) |
| Ids and links between records | stories only | yes |
| Restore | yes (the sections below) | **no**: refused before anything is read or written ("Download a version 1 export to restore") |

**Privacy.** Both versions are your own complete data: they include private details kept out of
printouts (a kit's meeting link, interviewer names, private notes). They never include request
keys, sign-in tokens, password hashes, share secrets or server settings.

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
| `submissions`, `practice_sessions`, `answers`, `ai_interactions`, `drill_attempts`, `whiteboard`, `code_reviews`, `test_design_runs`, `work_samples`, `comparisons`, `offer_rehearsals`, `offer_comparisons` (not restored: re-enter them), `scenario_attempts`, `learn_events`, `answer_reviews`, plans, goals and the review queue | Practice results and evaluations can't be verified from a file, so an edited backup can't create a passing verdict, a score, progress or readiness. |
| `shares`, `shared_feedback`, `schedule`, sessions | They could share data or start something (links, sessions, reminders). |
| `targets`, `collections`, `interview_kits`, `kit_templates`, `accepted_actions`, `interview_reflections`, `content_reports` | Not restorable yet (they depend on other records by id); listed in the preview. |
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
