# Code-review practice

Volume 10, prompt 3. The learner reviews **someone else's** code: a short Java solution written for
one of the existing coding problems. They write findings first, then compare them with an authored
review. This is the reverse of the coach's "Review my code", which looks at the learner's own
solution; the page says so at the top ("CODE REVIEW · YOU'RE THE REVIEWER").

Nothing is fetched from a repository, no pull request is opened, and nothing is sent to anyone.
The exercises are synthetic teaching snippets.

## Where it is

- **Coding library** → "Code review: review someone else's code" (`/problems?view=code-review`),
  for careers with coding practice. The command palette (Ctrl+K) has "Code review practice" for
  signed-in learners with coding practice.
- An exercise: `/code-reviews/<slug>` (signed in). A sent review: `/code-reviews/attempts/<id>`.

## What an exercise is made of

A file in `backend/app/seed/reviews/` (loaded by `backend/app/reviews/__init__.py`):

| Field | Meaning |
|---|---|
| `slug`, `version`, `title` | `review-…`; the version goes up when the code or the review is corrected |
| `problem` | the existing coding problem the code is a solution to: its statement, constraints and public tests are shown as the task |
| `context` | who wrote it and why it's being reviewed |
| `code` | the code under review, shown read-only with line numbers |
| `findings` | the authored review: each a **defect** or an **observation** |
| `repaired_code` | one correct repair (needed when there's a defect) |
| `debrief`, `review_status` | the closing explanation, and how the exercise was checked |

Each authored finding has a stable location (`lines`, plus `related_lines` where the same issue
shows), a title, an explanation, its consequence and a repair. A **defect** cites `evidence`: the
public test(s) of the problem that show it and what the code returns for each. An **observation**
has no evidence and says `why_preference`: why it's a preference, not a defect.

The three exercises:

| Exercise | Authored review |
|---|---|
| Review: Largest Number | a defect (the maximum starts at 0; public test 2, `[-5, -2, -11]`, returns 0 instead of -2) and a style observation (an index loop where an enhanced `for` would do: no input behaves differently) |
| Review: Binary Search | **no defect**: the code passes every public and hidden test. Two observations: `(lo + hi) / 2` can't overflow at these sizes (10^4 values), and an `else` after a `return` |
| Review: Second Largest Value | a defect (a repeat of the largest value becomes the second; public tests 2 and 3) and a maintainability observation (`-1` as "none" is safe only because values are never negative) |

### How the authored reviews are checked

- `validate-content` (`app/content/validate.py`) checks the shape: the slug prefix, the problem
  exists, every location is inside the code, a defect cites public tests by position, an observation
  has no failing test and says why it's a preference, an exercise with a defect has a repair, and
  at least one exercise has no defect.
- `scripts/verify_reference_solutions.py` (CI, real JDK) runs each snippet against **every** test
  of its problem through the production driver: the public tests it fails must be exactly those its
  defects cite, with the stated results; an exercise with no defect must pass every public and
  hidden test; the repair must pass every test; the code must not crash. So the evidence can't drift
  from the code, and "no defect" is proven, not asserted.

## The learner's review

Each finding cites a line range (typed as numbers, by keyboard; the cited code is shown under the
numbers and highlighted in the code), and has three text fields: **what's wrong**, **what happens
because of it**, and **what to change** (a change, or a test that would show the problem). There is
no severity field: the exercise doesn't ask for a security or production-risk judgement it can't
support. Up to 20 findings, plus an optional summary ("the code looks correct" is a complete review).

- **Drafts** are saved to the account against a revision, like stories and the whiteboard (a stale
  save is a 409 that shows both versions; a save whose reply was lost is recognised by its request
  key). Unsaved changes are also kept on this device (`code-review-draft:<account>:<slug>`, removed
  at sign-out) and offered back after a reload.
- **Stable anchors.** The server stores each finding's cited code (the excerpt) with its lines. If
  an exercise is corrected after a draft was written, the draft's findings are found again by their
  excerpt: "moved" to the new lines, or "not found" for the learner to check.
- **Text is text.** Code, comments and the learner's words are rendered as text (React escapes
  them; nothing is parsed as HTML or Markdown). Control characters are removed on the server.

## The reveal and the comparison

The authored review is sent only when the learner asks ("Stuck? Show the authored review", then a
confirmation) or sends a review. Either is recorded on the draft, and every review sent afterwards
says "Written after reading the authored review".

The comparison is fixed rules (`app/reviews/feedback.py`), not AI. For each of the learner's
findings:

- **Where it points**: the cited lines overlap an authored defect ("Points at an authored
  defect"), an authored observation ("…an authored observation (a preference)"), or neither ("Not
  covered by the authored review": it isn't marked wrong, but the note says nothing supports it yet
  and that an input giving a wrong answer would).
  A finding citing more than six lines isn't matched ("Too broad to compare"), since citing the
  whole file would otherwise line up with everything.
- **A consequence** (at least three words) and **a next step** (at least two words): said when
  present, asked for when missing.

Matching is by location, never by wording, so the same point in other words lines up, and no
phrase is required. There's no score; more findings never count for more, and three or more
unsupported findings add a note that a short review with evidence helps more than a long list. The
authored review is shown beside the learner's findings, with each defect's test evidence in its own
block ("checked when this exercise was written"), apart from the notes about the learner's
findings. This is separate from the coding judge's pass/fail: nothing is run when a review is sent.

## Versions, ownership, export and deletion

- A sent review (`code_review_attempts`) keeps a snapshot of the code, the authored review it was
  compared with and the comparison, so a corrected exercise never rewrites it; its page says when
  the exercise has a newer version.
- Drafts and reviews are the learner's own (owner checks in every query, and PostgreSQL row-level
  security on both tables: migration `5b7e2c9d4a10`). Another account gets 404.
- In the data export as `code_reviews` (drafts, and each review with the code reviewed); deleted
  with the account (`ON DELETE CASCADE`); not restored from a backup file, like other practice
  results.

## Supported evaluation limits

- The rules can't tell whether an explanation is **right**: a finding at the right lines with a wrong
  explanation still "points at" the authored defect. The page says the check compares locations, and
  shows the two explanations side by side for the learner to judge.
- A real issue the authored review doesn't list reads as "not covered". The authored reviews are
  small and checked against the tests, but they aren't exhaustive.
- Line overlap is generous within six lines (a finding citing a loop overlaps everything in that
  loop); the notes say which authored finding it overlapped. Wider findings aren't matched.
- No AI is involved, so an unavailable or over-budget AI coach changes nothing here. If AI ever
  assists the comparison, it must be grounded in the authored findings and the snippet, label its
  uncertainty, and leave this authored comparison working on its own.
- Java only; three exercises, written for practice and machine-checked, not yet reviewed by an
  outside instructor. Not counted in progress, plans or recommendations.
- The learner can't run their own test cases from the review page; the evidence is the authored,
  CI-checked runs above. Running the code is the judge's job, in the coding workspace.
