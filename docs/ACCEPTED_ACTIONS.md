# Accepted improvements: one improvement, one action

An interview review offers improvements worked out from the feedback ("Make your own part
clear", "Add a result you can point to"). Accepting one makes it an **action** with one id. The
plan page, the schedule and an interview kit's checklist all show that same action by its id, so
marking it done, moving it or renaming it in one place is what every other place shows.

This volume connects one source: improvements from an interview's replay. Reflection next steps
keep their own flow (docs/INTERVIEW_WORKFLOW.md); other sources can follow one at a time.

## Five things, kept apart

| | What it is | Where it lives | Who changes it |
|---|---|---|---|
| **Suggestion** | An improvement the review offers. Not chosen yet | Worked out from the feedback each time the review is read; never stored | Nobody: it follows the feedback |
| **Accepted action** | The learner's commitment, linked to the feedback it came from | `accepted_actions` (one row per accepted suggestion) | The learner: name, notes, once or weekly, done |
| **Occurrence** | A time on the schedule for it | `schedule_entries` with `kind = accepted_action` and `ref` = the action's id | The learner, on the schedule: move, cancel |
| **Attempt** | Practice actually done | The attempts' own tables (interview retries, coding submissions), counted, never edited | Practising |
| **Completion** | "I did this" | A one-off: `accepted_actions.done_at`. A weekly action: each occurrence's `completed_at` | The learner says so |

On screen: the review shows **Accept "…" as an action** (and, once accepted, "Accepted as an
action. See it on your plan"); the action shows where it came from, the practice related to it
since (below: evidence, never a claim that it was done or that it helped), its occurrences, and a
**Mark done** that is labelled as the learner's word. Completing an action changes no score and
says nothing about mastery.

## One identity

- The suggestion is the identity: (account, `interview_improvement`, interview id, improvement
  key) is unique. Accepting it again, from a double click, a second tab, at the same moment from
  two tabs, or a resend after a lost reply, returns the action already made (`200` instead of
  `201`). Two improvements with the same wording are still two actions; nothing is merged by
  wording.
- What the page sends is only *which* suggestion (interview id and key). The server reads the
  review as it builds it now and snapshots the improvement's title, the feedback it came from and
  the question versions of the answers, so the action keeps saying where it came from after the
  feedback rules change. The review and its results aren't touched.
- The improvement key is made from what the improvement is about (the rubric point or dimension
  it names, or its kind, such as unanswered questions), so it's the same each time the review is
  read while the feedback says the same thing.

## Where it shows

- **Plan page**: "Improvements you accepted", **beside** the plan, not inside it. The plan takes
  no hand-added steps and still adapts only to practice, as before (`backend/app/services/roadmap.py`, docs/PRACTICE_FLOW.md); an accepted
  action never becomes a plan step and doesn't change what the plan suggests. That's the
  deliberate decision for this volume.
- **Schedule**: each occurrence is an entry labelled "Accepted improvement" with the action's
  current name (read each time, never copied). A one-off's entry has **Mark done**, which marks
  the action; a weekly action's entry marks that week only.
- **Interview kit checklist**: "Add an improvement you accepted" adds an item that holds only the
  action's id (`origin: action`, `action_id`). Its words and its tick are the action's own: ticking
  it marks the action (no kit save), and renaming the action renames the item. Kit templates leave
  these items out.

## Occurrences and recurrence

- A **one-off** action is scheduled once. Scheduling it again while it's on the schedule is
  refused ("Already on your schedule on …. Move it there instead"). Moving the entry is the
  schedule's own move: same entry, same id, a higher `SEQUENCE` in the calendar file, one event.
- A **weekly** action is scheduled for 1–8 weeks at a time, one entry a week, each its own
  calendar event. Marking one week done leaves the others open; marking it not done restores it.
  "Mark done" on the action itself is refused for a weekly action (`weekly_action`).
- Once or weekly can change only while nothing is on the schedule for it and it isn't done
  (`has_occurrences`, `action_done`): changing what an occurrence means afterwards would rewrite
  history.
- Scheduling is repeat-safe (`client_request_id`; a weekly batch keys each week from it), within
  the schedule's own limit of entries.

## Edits

Name and notes are saved against the revision the page loaded. A stale save is refused
(`409 stale_revision`) with the saved action in `details.current`, and the page shows both
versions with "Keep mine" and "Use the saved one". A save whose reply was lost, sent again with
its key, is answered as saved (update receipts, docs/RECOVERY.md).

## Related practice (Volume 13, prompt 4)

On the plan's accepted improvements and on a kit checklist's improvement item: **Related practice
since you accepted it (2)**, opening a short list (`GET /api/v1/me/actions/{id}/practice`; both
pages show the same component reading this one endpoint, and neither keeps a copy).

- **Found only through stored links**, never by wording or by question alone: retries of the
  question the improvement came from in its source interview (`interview_retries` for that session
  and question index), and follow-ups to it (answers whose `follows_up_answer_id` is the original
  answer or one of its retries). Answering the same question on its own page, or another question,
  isn't related. Improvements whose practice isn't a retry of one question say "This kind of
  improvement has no practice linked to it yet".
- **Since it was accepted**: practice from before counts for nothing here (a follow-up made since,
  to a retry made before, does count).
- **Each attempt on its own**: what it was (Retry or Follow-up, with its own question's title), its
  date, its own score or "too short to score" (never zero), and the comparison rule's verdict
  against the attempt the improvement came from (docs/COMPARING_ATTEMPTS.md). A retry whose score
  compares says "lower than", "higher than" or "the same as" the original's; a follow-up is a
  different question, says so, and its score is never set beside the original's. Nothing is
  averaged.
- **Evidence, not a tick**: none of it marks the action done, moves an occurrence or changes the
  schedule; the list never says an improvement "worked". A disputed point's action still lists its
  practice, labelled.
- **Live**: read each time, so a deleted answer drops out and the count is one fewer (a follow-up
  whose earlier answer was deleted is unlinked, docs/FOLLOW_UPS.md, and drops out too).
- **Export**: each action carries `related_attempts` (answer ids, oldest first) in the version 2
  export, and `related_practice` (the count) in version 1. Another account's answers never appear,
  and another account's action is 404.

Tests: `backend/tests/test_related_practice.py`, `frontend/src/test/integration/actions.test.tsx`,
`frontend/e2e/related-practice.spec.ts` (against the real API).
Negative controls (each caught): matching by question instead of stored links; practice before
acceptance counted; another account's action readable; evidence ticking the action; a follow-up
shown as a retry; "too short" shown as a score; a disputed action unlabelled; the export without
the attempts; and on the pages, no list on the plan or in the kit, a follow-up's score set beside
the original's, "too short" shown as zero.

## Lifecycle and privacy

- Owner-only: every query is filtered by the account first, and on PostgreSQL row-level security
  backs that up (migration `d4a8b6c1f2e3`). Another account's action, occurrence or interview ids
  answer 404, the same as ids that don't exist.
- If the interview it came from is deleted, the action stays with what its feedback said and
  "That interview is no longer available" (retention follows the interview's own rules; the action
  holds a snapshot, not the answers).
- Exported in "Your data" (`accepted_actions`, with occurrences; version 2 adds ids and links:
  docs/BACKUP_FORMAT.md) and counted in the data summary. Deleted with the account. Not restored
  from a backup yet: accept them again from the review.
- No reminders or notifications beyond the schedule's existing calendar file.

## API

`/api/v1/me/actions`: `GET` (list), `POST` (accept: `{source: {interview_id, key}, recurrence}`),
`GET`/`PATCH /{id}`, `POST /{id}/complete`, `/{id}/reopen`, `/{id}/occurrences` (schedule),
`/{id}/occurrences/{entry_id}/complete` and `/reopen`.

## Limits

- One source (replay improvements). Reflection next steps and other feedback aren't actions yet.
- No delete or archive for an action yet; mark it done instead.
- "Practised since" counts retries of the question or submissions of the problem it points at; for
  an improvement without a practice target it isn't counted.
- Completion is the learner's word; linked evidence is shown as a count, never as completion.
