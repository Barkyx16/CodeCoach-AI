# Disputed feedback: what a dispute changes

When a learner disagrees with a point of their feedback, that point stops shaping what the plan
suggests until they count it again. What happened stays as it happened (Volume 12, prompt 7).

- Which disputes stand: `backend/app/services/disputes.py` (`Disputes.active`, `covering`, `note`).
- Where the plan uses them: `backend/app/services/roadmap.py` (`_evidence`, `_generate`,
  `_new_version`).
- Scope: feedback on career written answers. Read, through the same `covering` (and `overall`, for
  an answer's feedback as a whole), by every place that reuses that advice; see "Every place that
  reads a dispute" below (Volume 14, prompt 9).

## Every place that reads a dispute

| Place | What a dispute changes there | What it says |
|---|---|---|
| The adaptive plan (`roadmap.py`) | as described below | "Not suggested (n): Left out because of feedback you disputed …" |
| An interview's summary, "Work on next" (`review.py`) | a point missed in an answer you disputed it on (or disputed overall) is still counted, but isn't used as evidence or to choose the retry; a point missed only where it's disputed isn't suggested at all, unless you'd already accepted it (it stays, with its dispute said) | "Missing in 3 of 3 answers, one disputed." with the dispute linked; under **Not suggested (n)**: "Not suggested: “…” (missing in 2 of 4 answers, all disputed). Left out because of feedback you disputed, not because there's nothing to practise." |
| The review queue (`review_queue.py`) | an answer whose score is disputed for an item doesn't move its ladder, whenever it was counted: the ladder is recounted from the item's answers without it (see "The review queue" below). For an item saved for one point or several, a dispute on any of them counts like a dispute overall, for that item only. An item whose every reason is disputed (saved from an interview answer you disputed, and not answered since except in answers you disputed) isn't scheduled: it's listed under **You disputed this**, with "Count it again (see the dispute)" and "Answer it anyway". An item with any other reason keeps its schedule | "Recounted: one earlier score was disputed, so it's due in 3 days, not 7."; "Not scheduled: you saved it from an interview answer whose feedback you disputed …" (or "…, for “…”, and you disputed that point …"); a kept item: "One reason it's here is feedback you disputed …; it's scheduled for its other reasons." |
| Today and the schedule's "things to schedule" | follow the queue, by the same reading (`ReviewQueueService.ladders`): an item it doesn't schedule isn't counted as due or offered, and a recounted item is due when the recount says | (the queue's own words) |
| Accepted improvements | labelled, never moved (Volume 12, prompt 7) | "It stays as it is; it's yours to keep, move or mark done." |
| Drills | nothing to read: a drill's feedback is its own (each attempt, against the drill's checklist), no drill reuses an answer's feedback, and drill feedback can't be disputed | |

A dispute on one point doesn't dispute an answer's score, except for a queue item saved for that
point: there it counts like a dispute on the feedback overall. The feedback, scores and history
never change; the export marks what was left out, by id (`interviews[].points_left_out_disputed`,
the keys the summary didn't suggest; `review_queue[].left_out_disputed`, and `recounted` with the
ladder as the queue shows it). Counting the feedback again restores each place
at once (everything is read live). Another account's disputes never apply: a flag can only be made
on your own answer (404 otherwise), and every place reads only your own.

## The review queue

Volume 15, prompt 9. An item's ladder (1, 3, 7, 14, 30 days) is kept as it's counted: every answer
to its question since it was last scheduled moves it, in order, by the score rule (85+ up a step,
below 70 back to the first, in between the same), whatever was disputed. What the queue, Today, the
schedule and the export show is read from that by one function (`review_queue.ladder`):

- With no dispute on any answer since the item was saved, it's the stored ladder.
- Otherwise it's **recounted** from the item's answers since it was saved, oldest first, leaving
  out each one whose score is disputed for this item. The rule is the same whenever the answer was
  counted or the dispute made, so an item counted before Volume 14, prompt 9 (its stored step
  already moved by an answer now disputed) comes out the same as one counted after. Nothing is
  rewritten: the stored ladder, the answers, their scores and the feedback stay as they were.
- When the recount changes when it's due, the item says so, as the last sentence of why it's due
  (and in `recounted`): "Recounted: one earlier score was disputed, so it's due in 3 days, not
  7." It never moves an item earlier, or later, without that sentence.
- A snooze still holds: the recount never brings an item back before the day you snoozed it to.
- Withdrawing the dispute ("Count it again") shows the stored ladder again at once.

**Saved for one point.** "Save this point for review", under a point to work on in an interview's
summary, saves the question its retry targets for that point (`review_items.criterion`, migration
`f5b9d3e7a1c4`; an item saved for the whole answer, as every item before this, has none). For that
item a dispute on that point counts like a dispute on the whole feedback: it holds the item when
it's the only reason it's here, and leaves that answer's score out of the recount. A dispute on
another point of the same answer doesn't. The queue says what each item was saved for ("Saved for
“…”."), and the recount sentence names the point ("one earlier score was disputed (on “…”, the
point it was saved for)").

**Saved for several points** (Volume 16, prompt 5). A question is one item, and saving it again for
another point adds that point to it and says so ("Added “B” to the points it's saved for.";
`review_items.points`, migration `c3f8a1d5e926`, the points in the order added). Saving it for the
whole answer makes it a whole-answer item ("It's now saved for the whole answer, not only for “A”
and “B”."); a whole-answer item saved for a point stays whole ("It's already saved for the whole
answer, which covers every point."). The same point again changes nothing. A dispute on **any** of
its points leaves that answer's score out of the recount, and the item is held when every reason
it's here is disputed, as before. The queue lists the points, and with several each has "Remove this
point" (`DELETE /me/reviews/{id}/points?point=…`): the item stays with its other points, and scores
disputed only on that point count again; its last point can't be removed (remove the question
instead). The recount sentence names each disputed point it left out ("two earlier scores were
disputed, on “A” and “B”"); with one, it reads as before. An item from before this keeps its one
point in `criterion` with no `points`, and reads exactly as it did: nothing was rewritten. The export
lists every point (`review_queue[].saved_for_points`, beside `saved_for_point`, the first). Review
items still aren't restored from a backup file (docs/BACKUP_FORMAT.md), so neither are their points.
In the interview summary, a question already in the queue offers "Add this point to its review".

**Which point, by name** (Volume 17, prompt 8). With several points saved and one disputed, the
recount names it and the points the item stays for: "one earlier score was disputed (on “B”, one of
the points it's saved for; it stays for “A”)"; with every saved point disputed, "(on “B” and “A”,
every point it's saved for)", the points in the order they were disputed. With one point it reads
as before, word for word ("(on “A”, the point it was saved for)"). The recount reads the points the
item has now.

**Removing a point.** From the review queue and from the interview summary ("Remove this point",
`DELETE /me/reviews/{id}/points?point=…`), one point comes off and the item keeps its ladder (due
date, step, reviews, last score) and its other points. Its last point is the question's place in
the queue: the control says so first ("“A” is the only point “…” is saved for, so removing it takes
the question out of your review queue. Its answers, scores and any disputes stay."), takes it out
(`DELETE /me/reviews/{id}`; the point endpoint still answers 409 `last_point`), and offers **Undo**
(`POST /me/reviews/{id}/restore`), which puts it back as it was, ladder and points; refused with 409
`already_in_queue` once the question was saved again, and 404 for another account's item.

**Undo for every removal** (Volume 18, prompt 1). The queue's own **Remove**, on a scheduled
question or one there only for disputed feedback, now offers the same Undo: "Took “…” out of your
review queue. Its answers, scores and any disputes stay." with **Undo**, which puts it back as it
was. The Remove button goes with its row, so the keyboard's place moves to Undo. A refused Undo
says why ("It's back in your review queue already: it was saved again.") and changes nothing; a
second Undo of one already back changes nothing either (the restore answers with the queue as it
is). The Undo lasts while the page is open; after a reload, saving the question again is the way
back (its history is kept). Tests: `reviewQueueUndo.test.tsx` (3), the summary's Undo words in
`reviewRecount.test.tsx`; negative controls 4, all caught.

A removed point is kept in the item's history with its date (`review_items.removed_points`,
`[{point, at}]`, migration `a8c2e4f6b195`; `removed_points` on the queue item: "“B” was removed on
…"). It no longer holds a date back, and when a dispute on it would have, the item says why its
score counts again ("“B” was taken off on Nov 16, so one disputed score on it counts again.").
Saving the point again puts it back, and its history stays. Removing a point never touches an
answer, its score or its dispute. The export carries the points as they are now and the removed
ones with their dates (`review_queue[].saved_for_points`, `points_removed`); a backup file still
doesn't restore the review queue (docs/BACKUP_FORMAT.md), so neither are its points.

Reading stays bounded: the answers to every item's question come from one query (only the columns
the ladder needs), so a long history doesn't add statements (a test reads an item with a hundred
answers, half disputed, in the same statements as one). Only this account's answers and disputes
are read; on PostgreSQL row-level security keeps it so even if that query lost its owner filter (a
test drops the filter and checks).

## What counts as a dispute

A dispute is an **"I disagree"** flag on one point of an answer's feedback, or on the feedback
overall, that the learner hasn't counted again. The flag already existed (docs/RUBRIC_TRANSPARENCY.md,
"Disagreeing"); what's new is that it now does something, and the flag panel says what:

> Disputed on 3 November: this point doesn't shape your plan until you count it again.
> [Count it in my plan again]

- **"It's unclear"** isn't a dispute: it changes nothing.
- **Report a problem** about the question itself is a separate flow (content reports) and isn't a
  dispute either.
- Changing an "I disagree" to "It's unclear", or removing the flag, ends the dispute too; both are
  the learner's own action.

## What a dispute changes

| | Before the plan exists | After suggestions exist |
|---|---|---|
| A retry or review of the question | not suggested if that answer's feedback is disputed overall and nothing else makes the question weak | stays, labelled "Based on feedback you disputed on 3 November: “Backs it up with a concrete example”." with the dispute linked |
| The points a retry names ("it missed …") | a disputed point isn't named; the next undisputed ones are | as above |
| A focus or lesson suggestion | an answer disputed overall doesn't count toward its skill's average | labelled when it was derived from that answer |
| An accepted improvement | | stays where it is, labelled: "It stays as it is; it's yours to keep, move or mark done." |
| A scheduled entry (a plan activity or an accepted improvement) | | stays scheduled, labelled, never cancelled |

The plan says in one line what it didn't suggest, so a dispute isn't mistaken for a gap in the
content:

> **Not suggested (1)**: Left out because of feedback you disputed, not because there's nothing to practise.
> Not suggested: adding “Backs it up with a concrete example” to “What good patient assessment looks like”: you disputed this point on 3 November. [See the dispute]

## What a dispute doesn't change

- The feedback, word for word; the score; the rating; any judge verdict; any earlier evaluation.
- Anything already done or committed to: accepted improvements and schedule entries are never
  deleted, moved or cancelled.
- Similar suggestions: a dispute is about one point of one answer. The same point missed in
  another, undisputed answer still counts, as does any other undisputed feedback and every
  deterministic result.
- Nothing calls an AI provider because of a dispute.

## Derivation records

Each plan activity records what it came from: `plan_items.derived_from`, a list of
`{answer_id, criterion}`, the criterion a point's label or `"Overall"` (that answer's score and
feedback as a whole). Only activities derived from a disputed point (or from an answer disputed
overall) are labelled. Activities from before derivations were recorded have none (`null`) and
aren't labelled: what they came from isn't guessed.

Accepted improvements come from an interview's feedback point (`source_key` `point:<label>`): one
is labelled when that point, or that feedback overall, is disputed on any of that interview's
answers. Improvements that came from no point ("answer the questions you didn't get to") aren't.

What a version didn't suggest is kept with it (`practice_plans.withheld`), so the same lines show
after a reload and on another device.

## Timing

- **Disputed before planning**: the next version never suggests from it.
- **Disputed after suggestions exist**: nothing is regenerated or removed; exactly the derived
  activities are labelled, read live from the disputes as they stand.
- **Disputed while a version is being worked out** (another tab, another device): the version is
  checked against the disputes just before it's published and worked out again if they changed
  (up to three times).
- **A version built before a dispute** isn't reused: the next one is worked out from the disputes
  as they stand. The plan keeps no other summary of feedback.
- **Counting it again** is a button, never automatic. It records when (`answer_flags.reinstated_at`);
  the flag and its note stay ("You disagreed", "Counted in your plan again since 5 November").
  Labels go at once; the point can shape suggestions again from the plan's next version (when work
  in it is done, the goals change, the plan runs out, or the learner updates it for new practice:
  docs/PLAN_UPDATES.md), and a "Not suggested" line says so. A dispute or a reinstatement on its own
  isn't new practice and offers no update.

## Data

Dates are worded the same everywhere ("on 3 November") and are the calendar day in UTC, so the
flag, the plan's labels and its "Not suggested" lines never name different days. Close to midnight
that can be a day off from the learner's own calendar.

- `answer_flags.disputed_at`: when the flag became "I disagree" (`null` for flags from before this
  was recorded: shown as "the date wasn't recorded"). `reinstated_at`: when the learner counted it
  again.
- `plan_items.derived_from` and `practice_plans.withheld`: above.
- The export carries each flag's `disputed_at` and `reinstated_at`, each plan activity's
  `derived_from` and each version's withheld lines. Disputes, like flags, belong to the account:
  another account's answers and flags are refused (404).

## Not covered

Coding verdicts, drills, whiteboards, work samples and interview-wide summaries keep their own
recommendation rules for now.
