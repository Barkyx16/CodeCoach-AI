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
  passed)". Attempts only saved (no judge on the server) aren't verdicts, so they aren't counted. A
  submission that completed a coding activity in the version is that activity's, not new. To see
  whether they change anything, the coding recommender reads the learner's submissions with these
  left out (`ProgressService.recommend(leave_out=...)`).
- **Judged debugging exercises** (Volume 16, prompt 7), by the same rule: a submission to an
  exercise counts for the skills the exercise names (its topics after "debugging" itself), in the
  weak-topic and difficulty-ladder rules exactly as a problem's does. An exercise is never suggested
  itself: the plan's coding activities are problems.
- **Lesson checks passed** (Volume 17, prompt 3): a Learn lesson of this career whose check
  (graded by its rubric: every answer right) was passed since the version, on the lesson's current
  version, once per lesson. It counts for the lesson's skill, named "Lesson check passed: <lesson>"
  and in the skill's sentence ("the check passed on the lesson “SBAR handoffs”"), never as mastery.
  The planner already reads passed checks (it doesn't suggest a lesson whose check you've passed);
  to see what a new one moves, it plans without it as well. A check that completed one of the
  version's own lesson activities is that activity's, not new (the plan moves on by itself then);
  one passed before the version was evidence already. Starting or reading a lesson, or a check not
  passed, never counts.

How code counts, said under the preview whenever code is among what's new: "How code counts: a pass
counts as solved; failed tests, errors and time or memory limits count as tried, not solved. A
verdict is never turned into a score." Each submission is named with its verdict in the judge's
terms (`verdict_detail`: passed, tests failed, compile error, runtime error, time limit exceeded,
memory limit exceeded) and never a score (`score` stays null).

Not counted, and named as not counted when an update is offered:

- answers too short to score ("1 answer too short to score isn’t counted.");
- answers whose feedback as a whole the learner disputed (docs/DISPUTES.md);
- submissions the judge couldn't run (`INTERNAL_ERROR`: its own problem, not the learner's code):
  "1 submission the judge couldn't run isn’t counted: that was a problem on the judge's side, not
  your code." (Volume 16, prompt 7). The plan doesn't read one as an attempt anywhere: the coding
  recommender leaves it out (so it never asks to "finish" a problem the judge failed on), and it
  doesn't complete a coding activity.

A lesson check passed on a version the lesson has since replaced isn't counted, and is said: "1
lesson check passed on a version the lesson has since replaced isn’t counted: pass its current
version."

Not counted, by design: **accepted improvements**. They're kept beside the plan, never as steps, and
don't change what it suggests (docs/ACCEPTED_ACTIONS.md, a deliberate decision); the practice they
lead to (an answer, a submission) counts like any other. Reflections aren't counted either. The plan
page says which evidence the plan reads, in a sentence from the server (`evidence_read`): "This plan
reads your scored answers to Software Engineer questions, your finished question rounds and the
lesson checks you've passed, and the judge's verdicts on code you submit: to problems, and to
debugging exercises for the skills they name (not runs, which check the public tests only). A lesson
only read, or a check not passed, isn't evidence. Improvements you accept are kept beside the plan
and don't change what it suggests; the practice they lead to does." A career without coding says the
first part only.

## What each skill's evidence would move

The preview groups what's new by skill (`news.by_skill`, Volume 16, prompt 7), oldest first, in one
sentence each: what's new, what it counts as, and what the next version would suggest or stop
suggesting because of it.

> Arrays: “Contains Duplicate” passed, which counts as solved, so the next version would suggest
> “Solve: First Unique Character” and not “Solve: Find Largest Number”.
>
> Hash-sets: “Contains Duplicate” passed, which counts as solved, so the next version would suggest
> “Solve: First Unique Character” and not “Solve: Find Largest Number”.

A skill is a question's skill, each of a problem's topics, each of an exercise's topics after
"debugging", a lesson's skill, or the kind of round ("Interview practice", "Baseline").

**Each skill on its own** (Volume 17, prompt 9). For each skill with new evidence, the planner is
asked once more without that skill's new evidence, and that plan is compared with the plan with all
of it: what differs is the skill's line. So a problem with two topics moves both topics' lines (it's
evidence for each, as the planner reads it), and a line says only what that skill's evidence would
move by itself. Before this, the planner was asked twice (with and without all of what's new) and
each difference was put on a skill by what it was for, so a problem counted for its first topic only.

- **What only skills together move** is said once, as before: "From all of it together, the next
  version also wouldn't suggest “Solve: Find Largest Number”." With Contains Duplicate passed and
  Valid Parentheses failing to compile, leaving out either alone still leaves the other taking Find
  Largest Number's place; only without both does it come back.
- **A skill whose own evidence moves nothing** says so, in the same words: "Arrays: “Contains
  Duplicate” passed, which counts as solved; on its own that changes nothing the plan chooses."
- **The bound** is the plan's own limit on items, `MAX_ITEMS` (8: `SKILLS_ASKED_ALONE`). Past it, the
  remaining skills are asked about together, in one more plan, and said together, with how many:
  "The other 6 skills together (dynamic-programming, …): …" (`skills` lists them; `skill` is
  null). Nine skills are all asked about alone: the "rest" would be that one skill. At most 11 plans
  are made (with and without all of it, eight alone, the rest).
- **Made in memory.** The evidence's rows (answers' ids and scores, finished rounds, spoken turns,
  passed lessons) and the code's facts (problems, submissions, coaching, progress events) are read
  once; each plan is built from them. The preview's plans don't read a weak answer's feedback: it
  words an item (what it missed) and never chooses one, so the plans choose exactly what the full
  plan would (a test compares them). With 14 skills new, the plan request now runs 31 statements on
  SQLite and 34 on PostgreSQL, against 41 and 44 before (two plans then, eleven now); the number
  doesn't change with how many skills are asked about (a test asks with the bound at 1 and at 8).
- **The plan an update applies** is the same as before: only the preview's lines changed.

**Time**, measured on the whole `GET /me/plan` with 14 skills new (eight weak answers, three passed
problems on six topics), the test client in one process, the same machine, the commit before and
this one alternated: SQLite, median of 25 requests, three rounds: 55.0, 56.8 and 62.0 ms before,
68.9, 66.9 and 68.4 ms after (planning in memory costs more than SQLite's in-process statements
save); PostgreSQL, two rounds: 103.3 and 103.3 ms before, 90.4 and 92.6 ms after (ten fewer round
trips). **Budget:** no more than 1.25 times the median before on either database: 1.17 on SQLite and
0.88 on PostgreSQL. With fewer skills new, fewer plans are made.

## A debugging exercise not fixed yet

Since Volume 18, prompt 7, a debugging exercise tried and not fixed brings the lesson that prepares
the exercises, **Fixing code from a failing test** (`se-failing-test`; docs/ATTEMPT_CONDITIONS.md),
when the plan reads code (a software engineer's plan with coding among its formats):

> **Learn: Fixing code from a failing test** · 7 min
> A 7-minute lesson that prepares the debugging exercises, because “Fix: Coldest Reading” isn't fixed
> yet. Pass the lesson's comprehension check. Reading it alone doesn't count.

- Tried means a submission (submit, not run) the judge judged and didn't pass: failed tests, a
  compile error, a time-out. One the judge couldn't run isn't an attempt, as everywhere in the plan.
  An exercise passed since is fixed, and doesn't bring it.
- It names the most recent exercise not fixed. The exercise itself is never suggested: it's evidence
  for its skills, not an activity.
- One lesson at a time, as before: a lesson for a weak skill or a chosen focus skill comes first, and
  this one waits until there's none. Its check passed, it isn't suggested again.
- **A skipped lesson waits a week**, as a skipped question or problem does: no version in the next 7
  days suggests it again, by its unit. Before, every lesson came straight back in the next version
  after a skip; now a skipped focus-skill lesson makes way for the next lesson, this one included.
- It's on the skill "debugging exercises", not the written-answer skill "debugging" (whose lesson is
  **Explaining how you debug**), so it's never placed before a retry it doesn't prepare.
- The plan reads the code once for this and its coding suggestions (`fact_rows` once per version,
  counted by a test); the update preview, which asks the planner with and without what's new, says it
  in the skill's sentence: "Arrays: the debugging exercise “Fix: Coldest Reading” didn't pass (tests
  failed), which counts as tried, not solved, so the next version would suggest “Learn: Fixing code
  from a failing test” and “Solve: Contains Duplicate” and not “Solve: Valid Palindrome”."

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

The version an update makes records the judged submissions it read, by id, oldest first
(`practice_plans.read_submissions`, migration `d4a9b2e6f137`; Volume 16, prompt 7): `[]` for an
update that read no code, null for a version made otherwise (an activity done, goals changed) and
for every version from before. The plan response lists them (`read_submissions`: id, title, verdict,
whether an exercise, link; one statement, only for such a version; one no longer stored is listed
by id), the "Your plan changed" panel shows "Code this update read as new evidence", and the export
carries the ids on each version (`practice_plans[].read_submissions`). A version from before reads
exactly as it did. It records the lesson checks it read the same way (`practice_plans.read_lessons`,
migration `f7a3c5e9b264`; Volume 17, prompt 3): `[{unit_id, version}]`, listed on the plan
(`read_lessons`: the lesson's title and link from the catalog, "A lesson that's no longer offered"
otherwise) under "Lesson checks this update read as new evidence", and in the export. Not pressing
changes nothing: no version, no item, nothing applied later.

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
| Runs counted; another career reading code; the judge's failure counted, read as an attempt or completing an activity; a verdict as a score; exercises not read, or suggested; what an update read not recorded or not exported; another account's code counted; moves not put on their skill (Volume 16, prompt 7) | `tests/test_plan_code_evidence.py` (13) |
| The skill sentences, the rule, the verdict's own words, an exercise's name, the code an update read or what the plan reads not shown | `planCodeEvidence.test.tsx` |
| The debugging lesson never suggested; suggested with its check passed, for a fixed exercise, for a problem that isn't an exercise, beside another lesson, or naming the oldest exercise; the code read twice; put on the written-answer skill; a skipped lesson not held back (by either lesson rule, or held back for ever) (Volume 18, prompt 7) | `tests/test_plan_debug_lesson.py` (12) |

## Limits

- A judged submission's verdict is said in the judge's terms; the counts and the comparison are on
  the submission's own page.
- An activity is put on a skill by what it's for, not by asking the planner once per skill: when
  several skills' evidence together moves an activity that isn't on any one of them, it's said once
  for all of it. A problem counts for its first topic in the preview; the planner's rules read all
  its topics.
- The debugging lesson (above) waits behind any other lesson, so with a weak skill that has its own
  lesson it isn't suggested until that one's check is passed or it's skipped.
- Whether the plan would change is decided by which activities are chosen, not their order or the
  numbers in their reasons.
- A dispute or its reinstatement isn't "new practice": it shows on the plan at once (labels) and
  shapes the next version, however that's made (docs/DISPUTES.md).
