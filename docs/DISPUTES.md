# Disputed feedback: what a dispute changes

When a learner disagrees with a point of their feedback, that point stops shaping what the plan
suggests until they count it again. What happened stays as it happened (Volume 12, prompt 7).

- Which disputes stand: `backend/app/services/disputes.py` (`Disputes.active`, `covering`, `note`).
- Where the plan uses them: `backend/app/services/roadmap.py` (`_evidence`, `_generate`,
  `_new_version`).
- Scope: feedback on career written answers, read by the adaptive plan. Other feedback sources
  (coding verdicts, drills, interview-wide summaries, the review queue) don't read disputes yet.

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
  Labels go at once; the point can shape suggestions again from the plan's next update (after
  practice, a goal change or when the plan runs out), and a "Not suggested" line says so.

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
recommendation rules for now; the review queue orders by score only and doesn't read disputes.
