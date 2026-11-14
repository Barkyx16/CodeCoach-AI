# Test design

Volume 10, prompt 4. The learner writes test cases for a small specification and sees, from a
real sandbox run, which **authored faulty versions** each case tells apart from a trusted
reference. The point is that one well-placed case (a value exactly at a bound, an empty array, the
longest run at the very end) can do more than many ordinary ones.

## Where it is

- **Coding library** → "Test design: write cases that find bugs" (`/problems?view=test-design`), for
  careers with coding practice; the command palette has "Test design" for signed-in coding careers.
- An exercise: `/test-design/<slug>` (signed in).

## What an exercise is made of

A file in `backend/app/seed/testdesign/` (loaded by `backend/app/testdesign/__init__.py`):

| Field | Meaning |
|---|---|
| `slug`, `version`, `title`, `summary` | `tests-…`; the version goes up when anything authored changes |
| `spec` | the specification, in Markdown |
| `signature` | the one supported shape: a first parameter `int[]`, then up to two `int`, returning `int` or `boolean` |
| `limits` | `max_cases` (12), `max_length` (20 values), `min_value` / `max_value` (-1000..1000) |
| `examples` | public inputs with the expected output; checked against the reference |
| `reference` | the trusted correct implementation (`class Solution`) |
| `variants` | the faulty versions: `id`, `title`, `defect` (what's wrong), `gap` (a hint for a learner who missed it), `witness` (an input that shows the defect) and `code` |
| `review_status` | how it was checked |

The two exercises: **Count in Range** (four versions: `v < hi`, `v > lo`, the last value skipped, a
reversed range treated as valid) and **Longest Run** (three: the final run ignored, an empty array
said to have a run of 1, neighbours that differ by 1 treated as equal). Their examples tell no
version apart; that's the starting point.

These exercises are not coding-bank problems and their runs never touch a bank problem's tests,
hidden or public.

### How an exercise is checked before anyone sees it

- `validate-content` (`app/content/validate.py`) checks the shape: the slug prefix, the supported
  signature, sane limits, examples and witnesses within the limits, every version's text, unique
  ids, and code that can share one file (exactly one `class Solution`, no `import`, `package` or
  `public class`).
- `scripts/verify_reference_solutions.py` (CI, real JDK) runs the reference and every version
  through the same driver the judge uses, on the examples, the witnesses and 200 seeded inputs within
  the limits (empty, one value, full length, extreme values, and random ones). It refuses an
  exercise when: something doesn't compile or doesn't finish; the reference throws on any of those
  inputs; an example's expected output isn't what the reference returns; a version gives the
  reference's answer on its own witness (it isn't faulty, or the witness doesn't show it); or the
  examples already tell every version apart. **Expected outputs come only from running the
  reference**, never from a person's or a model's guess.

## A run

1. **The cases are checked first** (on the page and again on the server): every parameter present
   and of the right type, arrays within the length limit, values within range, at most 12 cases.
   A refused set gets plain messages per case (`422 invalid_cases`, `details.cases`) and nothing is
   saved.
2. **Admission follows the judge's contract**: one account at a time (PostgreSQL advisory lock), the
   per-minute limit (`SUBMISSION_RATE_LIMIT_PER_MINUTE`), one pending run per account
   (`429 test_run_pending`, naming it), a full queue refused (`503 judge_busy`), and a judge that's
   down refused like Run (`503 judge_unavailable`) with the cases still on the page. A resend with
   the same request key returns the run it made; the same key with other cases is `409`.
3. **One sandbox job.** The worker claims queued runs like submissions (after them). The reference
   and every version become classes `Impl0..ImplK` in one `Solution.java`; the driver calls each on
   every distinct input. The runner's contract (exactly `Solution.java` and `Main.java`), the
   sandbox, the time limit and the output limits are unchanged. Runner failures are retried up to
   `JUDGE_MAX_ATTEMPTS`; a stalled run is put back by the same staleness rule.
4. **Without a judge** (`EXECUTION_ENABLED` off) the cases are saved as `not_run`: "these cases
   weren't run … nothing was guessed". No report is produced.

## The report

Read off the sandbox's outputs (`app/testdesign/report.py`):

- **Per case**: what the reference returned; which versions (named **A, B, C…**, never by id, since
  ids would give the defects away) returned something else or threw; which of those no earlier case
  had told apart.
- **A wrong expected output counts against nothing.** If the learner's expected output disagrees
  with the reference, the case is shown as "Disagrees with the specification", with what the
  reference returns, and it tells nothing apart. A correct implementation can never be called
  faulty: the reference decides, and a version that behaves like it is never "told apart".
- **Duplicates and redundancy**: an input already used is "Duplicate" and run once; a case that
  tells apart nothing new is said to add nothing new. More cases never count for more.
- **Results that didn't arrive** (time or output limit) are "not finished" or "unknown", never
  guessed; such a version isn't offered as the gap to investigate.
- **Coverage**: "Your cases tell N of the M authored faulty versions apart from the reference",
  always followed by: "This counts only the M faulty versions written for this exercise. It says
  nothing about every possible defect, or about any hidden tests in the problem bank."
- **One gap to investigate**: the authored hint for the first version no case told apart. A version
  is named (its title) only once a case tells it apart; all of them, with their defects, are shown
  only on a confirmed "Show what the faulty versions get wrong".

A run keeps its cases, the exercise version and the report. If the exercise changes before a queued
run is executed, the run isn't executed against the new version: it's failed with "run them again".
Revising cases makes a new run ("Edit these cases" loads an earlier run's cases into the editor);
earlier runs stay as they were.

## Storage and privacy

- `test_design_runs` (migration `8e4b1d7c2f60`): owner-only in every query, cascading with the
  account. Not under row-level security, like `submissions`, because the worker claims queued runs
  across learners (docs/ROW_LEVEL_SECURITY.md lists it among the deliberate exceptions).
- Unsent cases are kept on this device (`test-design-draft:<account>:<slug>`) and cleared at
  sign-out.
- In the data export as `test_design_runs`; not restored from a backup file, like other practice
  results.
- No AI is involved. The page links to the debugging lab and code review explicitly; nothing is
  added to the learner's plan.

## Limits

- One input shape (`int[]` plus up to two `int`, returning `int` or `boolean`), Java only, two
  exercises with seven faulty versions in all, written for practice and machine-checked but not
  reviewed by an outside instructor.
- Coverage is over the authored versions only; a set of cases that tells all of them apart can
  still miss other defects.
- The 200 seeded inputs make a hang or a reference crash unlikely within the limits; they don't
  prove there is none. The sandbox's time limit still bounds every run.
- The real gVisor path is tested only in CI's sandbox job (no Docker here); locally, tests run the
  same files with a local JDK.
