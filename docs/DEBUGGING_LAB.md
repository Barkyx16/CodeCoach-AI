# The debugging lab

Volume 10, prompt 2. Exercises that start from a program with a known defect: the learner
reproduces it with the public cases, works out the cause and fixes it. It's part of the coding
practice, not a separate application: the same editor, judge, drafts, hints, history and limits.

## Where it is

- **Coding library** → "Debugging lab: fix programs with a known bug" (`/problems?view=debugging`),
  for careers with coding practice. The command palette (Ctrl+K) has "Debugging lab" for the same
  careers.
- Each exercise opens in the usual workspace (`/problems/<slug>`), starting from the faulty code.

## Language and runtime

Java only, like the rest of the coding practice: `class Solution` with one method, the same
argument types and comparison as every problem (`backend/app/services/judge/harness.py`). Code
runs only in the existing judge: the API never runs it; the worker sends it to the runner, which
runs it under gVisor. On a server without a judge an attempt is saved and the page says it couldn't
be checked; nothing pretends it passed.

## What an exercise is made of

A file in `backend/app/seed/debugging/` (the problem format plus two keys) and a repair in
`backend/app/seed/reference/<slug>.java`:

| Field | Meaning |
|---|---|
| `kind` | `"debug"` |
| `starter_code` | the faulty program the learner starts from |
| `hints` | at least two staged hints about this defect (the existing hint ladder serves them) |
| `tests` | public cases (shown) and hidden cases (counted only), as for any problem |
| `lab.version` | the exercise's version; each attempt records the version it started from |
| `lab.intended_behavior` | what the code should do, in one sentence |
| `lab.reproduction` | positions of the public tests the faulty starter fails |
| `lab.defect` | `summary`, `explanation`, `why_missed` (why a simple case doesn't show it) |
| `lab.follow_up` | what to practise next |
| `lab.review_status` | who has checked it (shown to learners) |
| `alternatives/<slug>.N.java` | other correct repairs, checked like the reference |

## How an exercise is checked

`python scripts/verify_reference_solutions.py` (CI: "Reference solutions pass every seeded test")
and `python -m app.cli validate-content --run-reference` run real `javac`/`java` through the
production driver and comparison. An exercise passes only if:

- the faulty starter **compiles and runs without crashing** (a logic defect, not a compile error
  or an exception), **fails exactly** the public cases `lab.reproduction` names and passes the other
  public cases;
- the reference repair and every alternative pass **every** test, hidden ones included.

The content validator also checks the shape: a `debug-` slug, a public reproduction, the defect
text, two or more hints, a repair file. CI's sandbox job runs each exercise's starter and an
alternative repair through the real judge (`tests/test_judge_sandbox.py`, `e2e/judge.spec.ts`).

## What the learner sees, and when

- **Up front:** what the code should do, the failing public cases (input and expected result),
  the exercise version and review status. Optional notes (what you observed, a hypothesis, the next
  case to try) stay in this browser for the signed-in account and are removed at sign-out; nothing
  requires them.
- **When asked** (a two-step "Stuck? Show the explanation"): the defect, why a simple case misses
  it, one correct repair and a follow-up. Asking isn't recorded anywhere. The explanation endpoint
  (`GET /api/v1/problems/{slug}/lab/explanation`) returns authored text only, never a hidden test.
- **After an attempt:** the judge's verdict in the lab's terms ("Fixed: every test passes" only on
  a pass), whether each reproduction case now passes, and a line diff of what changed from the
  starting code. On a pass, "Why it happened". Any repair that passes is accepted: nothing compares
  it with the reference text.
- **History:** the code the attempt started from (with its version) and the code sent, apart from
  the verdict and any AI review.

## Versions

Each attempt stores the starter and lab version it started from (`submissions.starting_code`,
`lab_version`), so correcting an exercise later doesn't change what an old attempt shows it started
from. Public case results keep their own input and expected values from the run.

## The exercises (review status)

| Slug | Defect | Kind |
|---|---|---|
| `debug-coldest-day` | a running minimum that starts at 0 | an edge case (no reading below the start) |
| `debug-count-at-most` | `i < nums.length - 1` skips the last element | off-by-one |
| `debug-palindrome-sentence` | case compared exactly, and digits skipped | two defects |

All three were written for CodeCoach and are machine-checked as above. None has been reviewed by
an outside instructor yet; each says so on its page. They don't reuse any problem-bank test.

## Limits

- Three exercises, Java only.
- They aren't counted in problem progress, recommendations or a target role's coding coverage;
  attempts appear in History.
- Hints use the existing ladder (authored text; an AI provider, if configured, rewords it within the
  usual budget). The AI review, if asked for, is commentary next to the verdict, never the verdict.
- A correct repair that the hidden tests happen not to distinguish from a wrong one would pass:
  the tests decide, as for every problem.
