# New practice and "Update my plan"

When a learner has practised in ways the current plan version doesn't use, the plan says so in one
line and offers to update. Nothing updates by itself: reading the plan never makes a version for
this, and not pressing the button leaves the plan exactly as it is (Volume 13, prompt 1).

- Service: `backend/app/services/roadmap.py` (`_news`, `update`, `news_text`), the same planner as
  before; there's no second one.
- API: `GET /api/v1/me/plan` carries `news` (or `null`); `POST /api/v1/me/plan/update` with
  `{"version": <the version you saw>}` makes the next version.
- Interface: `frontend/src/features/plan/PlanNews.tsx`, on the plan page and the Today card.
- Tests: `backend/tests/test_plan_updates.py`, `frontend/src/test/integration/planNews.test.tsx`,
  `frontend/e2e/plan-updates.spec.ts`; `e2e/disputes.spec.ts` uses the button.

## When a version is made

| What happened | Before | Now |
|---|---|---|
| No plan yet | The first view makes version 1 | The same |
| Something in the plan is done (from evidence, or "reviewed") | The next view makes the next version | The same |
| Goals changed, or nothing is left open | The next view makes the next version | The same |
| Practice the plan doesn't use (an answer elsewhere, a finished round) | Nothing: it waited until one of the above (CI run 315 met this) | The plan names it and offers "Update my plan"; nothing is made until it's pressed |

## What counts as new

Since the version was made, and not used by any activity in it:

- **Answers** to career questions with a score that counts (`app/careers/eligibility.py`), written
  alone or inside a round. An answer that explicitly revises an earlier one is counted as a
  **retry**.
- **Finished question rounds** (a baseline, a practice round or a mock interview).
- **Judged coding submissions** (Volume 14, prompt 2), for a career with coding: submissions (not
  runs, which check the public tests only) that the judge gave a verdict on, named with it: "1
  submission (not passed) since this plan.", "3 submissions (2 not passed)", "2 submissions (both
  passed)". Attempts only saved (no judge on the server) and the judge's own failures aren't
  verdicts, so they aren't counted. A submission that completed a coding activity in the version is
  that activity's, not new. To see whether they change anything, the coding recommender reads the
  learner's submissions with these left out (`ProgressService.recommend(leave_out=...)`).

Not counted, and named as not counted when an update is offered:

- answers too short to score ("1 answer too short to score isn’t counted.");
- answers whose feedback as a whole the learner disputed (docs/DISPUTES.md).

Not counted at all yet: accepted improvements (they have their own section of the plan page and
the planner doesn't choose from them), lessons, reflections.

## Whether it changes anything

The planner answers that itself: `_news` plans twice, from the evidence with what's new and from the
same evidence without it (same goals, same disputes, same set-aside activities, same day), and offers
the update only when the activities chosen differ. So practice that changes nothing the planner uses
(a strong answer that moves no choice, an answer too short to score, a disputed answer) offers nothing,
and the version stays. A changed number inside a reason, with the same activities, doesn't offer one.

## The line

One line, counts only, oldest first in the details:

> **1 answer since this plan, below 70.** Your plan stays as it is until you update it.
> [Update my plan]

Variants: "2 answers since this plan, one below 70.", "2 answers (1 of them a retry) since this plan,
both below 70.", "3 answers and 1 finished round since this plan, all below 70." It describes what was
done and how it scored, never that anything improved. On the plan page a "What's new" list links each
answer and round; the Today card shows the line and the button only.

## Updating

`POST /api/v1/me/plan/update {"version": N}`:

- **N is the latest**: the normal next version from all the evidence, with its "what changed" notes.
  The first note says why: "Updated when you asked: 1 answer since version 1, below 70."; then the
  planner's own notes ("Added “Retry: …”: …", "Dropped …", "Moved … out …"). Every activity that
  leaves the plan gets a note; one whose round the learner had started also says "You'd started it:
  that round stays open, and what you answer in it is saved."
- **Another tab or device made a newer version first** (the version check, or two presses at the same
  moment meeting the unique version number): `409 plan_changed` with `details.version`, nothing made.
  The page says "Your plan was already updated, in another tab or on another device: this is version
  2." and shows it.
- **Nothing new changes it any more** (say, the answer was disputed in another tab): the same version,
  unchanged; the page says "Nothing to update: what's new no longer changes your plan."
- No plan yet: `409 plan_changed` with `details.version: null`.

After pressing, focus moves to the result line (the button is gone). Disputed feedback stays out of
the update as everywhere else: the version is built by the same `_new_version`.

## Boundaries

- Another account's practice never counts or shows: every query is the learner's own (and row-level
  security on PostgreSQL, docs/ROW_LEVEL_SECURITY.md).
- The plan describes evidence, not ability: no "improved", no readiness.
- Reading costs a little more: two statements on every view to find what's new since the version
  (the plan's query budget is 26, `tests/test_query_budgets.py`), and, only when there's something
  new, the planner runs twice more on that view.

## Negative controls (caught)

| Protection removed | Caught by |
|---|---|
| A view rebuilds the plan when there's news | `test_new_practice_is_named_and_the_plan_waits_until_asked`, `plan-updates.spec.ts` |
| The update isn't bound to the version seen | `test_two_tabs_updating_make_one_version_and_the_second_is_told`, `plan-updates.spec.ts`, `planNews.test.tsx` |
| Two presses at once: the second answered with the existing plan, not told | `test_two_tabs_pressing_at_the_same_moment_make_one_version` |
| Too-short answers counted | `test_evidence_the_planner_does_not_use_offers_no_update`, `plan-updates.spec.ts` |
| Disputed answers counted in the line | `test_evidence_the_planner_does_not_use_offers_no_update` (the count). In the browser this one isn't visible: the planner already leaves an answer disputed as a whole out, so counting it can't make an offer |
| Disputed answers both counted and read by the planner | `plan-updates.spec.ts` (an update is offered) |
| Offered without asking the planner whether anything changes | `test_practice_that_changes_nothing_the_planner_chooses_offers_nothing` |
| Another account's answers counted | `test_another_accounts_practice_never_counts_or_shows` |
| A started round's activity dropped without saying so | `test_dropping_an_activity_the_learner_started_says_so` |
| Rounds, or retries, not counted | `test_a_finished_round_and_its_answers_are_counted`, `test_a_revision_is_counted_as_a_retry` |
| A conflict shown as a failure; focus left behind; a no-op claimed as a new version; no line on Today; a failure not said | `planNews.test.tsx` (and Today: `plan-updates.spec.ts`) |

## Limits

- A judged submission's verdict is said as passed or not passed; the counts and the comparison are
  on the submission's own page.
- Whether the plan would change is decided by which activities are chosen, not their order or the
  numbers in their reasons.
- A dispute or its reinstatement isn't "new practice": it shows on the plan at once (labels) and
  shapes the next version, however that's made (docs/DISPUTES.md).
