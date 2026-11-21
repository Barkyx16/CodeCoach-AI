# Archive and delete: know the effects before you choose

Before an archive or a delete, the learner sees what will be archived, deleted, unlinked, kept or
made unavailable. The list comes from the same planning function that then carries the action out
(Volume 12, prompt 9).

- The planner: `backend/app/services/lifecycle.py` (`Lifecycle.plan_delete_application`,
  `plan_archive_note`, `plan_delete_story`, `plan_delete_note`, `plan_archive_target`,
  `plan_archive_action`, `plan_delete_action`, `plan_archive_story`, `plan_archive_application`,
  `plan_delete_account`, and the matching `delete_application`, `archive_note`, `delete_story`,
  `delete_note`, `archive_target`, `archive_action`, `delete_action`, `archive_story` and
  `archive_application`; the account's delete stays in `DELETE /auth/me`, bound to its plan).
- The preview: `frontend/src/features/lifecycle/ImpactPreview.tsx`, on the application page
  (**Archive…** and **Delete…**), the note page (**Archive…** and **Delete…**), the story page
  (**Archive…** and **Delete…**), the target workspace (**Archive…**) and each accepted improvement
  on the plan page (**Archive…** and **Delete…**); its list (`ImpactList`) in Settings → Danger
  zone (**Show what would be deleted**), reached from the privacy view's **Delete my account**.
- Scope: **deleting an application** and **archiving a note** (Volume 12, prompt 9); **deleting a
  story**, **deleting a note** (with its undo window) and **archiving a target** (Volume 13, prompt
  5); **archiving** and **deleting an accepted improvement** (Volume 14, prompt 5;
  docs/ACCEPTED_ACTIONS.md, "Archive and delete"); **archiving a story**, **archiving an
  application** and **deleting the account** (Volume 14, prompt 6). No lifecycle action in the app
  happens without its list first. **Unarchive** and a note's **Undo** have none: they put back
  what the list said was kept.
- The older routes carry out the same plan, as it is when they're called: `DELETE
  /me/stories/{id}`, `DELETE /me/notes/{id}`, `PATCH /targets/{id}` with `archived: true`, and
  `POST /me/stories/{id}/archive` and `/me/applications/{id}/archive` do exactly what the preview
  would list. `DELETE /auth/me` without `expected_fingerprint` (an older client) deletes as it
  always did; with it, it's refused when the list changed.

## One plan, used twice

1. **Preview** (`GET …/delete-preview`, `GET …/archive-preview`): the planner works out every one
   of the learner's records the action touches and returns them by kind and title, each with its
   effect, a one-line summary in words, notes on what it can't do, and a **fingerprint** of the
   plan. Nothing is changed.
2. **Carry out** (`POST …/delete`, `POST …/archive`, with `expected_fingerprint` and a request key):
   the planner runs again, with ownership and relationships checked again. If the new plan's
   fingerprint isn't the one previewed, nothing is done: the answer is 409 `impact_changed` with the
   new plan in `details.current`, and the page shows it ("What this affects changed since you
   looked. Nothing was done: check the list again."). If it matches, exactly what's listed is done,
   in one transaction, and the answer is the plan as carried out.

The fingerprint covers each item's effect, kind, id and title: an item added, removed, renamed or
moved to another effect changes it. The previewed list and the outcome are the same list, item for
item (tested by looking each one up afterwards).

Older clients that call `DELETE /api/v1/me/applications/{id}` or set `archived` on a note directly
get the same plan, worked out at that moment (no fingerprint to compare), and the same changes.

## Effect types

| Effect | Means | Reversible? |
|---|---|---|
| **archived** | Hidden from the usual lists; nothing is erased. | Yes: Unarchive. |
| **deleted** | Removed from the account. No undo window for applications or stories. | No, except a note: Undo for 10 minutes. |
| **unlinked** | The link goes; the other record stays exactly as it is. | The link can be made again by hand. |
| **kept** | Not touched: listed so it's clear it stays. | n/a |
| **unavailable** | Stays, but what it pointed at is gone, so it says "no longer available". | n/a |

### Deleting an application

| What | Effect |
|---|---|
| The application, with its notes and stage history | deleted |
| Each interview event | deleted |
| Each event's interview-day kit (checklist, questions, chosen examples, what it kept from them, and its story decisions) | deleted |
| Each event's reflection, with its suggested and accepted next steps | deleted |
| What an accepted next step made: a note, a schedule entry, a saved question | kept |
| Stories chosen for the application, its kits or its reflections | unlinked (they stay in the story bank) |
| Accepted improvements on a kit's checklist | unlinked (they stay on the plan page and the schedule) |
| Preparation entries on the schedule for its events | unavailable: they stay on the schedule, marked no longer available, until removed there |
| Offer comparisons that named it | unlinked: the comparison keeps the figures entered for that offer, without the link (and its revision moves on, so another tab's save gets the usual stale-save choice) |

The summary names the reach: "Delete this application, its 3 events, 1 kit and 1 reflection"; with
nothing else, "Delete this application". The notes say "This can't be undone. Archive keeps it out
of the way instead." and "Backups you made before now still hold a copy until you delete them."

Before this, an offer comparison that named a deleted application couldn't be opened (it answered
"Application not found"). The delete now unlinks it.

### Archiving a note

| What | Effect |
|---|---|
| The note | archived: hidden from the notes list, Continue and search unless archived notes are included; still opens, still in the export, can still go in a practice packet |
| Its pin, if pinned | unlinked: unarchiving doesn't pin it again |
| A reflection's next step that made it | kept: still done; the note is still there |

A note that's already archived previews "This note is already archived" with nothing to do.

### Deleting a story

| What | Effect |
|---|---|
| The story, with its saved versions | deleted |
| Each link to a target's requirement, with the review decisions about it | deleted (the requirement stays on its target) |
| Each interview-day kit that chose it | kept: the kit keeps what it prepared from the story, as it was, until removed there ("Remove it from this kit"; docs/STORY_FRESHNESS.md) |
| Applications that list it | unlinked (they stay in your applications; before this, the deleted story's id stayed on them, unlisted, and the version 2 export showed it as a missing link) |
| Reflections that list it | unavailable: each stays and keeps what it recorded, saying "A story you linked was deleted from your story bank since." (as before) |
| Practice answers that rehearsed it | unlinked: each keeps its text and score, without naming the story |

The summary names the reach: "Delete this story, its 1 requirement link and its revisions"; with
nothing else, "Delete this story, its revisions" (a story always has at least its first version).
The notes are the application's: it can't be undone, Archive keeps it out of the way instead, and
backups made before now still hold a copy. A story's create key is kept like an application's, so
a late retry of the create that made it is refused (410 `deleted_earlier`) instead of making it
again.

### Deleting a note

| What | Effect |
|---|---|
| The note | deleted, restorable for 10 minutes (Undo) exactly as it is now; after that it's removed from CodeCoach |
| Its pin, if pinned | kept: Undo brings it back pinned |
| A reflection's next step that made it | kept: still done |
| Practice packets | kept: a packet is made when asked for, so a deleted note just isn't offered; one already saved keeps its copy |

The outcome carries `restorable_until`; the notes list then says "Deleted “Handover phrases”. You
can undo this until 14:05; after that it's removed from CodeCoach." and offers **Undo** until that
time (the browser's clock; the server decides). Before this, deleting a pinned note unpinned it, so
Undo brought it back different; it's kept now. A deleted note isn't in the export.

### Archiving a target

| What | Effect |
|---|---|
| The target | archived: hidden from the targets list; still opens; in the export |
| Being the active target, if it was | unlinked: unarchiving doesn't make it active again |
| Each requirement (not removed ones) | kept, with its versions |
| Stories written for it or linked to it | kept, still linked |
| Applications linked to it | kept, still linked |
| Accepted improvements listed with its requirements | kept: still on the plan and the schedule |
| Answers and rounds practised for it | kept: they stay in your history and still count |

Archiving is reversible: **Unarchive** brings it back as it was (not as the active target). A target
that's already archived previews "This target is already archived" with everything kept.

### Archiving and deleting an accepted improvement

| What | Archive | Delete |
|---|---|---|
| The improvement | archived: off the plan's list, the schedule and Today | deleted, with its notes and marks of done |
| Each occurrence, done or not | kept, with its marks of done | deleted |
| A kit's checklist item naming it | kept, labelled archived | kept, as "An improvement you removed" |
| A target requirement it's listed with | kept, still listed | unlinked |
| The interview review's suggestion | kept, still accepted | kept; it can be accepted again |
| Practice done with it | kept | kept |

**Unarchive** brings it back with its occurrences. A deleted one comes back from a version 2 backup
with the same ids (docs/BACKUP_FORMAT.md).

### Archiving a story

| What | Effect |
|---|---|
| The story | archived: out of the story bank's list (under Archived); it still opens, in the export |
| Each link to a target's requirement | kept: still linked; the target labels the story archived |
| Each interview-day kit that chose it | kept: it keeps what it prepared from the story, and shows the story as archived |
| Applications that list it | kept: still listed, marked archived |
| Reflections that name it | kept |
| Practice answers that rehearsed it | kept: each keeps its text and score, and still names it |

Nothing is unlinked, so **Unarchive** brings it back exactly as it was (the same list, previewed
again, is identical; `test_archiving_a_story_lists_what_keeps_it_and_unarchive_brings_it_back`).

### Archiving an application

| What | Effect |
|---|---|
| The application | archived: out of the applications list, the board and the upcoming list; still opens |
| Each interview event | kept, with its date and stage |
| Each event's interview-day kit and reflection | kept, as prepared |
| Schedule entries for its events | kept, but **off the schedule and Today while it's archived**; back when you unarchive it |
| Offer comparisons that name it | kept: they still compare it |

An interview still to come gets a warning above the list: archiving doesn't cancel it or change the
stage. Until this prompt, an archived application's interviews stayed on the schedule and Today;
now its events' entries are hidden there (`backend/app/services/schedule.py`, `_archived_events`)
and come back unchanged on **Unarchive** (`test_archiving_an_application_takes_its_interviews_off_the_schedule_until_unarchived`).
A calendar file downloaded earlier keeps its events.

### Deleting the account

The list comes first (Settings → Danger zone → **Show what would be deleted**); the password and
typing DELETE stay, and **Delete my account** is disabled until the list is shown. The delete
carries the list's fingerprint: anything added or removed since is refused with the new list
("Something changed since you looked. Nothing was deleted"), and nothing is deleted.

| What | Effect |
|---|---|
| The account: email, name, career and password hash | deleted |
| Every category on the privacy view with something in it, with its count (`Notes: 3`, …) | deleted: the counts are the privacy view's own (`data_summary`), not a second tally, and equal what is removed (`test_the_account_preview_counts_equal_what_goes_and_a_change_since_is_refused`) |
| Emails waiting to be sent (pending, sending or held) | deleted: "Cancelled: never sent." (the outbox rows go with the account, so the worker can't pick them up; one already being sent finds no account and sends nothing) |
| Links you shared that still open (closed ones included: closing only stops feedback) | deleted: "They stop working at once." |
| Signed-in devices (each sign-in family) | deleted: "Every device is signed out." |

And what remains, said as notes:

- "This can't be undone, and CodeCoach can't restore it for you."
- Backups made before now keep a copy until they age out: with the default rotation
  (docs/BACKUP.md) and nightly backups, the last of them by the first day of the third month after
  the deletion (`backups_age_out_by`; for 15 November 2026, 2027-02-01). That's the worst case,
  when no backup runs after the deletion before the month ends; it's checked against the rotation
  code itself (`test_the_age_out_date_matches_the_rotation_itself`). If backups stop, or the server
  keeps more, copies stay longer, and the note says so. It never says backups vanish at once.
- A data export you downloaded is yours to delete.

Afterwards signing in fails, the old token is refused and a shared link answers 404
(`test_after_deleting_as_previewed_sign_in_fails_the_link_is_gone_and_no_email_is_left`;
`frontend/e2e/account-deletion.spec.ts`, at desktop and phone width). What deletion removes didn't
change, with one correction found by the preview: the list first counted only links that weren't
closed, though a closed link still opens; it now counts every link that isn't revoked or expired.

## What can't bring it back

- **A retried request** (`client_request_id`): the first one leaves a receipt; the same key again
  answers with what was done (`replayed: true`, "This was already done; nothing was done again."),
  never does it twice. The same key for another action or record is refused (409
  `idempotency_key_reused`). A refused request (a changed scope) leaves no receipt, so the key isn't
  spent.
- **A late retry of the create** (the browser keeps unconfirmed requests for a day): deleting an
  application or a story records its create key, so that create sent again is refused with 410
  `deleted_earlier` instead of making it again. A create with a new key makes a new one, as
  always.
- **Another tab or a request in flight**: adding an event, saving its kit or reflection, accepting a
  reflection's next step, or scheduling preparation for a deleted application's event answers 404.
  Two deletes at once: the second waits for the first (a row lock on PostgreSQL), then answers with
  the first's receipt if it's the same request, or 404.
- Nothing runs in the background for an application, a note, a story or a target (no judge run, no
  queued email), so there's nothing in flight to finish later. For the account, queued emails go
  with it and a judge result that arrives later is discarded (docs/PRIVACY.md, "Deletion, step by
  step").

## Privacy and retention

- Only the learner's own records are read or listed. Another account's id gets the same 404 as one
  that doesn't exist, from the preview and from carrying it out, and none of their records is
  listed or counted, even one that names this account's records.
- Receipts (`lifecycle_receipts`) keep what was done by kind and id, never titles or text, so the
  words of what was deleted don't stay behind. They go after 7 days (housekeeping), with the create
  keys of deleted applications. They're counted under **Recovery records** on Your data, aren't in
  the export, go with the account, and are copied by a database move (so a late create retry
  still isn't made again after it). Like `update_receipts` they're outside row-level security (no
  content; purged across learners by housekeeping); every lookup filters by the learner.
- The wording never calls archiving, unlinking or a scheduled clean-up permanent erasure. Deleting
  removes the records from the account; copies in backups made earlier age out with those backups
  (docs/BACKUP.md), and emails already delivered can't be recalled.

## On the page

The **Delete…** and **Archive…** buttons open the list under them (nothing is sent until the button
is pressed). Focus moves to "What this will do" when the list arrives, and again if it changes. The
button names the action and its reach ("Delete this application, its 2 events and 1 kit", "Archive
this note"); **Cancel** closes it. After a delete the page goes to Your applications, where the
outcome has focus: "Deleted Ward nurse at Mercy General. With it went its 2 events and 1 kit.
Everything listed as kept or unlinked is where it was." After an archive the note page says
"Archived Handover phrases. It's hidden from your notes list, Continue and search; nothing is
erased. Unarchive brings it back." with focus on it.

The story page's **Delete…** and the note page's **Delete…** replace the browser's confirm box
(the list is the confirmation); after either, the page goes to the list (the notes list offers
Undo). The target workspace's **Archive…** opens the list under the header; after it, "Archived ED
Nurse. Unarchive it any time. It's hidden from your targets list; its requirements, stories and
practice are kept." has focus, and **Unarchive** (no preview: it hides nothing) takes its place.

## API

- `GET /api/v1/me/applications/{id}/delete-preview` → `Impact`
- `POST /api/v1/me/applications/{id}/delete` `{expected_fingerprint, client_request_id?}` →
  `LifecycleOutcome` (409 `impact_changed`, 404, 409 `idempotency_key_reused`)
- `GET /api/v1/me/notes/{id}/archive-preview` → `Impact`
- `POST /api/v1/me/notes/{id}/archive` `{expected_fingerprint, client_request_id?}` → `LifecycleOutcome`
- `GET /api/v1/me/notes/{id}/delete-preview` → `Impact`; `POST /api/v1/me/notes/{id}/delete` →
  `LifecycleOutcome` with `restorable_until`; `POST /api/v1/me/notes/{id}/restore` is Undo
- `GET /api/v1/me/stories/{id}/delete-preview` → `Impact`; `POST /api/v1/me/stories/{id}/delete` →
  `LifecycleOutcome`
- `GET /api/v1/targets/{id}/archive-preview` → `Impact`; `POST /api/v1/targets/{id}/archive` →
  `LifecycleOutcome`
- `GET /api/v1/me/stories/{id}/archive-preview` → `Impact`; `POST
  /api/v1/me/stories/{id}/archive-as-previewed` `{expected_fingerprint, client_request_id?}` →
  `LifecycleOutcome` (the older `POST .../archive` still returns the story)
- `GET /api/v1/me/applications/{id}/archive-preview` → `Impact`; `POST
  /api/v1/me/applications/{id}/archive-as-previewed` → `LifecycleOutcome` (the older `POST
  .../archive` still returns the application)
- `GET /api/v1/auth/me/delete-preview` → `Impact`; `DELETE /api/v1/auth/me` `{password, confirm,
  expected_fingerprint?}` → 204 (409 `impact_changed` with `details.current`, 400 without DELETE,
  401 with the wrong password)
- `Impact` = `{action, target_id, title, summary, effects: [{effect, kind, title, id, note}], notes,
  fingerprint}`; `LifecycleOutcome` adds `done_at`, `replayed`, `message` and `restorable_until`
  (a deleted note only).
