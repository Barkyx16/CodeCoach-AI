# Comparing attempts: one rule everywhere

Whether two attempts can be compared is decided in one place, and every page that compares written
answers asks it (Volume 12, prompt 6). The same two answers read the same on the question page, in
an interview retry, in the progress chart's list and in the data export.

- The rules: `backend/app/careers/comparability.py` (`classify`, `score_basis`), pure functions.
- The facts they look at: `backend/app/services/attempt_comparisons.py`, from what's recorded.
- Version: **comparison rules v1** (`CONTRACT_VERSION`). Every result carries it, and every
  explanation ends with it.

## What it looks at

| Fact | Where it comes from | If it isn't recorded |
|---|---|---|
| The question | the answer's career and question | always recorded |
| The question's version | `content_version` (versions start at 1; corrections publish 2 and up) | always recorded |
| The score scale | the kind of attempt: written answers are scored 0-100 | always known for written answers |
| Who graded it | the recorded coach: "built-in (offline)" is fixed rules | unknown |
| The rubric | the recorded `rubric_version`, or the rubric named in the recorded evaluator | unknown: never defaulted |
| Long enough to score | the recorded evidence level, or the recorded word count (`app/careers/eligibility.py`) | unknown |
| The format | an interview turn (a timed mock interview) or a retry row, else on its own | always known: interviews aren't deleted apart from their answers |
| In-app help | docs/ATTEMPT_CONDITIONS.md: lessons read for the question and version | unknown before 14 Nov 2026 |

How an answer was entered (typed or dictated) and accessibility settings are never inputs.

## Outcomes

| Outcome | When | Scores | What was written |
|---|---|---|---|
| Comparable | Everything above is the same | Shown as a change | Compared point by point |
| Partly comparable | Only the format or the help differs | Shown as a change, with the difference named | Compared |
| Partly comparable | The rubric or the question's version differs, or one was too short to score | Not compared | Compared |
| Not comparable | Different questions, scales or kinds of evaluator | Not compared; each keeps its own score | Not compared |
| Can't tell | Something above wasn't recorded (and nothing is known to be incompatible) | Not compared | Not compared |

A known incompatibility wins over a missing fact; a missing fact wins over a partial difference.
Nothing is converted between scales and no difference of unlike scores is ever shown as an
improvement.

## Explanations (the exact words)

| Rule | Explanation |
|---|---|
| comparable | "Comparable: the same question and version, rubric, evaluator and conditions." |
| question | "they answer different questions" |
| scale | "they're scored on different scales (0-4 and 0-100); each keeps its own score, never converted" |
| source | "different kinds of evaluator graded them (a person and fixed rules)" |
| rubric | "scored under different rubrics (v9 and v10): compare what you wrote, not the numbers" |
| question version | "the question was changed in between (version 1, now 2): compare what you wrote, not the numbers" |
| scoring | "one was too short to score: compare what you wrote, not the numbers" |
| format | "the conditions differed: the earlier one was answered in a timed mock interview, the later one as a retry after a mock interview" |
| help | "the in-app help differed: before the earlier one, none recorded; before the later one, hint shown" |
| missing | "which rubric graded one of them wasn't recorded" (and the same for who graded it, scoring, the scale, the format, or "in-app help before one of them wasn't recorded (it's recorded from 14 Nov 2026)") |

Each explanation starts with its outcome ("Partly comparable: …", "Not comparable: …", "Can't tell
whether these compare: …") and ends "(Comparison rules v1)". When only the format or the help
differs, it adds "The scores are on the same rubric, so both are shown".

## Which answer an answer is compared with

The one it revises (a stored link), else the one just before it to the same question, in any
format. The same choice everywhere (`previous_of`).

## Where it's used

- **The question page**: each answer in the list carries its comparison
  (`GET …/questions/{id}/answers`, `comparison`). The recap shows the explanation word for word,
  then what changed in the points (when what was written compares) and the score change (only when
  the scores compare). The page decides nothing itself.
- **An interview retry**: the original and the latest retry (`…/comparison`, `classification`;
  `comparable` is "the scores compare", `comparability_note` the explanation). The point lists are
  hidden when what was written doesn't compare.
- **The progress chart** (Analytics, a career): the trend averages one series per score basis
  ("Graded by fixed rules, rubric v10, scored 0-100"): answers long enough to score, from the same
  kind of evaluator and rubric, on the same scale. It averages different questions; format and help
  don't split a series. Each week's count is its average's denominator; each series shows how many
  answers it counted, and the answers it leaves out are counted by reason ("too short to score",
  "which rubric graded it wasn't recorded"). With fewer than two answers in a series it says "Not
  enough comparable answers to show a trend" instead of drawing one. "Answers in this range, and
  which the trend counts" lists every answer in the range (`GET /me/careers/{slug}/analytics/attempts`,
  50 at a time): its own score on its own scale, in the trend or why not, and its comparison with
  the answer before it, the same as on the question page. The number in the trend equals the number
  listed as in it, for any range and career.
- **The data export**: each written answer's `comparison`, with `contract_version`, as decided when
  the file was made: an export keeps the classification it was made with.

## When the rules change

Change `CONTRACT_VERSION` with the rules and add a row here. The explanation names the version that
decided it, so a page and an earlier export can be told apart.

## Not covered yet

Coding submissions, drills, whiteboards, work samples and the other formats keep their own rules for
now (docs/DRILLS.md and others) and adopt this contract later. Help outside the app isn't known.
