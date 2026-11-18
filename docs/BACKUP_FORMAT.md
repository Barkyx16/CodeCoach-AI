# Backups: the format, and restoring your own data

"Download my data" (Settings → Your data) gives a JSON file of everything CodeCoach stores about
the account. "Restore from a backup" brings part of such a file back into the account that's
signed in. This is portability of your own practice data, not a way to sign in, move an account
or copy someone else's.

## The format

- One JSON object, UTF-8, at most **5 MB**. No archives, paths or attachments are read, and nothing
  in it is executed.
- `export_version` (an integer) says which format it is. **Version 1** is the default; version 2
  (below) adds links between records. Restore reads both (version 2 since Volume 14, prompt 5, which
  also brings back accepted improvements by id); any other value is refused with the supported
  versions listed and nothing changed.
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
nothing. Since Volume 19, prompt 9 it also checks test-design runs' ids (`test_design_run`): a file
exported before then has runs without ids, and the check says so (`missing_id`).

| | Version 1 | Version 2 |
|---|---|---|
| Default download | yes | opt-in |
| All data and fields | yes | yes (the same fields) |
| Ids and links between records | stories only | yes |
| Restore | yes (the sections below) | yes: the same sections, plus accepted improvements (Volume 14, prompt 5) and collections (Volume 15, prompt 6), which need the ids only a version 2 file keeps |

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
| `collections` (version 2 files only) | Collections with their name and queue (its position, and when it started), and their items in the order of each item's `position` (not where it sits in the file), each with the version it was added at (only one the source has had; otherwise "not known", never the version now), its mark of done in the queue (never later than now) and its "Mark reviewed" (`source_reviews`). Under the collection's and each item's id in the file when the file is this account's and no one has the id; otherwise new ids (Volume 15, prompt 6) | The same collection (by id) is already here: never overwritten, counted as already there. Another collection with the same name (spacing and capitals aside): skipped and said ("it's never overwritten or merged") | An item whose question, problem or drill left the library is left out with the reason (never swapped for a similar one); a retired one is kept and shown as unavailable, as the collection shows it today; the same item twice in one collection is kept once. Items name library content, not bookmarks, so nothing of another account is ever linked |
| `listed_names` (Volume 16, prompt 4) | Names you listed, each replaced with [name] wherever something leaves the app (docs/PRIVACY.md), with the time each was added | The same name in any letter case and spacing is already listed | The list holds up to 100: names over the limit are left out and counted ("Over the list's limit of 100 names"), never named. A name the list couldn't hold (no letter, too long) is skipped with the reason. Version 1 and 2 files alike: a name needs no id |
| `dismissed_suggestions` (Volume 16, prompt 4) | Suggestions you dismissed, not offered again on any device, with the time each was dismissed | The same suggestion (its key) is already dismissed | A suggestion that's no longer offered (its question retired, its pair removed) is left out with the reason, never matched to a similar one. Version 1 and 2 files alike |
| `review_queue` (Volume 20, prompt 1) | Which questions you saved for review, each as a new item starting afresh: the ladder's first rung, first due 1 day after the restore, no score, no reviews and no points, as saving the question now would make it. Nothing else in the record is read: its `step`, `due_at`, `last_score`, `reviews`, `saved_for_points` and `points_removed` come from answers, and a file can't prove those happened here, so an edited file can't create progress. The preview says so beside the category (`note`). Version 1 and 2 files alike | The same question (career and question) is already in the queue: left exactly as it is | A question no longer in the library is left out with the reason, never swapped for a similar one. One removed from the queue when the file was made is left out ("Removed from the queue when the file was made"); one you removed here stays removed ("put it back from Removed recently"). The queue holds up to 100 questions: a restore that would go over it changes nothing and says so |
| `accepted_actions` (version 2 files only) | Accepted improvements with their notes, recurrence, marks of done and archive date, under the id in the file, and their occurrences from `schedule.entries` (date, time, time zone, length, status and marks of done), under theirs; requirement reuse only for requirements in this account (Volume 14, prompt 5) | One from the same suggestion (interview and improvement key) is already there | Its interview isn't in this account: skipped with the reason. An id already used elsewhere gets a new one |

Each record is checked against the same limits as the app's own forms (lengths, `http(s)` links,
allowed stages and kinds). A record that fails is skipped and counted with its reason; unknown
fields inside a record are ignored and counted. Ids, owner ids, revision numbers and timestamps in
the file are never used: restored records get new ids, belong to the signed-in account, and are
dated now. The exception is accepted improvements from a version 2 file: they keep their ids (so
the kits and requirement links that name them find them again) and their marks of done (never later
than now), but still belong to the signed-in account and need its interview; and collections from a
version 2 file of this account, which keep their ids, their items' ids and their queue. A file from
another account brings collections in under new ids, so another account's ids are never restored
into this one (even after that account deleted them).

## What restore never reads

| Section | Why |
|---|---|
| `profile`, `onboarding` | Account details, sign-in and roles are never restored. The account stays exactly as it is, whatever the file says (an `is_admin` in a file changes nothing). |
| `submissions`, `practice_sessions`, `answers`, `ai_interactions`, `drill_attempts`, `whiteboard`, `code_reviews`, `test_design_runs`, `work_samples`, `comparisons`, `offer_rehearsals`, `offer_comparisons` (not restored: re-enter them), `scenario_attempts`, `learn_events`, `answer_reviews`, plans, goals, and the review queue's ladders, scores and points (only which questions were saved comes back, above) | Practice results and evaluations can't be verified from a file, so an edited backup can't create a passing verdict, a score, progress or readiness. |
| `shares`, `shared_feedback`, `schedule`, sessions | They could share data or start something (links, sessions, reminders). |
| `targets`, `interview_kits`, `kit_templates`, `interview_reflections`, `content_reports` | Not restorable yet (they depend on other records by id); listed in the preview. `accepted_actions` and `collections` in a version 1 file (no ids) are listed as skipped: restore them from a version 2 file. |
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
nothing more. Notes are removed with the notebook's own delete. A collection counts as changed if it
was renamed, reordered, its queue moved, an item was added, removed, marked done or reviewed since;
the collections kept for that are named (`removal.kept_collections`), and removing one takes its
items and their reviews with it. A name renamed since is kept; a suggestion offered again since is
already gone, so it stays offered. A question saved for review counts as changed if it was practised, snoozed, given a point or
planned in the schedule since, and is kept; one removed from the queue since is already gone.

## Privacy

Restores are owner-only, recorded in the data export (`restores`), and deleted with the account.
The file's content isn't stored: only a fingerprint of the file (to recognise it again) and which
records each batch added. For a name, that record is a digest, never the name, and the preview,
the result and the batch say how many, never which; no name reaches a log or a trace
(`tests/test_restore_choices.py`).

## Verified, and not

See the V2-10 entry in [RESUME_LIFTER.md](../RESUME_LIFTER.md). Only synthetic test accounts and
files were used; no import was run against real users or a real database.
