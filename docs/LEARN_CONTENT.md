# Learn mode content: authoring and review

Learn units are short lessons that teach a skill before it's assessed. They're plain Python data in
[`backend/app/learn/units.py`](../backend/app/learn/units.py), validated by
`backend/tests/test_learn.py`. No model is called to show or grade a unit.

## Coverage (honest)

| Career | Units |
| --- | --- |
| Software Engineer | Hash maps for fast lookup · Sliding windows (needs hash maps first) · Explaining how you debug |
| Registered Nurse | STAR answers · SBAR for handoffs and escalation · Prioritizing several patients (needs SBAR first) |

Every other career shows "no lessons yet" instead of borrowing another career's units.

## What a unit contains

`Unit` (see `backend/app/learn/__init__.py`): `id`, `track`, `version` and `changes`, `title`,
`skill` (one of the career's skills, which links it to the practice plan, or `None`), coding
`topics`, `minutes`, `objective`, `prerequisites` (unit ids, same career), `explanation`, one
worked `example` (optional code), `mistakes`, an `exercise` (prompt, the four guided steps:
a question to think about, the concept, an example, the fuller explanation; and a `solution`
kept hidden until requested), a multiple-choice `check` (answers never leave the server before an
attempt), a `practice` action (a real question or problem id), `references`, `review`, an
optional `scope_note` for regulated careers, and `question_ids` it prepares for.

## Rules

1. **Small and specific.** One skill, 5–10 minutes. Don't claim to cover a whole topic.
2. **Real references only.** Cite documents you have read. If you don't know a stable link, set
   `url=None` and say how to find it in `note`; never guess a URL. Repository references point at
   the code or data the unit relies on. A unit with no outside references says so on the page.
3. **Review status is a claim.** `author_reviewed` means someone checked the unit against its
   references. Anything drafted by a model and not yet checked must be `generated_draft`; the page
   shows a "Generated draft: not reviewed yet" badge. Don't invent reviewers or credentials.
   A format with no structured review, such as a test-design exercise, says it in its note: a note
   saying its review is owed ("Its review is owed: not yet reviewed by the project author") is
   listed as owed in the review report whatever checks it also names (Volume 20, prompt 9: Count
   Pairs, drafted with an AI coding assistant and machine-checked).
   Since Volume 18, prompt 8, every lesson link carries its `review_status` too (`UnitLink`:
   "Learn first" and prerequisites), so a draft's "Learn first" link says "Draft: not reviewed",
   and the practice plan's reason for a draft it suggests ends "It's a generated draft, not
   reviewed yet." **Fixing code from a failing test** (`se-failing-test`) is the one draft: it was
   written in this repository with an AI coding assistant (Volume 17, prompt 5) and was labelled
   `author_reviewed` when nobody had reviewed it; that was corrected here. Its review is the
   project author's to do: check it against its references and the three exercises, then set
   `review=_AUTHOR_REVIEW` with that day's date (no version bump: the meaning doesn't change).
   Since Volume 19, prompt 7, the content gate (`validate-content`) refuses a lesson or scenario whose
   review says `author_reviewed` while naming a drafting tool (an AI assistant, a model, "generated",
   "drafted") as its reviewer.
4. **Regulated careers.** Nursing and similar units carry a `scope_note`: interview education, not
   clinical guidance, with jurisdiction and facility policy named. Keep patient details generic.
5. **Versioning.** Bump `version` and append to `changes` when the meaning changes (a fix, a new
   check question, a different example). Learner progress is stored per version, so history is
   kept and the page tells returning learners what changed. A page still showing an older version
   gets `409 unit_changed` instead of recording against the wrong version.
6. **Progress means something.** Events are `started`, `read`, `check_attempted`,
   `check_passed` (every answer right) and `practiced` (a real answer or submission to the linked
   practice after starting). Reading or passing the check never marks a problem solved or a skill
   validated; the practice plan only counts a lesson as done when its check is passed.

## What's still owed a review

`python -m app.cli content review-status` (Volume 19, prompt 7; `app/content/review_status.py`)
lists every content item with its format, id, title, version and review status, read from the
content files as they are, and where its review note lives (the file and the field), in three
groups:

- **Review owed**: drafted and not yet checked: a lesson or scenario whose review says
  `generated_draft`, or a note that names no check.
- **Reviewed**, with what the note says the review was: the author's review, machine-checked,
  checked for consistency, or a dated check (no reviewer named); and "no outside review" when the
  note says so.
- **No review recorded**: drills and whiteboard prompts (no review field), and the generated banks:
  career questions counted per career, by the status their labels record ("Generated by
  CodeCoach's question templates; not reviewed by a subject-matter expert"), and the coding problem
  bank.

Nothing is inferred or upgraded: a kind is named only when its note says it, and a note naming no
check is listed as owed. `--owed` prints only what's owed (and any claim with no check here); `--json` prints the same report for a
script. It's a report, not a gate: it exits 0 whatever it finds, and CI's content-gate step runs it
(`--owed`) so its output is in every run's log. It changes no status: marking something reviewed
stays the author's act, in the file the line names.

**A claim names its check** (Volume 20, prompt 8). A note that says "machine-checked" is listed as
reviewed only when its format is in `MACHINE_CHECKS` (`app/content/review_status.py`), one table
naming, for each such format, the test and the command in this repository that do the check, the
CI steps that run them, and what the check proves; the report prints that under the item and
`--json` carries it (`check`). A claim in a format with no mapped check is listed apart, **Claimed
machine-checked, no check found here**, never among the reviewed; `--owed` prints it with what's
owed, so CI's content-gate step logs what isn't backed. Every other format is named in
`NO_MACHINE_CHECK` with why (an author's review is never reported as machine-checked). The report
runs no check itself.

| Format | What its check proves | The test | The command | CI steps that run them |
|---|---|---|---|---|
| debugging exercise | the faulty starter fails exactly its reproduction cases, and the repair and every alternative pass every test | `tests/test_debugging_lab.py::test_each_starter_shows_its_defect_and_each_repair_passes` | `python scripts/verify_reference_solutions.py` | Backend › Tests (SQLite); Backend › Reference solutions pass every seeded test |
| code-review exercise | the reviewed code fails exactly the public tests its defects cite, with the results they state, and the repair passes every test | `tests/test_code_reviews.py::test_each_authored_review_matches_what_the_code_does_on_the_tests` | the same | the same |
| test-design exercise | every faulty version differs from the reference on its own witness case, and the reference gives each example's expected output | `tests/test_test_design.py::test_every_exercise_passes_the_jdk_check` | the same | the same |

(The Backend job installs a JDK, so the `@java` tests run there; a test checks it.) Today's `--owed`, with the third test-design exercise (Volume 20, prompt 9) owed its review and naming its machine check:

```
Review owed (drafted and not yet checked): 2
  lesson · se-failing-test v1 · Fixing code from a failing test
      drafted, not yet reviewed by the project author. generated_draft (Drafted in this repository with an AI coding assistant, 2026-11-16). Checked against the debugging exercises' tests and the references listed, and by a test that no exercise's defect is in its words. Not yet reviewed by the project author or an outside expert.
      note: backend/app/learn/units.py: review
  test-design exercise · tests-count-pairs v1 · Test design: Count Pairs
      drafted, its review owed; machine-checked. Drafted in this repository with an AI coding assistant, 2026-11-18, and machine-checked: the reference and every faulty version were compiled and run with a real JDK, and each version's defect was shown on a case. Its review is owed: not yet reviewed by the project author.
      check: every faulty version differs from the reference on its own witness case, and the reference gives each example's expected output
        by backend/tests/test_test_design.py::test_every_exercise_passes_the_jdk_check and `python scripts/verify_reference_solutions.py`
        run in CI: Backend (lint, types, SQLite tests, reference solutions) › Tests (SQLite); Backend (lint, types, SQLite tests, reference solutions) › Reference solutions pass every seeded test
      note: backend/app/seed/testdesign/003-tests-count-pairs.json: review_status

Claimed machine-checked, no check found here: 0

This is a report of what the content says, not a review: marking something reviewed is the author's act.
```

and one machine-checked item from the full report:

```
  test-design exercise · tests-count-in-range v1 · Test design: Count in Range
      machine-checked. Written for practice and machine-checked: the reference and every faulty version were compiled and run with a real JDK, and each version's defect was shown on a case.
      check: every faulty version differs from the reference on its own witness case, and the reference gives each example's expected output
        by backend/tests/test_test_design.py::test_every_exercise_passes_the_jdk_check and `python scripts/verify_reference_solutions.py`
        run in CI: Backend (lint, types, SQLite tests, reference solutions) › Tests (SQLite); Backend (lint, types, SQLite tests, reference solutions) › Reference solutions pass every seeded test
      note: backend/app/seed/testdesign/001-tests-count-in-range.json: review_status
```

Tests: `tests/test_content_review_status.py` (every draft lesson owed and no reviewed one; every
format present, each note's file existing; `--owed`, `--json` and the exit code; an unknown note
never upgraded; a fixture with one item per format landing in its group, and a renamed review field
failing loudly for each file-based format; the gate's refusal; since Volume 20, prompt 8: every
mapped check's test, command and CI steps exist and the job installs a JDK, a renamed step or test
failing the table's test, every format in one of the two lists, every machine-checked item today
naming its check, a claim with no check here listed apart and printed by `--owed`, an author's
review never machine-checked, the check printed and in `--json`, and CI's content gate running
`--owed`).

## Adding a unit

1. Write it in `units.py` and add it to `UNITS`.
2. Run `pytest tests/test_learn.py`: it checks every unit is complete, prerequisites exist in the
   same career, skills belong to the career, practice items exist, check answers are in range, and
   links are absent or `https://`.
3. Read it in the app on desktop and a 320px-wide screen; check keyboard access to the outline,
   code blocks, guided steps and the check.
4. Set `review` honestly and note what it was checked against.
