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
| format | A timed interview answer and one that wasn't timed name it (Volume 13, prompt 3), from the round's recorded time limit and follow-up: "the conditions differed: the earlier one was timed (answered in a 15-minute mock interview, with a follow-up from the interviewer); this one wasn't (answered as a retry after a mock interview)". Otherwise: "the conditions differed: the earlier one was answered on its own, the later one as a retry after a mock interview". The verdict is rules v1's, unchanged: only the reason says more |
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

## Coding submissions (Volume 14, prompt 1)

A finished submission is compared with the **previous judged submission of the same problem in the
same mode**, by the same `classify()` with code's own facts (`AttemptComparisons.submission_facts`):

| Fact | For a submission |
|---|---|
| question | the problem (another problem: not comparable, "they're attempts at different problems") |
| version | the version of the problem's tests the submission was judged on (`submissions.content_version`); not recorded on a problem whose tests changed since: can't tell |
| evaluator, scale, rubric | the code judge, tests passed, the problem's tests: the same for every submission |
| scoring | judged (any verdict on the code: passed, failed, didn't compile, crashed, ran too long, used too much memory) or not judged (the judge's own failure): not judged is not comparable, "this one wasn't judged, so there's no verdict to set beside the other" |
| format | a submission (every test) or a run (the public tests only): never compared with each other |
| help | the attempt's conditions (docs/ATTEMPT_CONDITIONS.md), as for written answers |

- **Which one before**: the latest earlier submission of the same problem and mode that the judge gave
  a verdict on. A submission the judge failed on is never the one before; one still being judged (or
  only saved) isn't compared yet.
- **Wording**: "Comparable: the same problem and tests, judged the same way, with the same in-app help";
  a test version in between reads "the problem's tests changed in between (version 1, now 2): compare
  the code, not the counts" (the counts aren't set side by side then); when only the help differs, "The
  counts are from the same tests, so both are shown".
- **Where**: the submission's page and the workspace's result ("Compared with your previous
  submission": each verdict with its own counts, and the explanation), History's row ("Partly
  comparable with the one before"), and the export (`submissions[].comparison`).
- **Never**: a verdict or count changed, the time in the method compared (it varies with the
  machine), "improved", "better" or an average.
- **Rules version**: still v1. No written answer's classification changed; code's rules are new
  facts for the same rules.

### Under a target's requirement (Volume 16, prompt 9)

Each submission a requirement lists (its latest three judged submissions, not runs, to the problems
it offers) shows its verdict, its tests passed and the contract's one-line outcome against the one
before it, in History's words ("Comparable with the one before"), linking to that same comparison on
the submission's own page (`/history/submissions/{id}#comparison`): the `compared` object is the
page's, built by the same `compared_view`, so the two can't say different things. The first judged
submission of a problem says "Not compared: the first judged submission of this problem"; one the
contract couldn't set beside the one before (other tests whose version wasn't recorded, another
problem) says its outcome in the contract's words.

- **The requirement's line** (`comparisons`): "1 compared with the one before; 1 not compared: the
  first judged submission of its problem." Compared means comparable or partly comparable; not
  compared gives the contract's reason for each (counted when several share one). It sits beside the
  coverage line, which counts practice exactly as before: no new score, no "improved", no "mastered".
- **A failed then passed submission** shows both verdicts and counts side by side under "Comparable
  with the one before", with the explanation (the rule). As everywhere, the contract doesn't call one
  "improved": the two results, comparable, say it.
- **Bounded**: the listed submissions of every requirement are compared in one batch (a problem two
  requirements share is compared once), with each one's result and problem tests loaded together, so
  reading the target takes the same statements with 6 submissions or 46
  (`test_reading_the_target_doesnt_grow_with_the_number_of_submissions`).
- **Export**: each requirement carries `submissions: [{id, status, comparison, compared_with,
  outcome}]` by id, as the page lists them.
- Tests: `backend/tests/test_requirement_comparisons.py` (8),
  `frontend/src/test/integration/targets.test.tsx` ("A requirement's submissions, compared").

## Drills, whiteboards and work samples (Volume 15, prompt 4)

Each **assessed** attempt is compared with the **previous assessed attempt at the same item** (a
drill, a whiteboard prompt, a work-sample brief): the one it revises when it says so (a work sample's
revision), else the one just before it (`previous_of`). The same `classify()`, the same outcome names
and contract version, with each format's own facts (`AttemptComparisons.checklist_facts`):

| Fact | Drill | Whiteboard design | Work sample |
|---|---|---|---|
| question | the drill, and the career its prompt was worded for (`drill_attempts.track`) | the prompt | the brief |
| version | the drill's rubric version: its points are its rubric | the prompt's version (its points) | the brief's version (its points) |
| rules (rubric) | the drill's points, versioned with it | the whiteboard rules' version (`rubric_version`) | the brief's rules version (`feedback.rules_version`) |
| evaluator | fixed rules | fixed rules | fixed rules |
| scale | the item's number of points | the prompt's number of points | the brief's number of points |
| assessed | a result is stored (its points, each there or not) | a result is stored (each point addressed or not found) | a result is stored (points covered of total) |
| help | the attempt's conditions (docs/ATTEMPT_CONDITIONS.md) | the same | the same |

The result is a checklist of the item's points, so these rules differ from a written answer's in one
place: **a changed checklist isn't comparable at all**. A written answer's text still compares under
another rubric; a checklist's ticks against other points don't. So:

| What differs | Outcome | Wording |
|---|---|---|
| nothing | comparable | "Comparable: the same drill (prompt, brief) and version, checked by the same fixed rules, with the same in-app help" |
| the help shown before it | partly comparable | "…the in-app help differed: …. The results are from the same checks by the same fixed rules, so both are shown" |
| the item's points (a new version) | not comparable | "the drill's (prompt's, brief's) points changed in between (version 1, now 2); each keeps its own result" |
| the rules that check them | not comparable | "they were checked by different versions of the rules (v1 and v2); each keeps its own result" |
| a drill asked for another career | not comparable | "the drill's prompt was worded for a different career each time" |
| help from before recording began (15 Nov 2026) | can't tell | "in-app help before one of them wasn't recorded (it's recorded from 15 Nov 2026)": never assumed the same |
| a work sample's rules version not stored | can't tell | "which rubric graded one of them wasn't recorded" |

- **Self-assessed?** None of the three is. A whiteboard design is checked by built-in rules against
  the prompt's points (docs/WHITEBOARD.md), not by the learner, so every one of these comparisons says
  "fixed rules". A self-assessed format would need its own kind of evaluator, named in the wording.
- **Not assessed**: an attempt with no stored result is never compared, and isn't the one before: the
  next assessed attempt is set beside the last assessed one.
- **Where**: each attempt's page ("Compared with your previous attempt": the earlier result and this
  one, each as it was given, such as "2 of 3 points there", and the explanation word for word), its row
  in the format's own attempts list ("Partly comparable with the one before"), the API (`compared` on
  each attempt and each row: `previous`, `result`, `comparison`) and the export
  (`drill_attempts[].comparison`, `whiteboard.attempts[].comparison`, `work_samples.attempts[].comparison`,
  by id). A drill's point-by-point changes ("Now there: …") are shown only when the points compare.
- **History** (Volume 16, prompt 6): each drill attempt, whiteboard design and work sample is a row
  (types `drill_attempt`, `whiteboard_attempt`, `work_sample_attempt`), with its date, the format,
  what was practised, its result and the outcome in its own page's words: "3 of 4 points there ·
  Comparable with the one before", or why it isn't compared, the same words on its page ("Not
  compared: the first checked attempt at this drill", "Not compared: no result was stored"; each
  attempt now carries `not_compared` there too, never a blank). Its in-app help comes in History's one
  request for the rows on screen. It links to that attempt (since Volume 17, prompt 2): the format's
  page with `?attempt=<id>` (`/drills/<id>?attempt=…`, `/whiteboard/<prompt>?attempt=…`,
  `/work-samples/<brief>?attempt=…`), which opens it. The rows sort and page with every other kind
  by when they were made; the type filter and the facet counts include them (a coding-only, skill or
  other-status filter leaves them out: they carry no skills, and an attempt is checked when it's
  saved). One statement counts all three formats and their rows and comparisons are read once per
  format that has some, so reading History doesn't grow with the number of attempts (a test reads it
  with two attempts and with fourteen in the same statements). The rows already there read exactly as
  before. No chart or replay reads these attempts.
- **History, the other three formats** (Volume 17, prompt 2): each scenario run, code-review exercise
  and sample-answer comparison is a row too (types `scenario_attempt`, `code_review_attempt`,
  `comparison_attempt`), in the words its own page's list uses ("In progress · version 1", "1
  finding · points at 1 of 2 authored defects · version 1", "1 excerpt, 1 matching the explanation ·
  version 1", with "after reading the authored review" or "after the explanation" where it was), then
  why it isn't compared: no rule of this contract covers these formats ("Not compared: scenario runs
  aren't compared with each other" (each run takes its own path), "Not compared: code reviews aren't
  compared with each other yet", "Not compared: readings of sample answers aren't compared with each
  other yet"). Each opens that attempt: a run's or a review's own page, or the lesson's page showing
  that reading (`/compare/<lesson>?attempt=<id>`); one that can't be opened says so. Its in-app help
  comes in the same one request. A scenario run in progress is "In progress" (the status filter and
  facet count it so); a code review is a coding problem's (the coding filter shows it, a career's
  doesn't); a sample-answer lesson is for every career (a career filter leaves it out). The one
  counting statement covers all six formats, so reading History still doesn't grow with the number of
  attempts (a test reads it with three attempts and with sixteen in the same statements). Checked in
  a browser at 412 and 360 pixels wide: the rows wrap, the page doesn't scroll sideways, and each link
  opens its attempt (`e2e/history-attempts-mobile.spec.ts`).
- **Never**: a result changed, "improved", "better", an average or a trend, within a format or across
  formats.
- **Rules version**: still v1. No written answer's or submission's classification changed; these are
  new facts, with the rules for a checklist, under the same version.

## Not covered yet

Every list of coding submissions now says how each compares with the one before: History, a
submission's page and the workspace's result, an improvement's related practice, a requirement, and
your submissions list (`GET /me/submissions`, `outcome_text`), which the dashboard's "Recent
attempts" shows, linking to the comparison (the first says it's the first; one still being judged,
or that the judge couldn't run, says nothing). Scenario runs, code-review exercises and sample-answer
comparisons are listed in History (Volume 17, prompt 2) but not compared: they, and the other formats,
keep their own rules for now (docs/SCENARIOS.md, docs/CODE_REVIEWS.md, docs/COMPARE_ANSWERS.md and others) and adopt
this contract later. Help outside the app isn't known.
