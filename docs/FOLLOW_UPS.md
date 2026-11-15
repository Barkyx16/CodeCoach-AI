# Follow-up questions: the same idea, a different question

After repeated practice on one written question, the question page can offer an optional,
different question about the same thing, so the learner can see whether an improvement carries
over (Volume 12, prompt 4). Both answers are kept, each with its own score. Coding problems have
reviewed follow-ups too (below, "Coding problems").

## Relationships are authored and reviewed

`backend/app/careers/followups.py` lists each relationship: question A, question B, what they
share (the objective) and how B differs, and how it was reviewed. Nothing is generated: when a
question has no reviewed relationship, the page says "No reviewed related question is linked to
this one yet." The content gate (`python -m app.content.validate`, run in CI) refuses a
relationship that isn't reviewed, has no objective or difference, points to a question missing
from the bank, links a question to itself, or is listed twice; a retired follow-up is a warning
and isn't offered. A relationship stays in its career; another career only if it says so
(`to_track`), and none does today.

| Career | Question | Follow-up | What's different |
|---|---|---|---|
| Registered nurse | Catching mistakes with electronic health records | Catching mistakes with IV pumps | Different equipment |
| Registered nurse | Keeping patients informed | Keeping patients' families informed | A different audience |
| Registered nurse | Checking your patient assessment work | Checking your medication administration work | A different task |
| Customer service | Catching mistakes with help desk software | Catching mistakes with CRM systems | A different tool |
| Customer service | Keeping customers informed | Keeping team leads informed | A different audience |

Each pair has the same rubric points in the bank; the review checked both prompts and rubrics.

## When it's offered

- **Threshold:** two answers to the question that were long enough to score (too-short answers
  don't count, and an answer whose length wasn't recorded doesn't either). The two needn't be
  comparable with each other: the offer is about practice, not a change in score. Before that,
  nothing is shown.
- **Only this account's answers** decide it; another account's practice never does.
- **Optional:** "Not now" hides it in this browser (`codecoach.followups.dismissed.v1.<account>`,
  pairs of question ids only; kept when you sign out, and listed on Your data under "Also on this
  device").
- **Retired and revised:** a retired follow-up isn't offered; a revised one shows its current
  version, and earlier answers keep the version they were written against.

## How exposure is described

"Not previously attempted in this app" when this account has no answer to it here, or "Answered
N times before in this app". Never "new to you" or "never seen": practice elsewhere isn't known.

## The follow-up is its own attempt

Opening it from the offer adds `?followUpOf=<answer id>`, and the answer is saved with
`follows_up_answer_id` (migration `f7d1b3e5a209`; checked: your own answer, to a question with a
reviewed relationship to this one, else 404 or 400 `not_a_follow_up`). It has its own record,
score and conditions (docs/ATTEMPT_CONDITIONS.md). On the first question's page, "Follow-ups you
answered" lists it beside the original with its own score and in-app help; scores are never
merged or averaged, and a result either way is more evidence, not a verdict ("mastered" is never
said). The export carries the link (`follows_up`).

## Under an accepted improvement

A follow-up whose earlier answer is an interview answer an improvement was accepted from (or one of
its retries) is listed under that improvement's **Related practice** (docs/ACCEPTED_ACTIONS.md), by
that stored link only: with its own question's title, its own score, and "A different question
about the same thing: not a retry, so its score isn't set beside the original's." It never marks the
improvement done and never says it worked.

## Coding problems

Volume 14, prompt 10. After a **judged submission** of a coding problem **passed**, the workspace
can offer a different problem that shares one idea with it, judged in the same sandbox, its verdict
its own.

**Pairs are authored and reviewed.** `backend/app/content/problem_followups.py` lists each pair:
problem A, problem B, the idea they share and how B differs, and how it was reviewed. Nothing is
inferred from topics. The content gate refuses a pair whose problems aren't both in the bank with a
reference solution, that isn't reviewed, has no shared idea or difference, links a problem to
itself, or is listed twice (`tests/test_problem_followups.py` checks each refusal).

| Problem | Follow-up | The same | Different |
|---|---|---|---|
| Two Sum | Two Sum in a Sorted Array (easy) | Finding the two values that add up to a target | The array is sorted and extra space is limited, so two pointers replace the hash map |
| Two Sum in a Sorted Array | Three Numbers That Sum to Zero (medium) | Two pointers closing in on a target over a sorted array | Three values instead of two: fix one, then run the two pointers on the rest, skipping repeats |
| Contains Duplicate | Valid Anagram (easy) | Remembering what you've already seen in one pass | Count each letter instead of noting whether a value appeared |
| Valid Anagram | Group Anagrams (medium) | A word's letter counts as its signature | Use the signature as a map key to group many words, not to compare two |
| Valid Palindrome | Reverse a String (easy) | Two pointers walking in from both ends of a string | Build the reversed string instead of comparing the ends |

**When it's offered** (`GET /api/v1/problems/{slug}/follow-ups`, `app/services/problem_followups.py`):

- only after this account's judged submission of the problem passed: a run never counts (it
  checks the public tests only), and neither does a failed or unjudged submission (`not_yet`);
- only while the follow-up hasn't been attempted in this app at all, by a submission or a run
  ("Not previously attempted in this app", the same words as for questions); once tried, it isn't
  offered again (`done`);
- never for a retired problem, and never once dismissed. **Not now** is kept with the account
  (`POST .../follow-ups/{to_slug}/dismiss`, in the onboarding state's dismissed list as
  `problem-follow-up:<from>><to>`), so it stays dismissed on every device; an unknown pair is 404.

The offer says: "An optional, different problem that shares one idea with this one. Its verdict
will be its own: it isn't combined with this one's, and passing it doesn't by itself show that
anything was learned." It appears under the passed result (at phone size, in the Code tab, where
the result is) and, when no result is on screen, beside the problem; never both at once.

**The follow-up is its own attempt.** The offer's link opens the second problem with
`?followUpOf=<the passed submission>`; the workspace says so above the editor ("That one stays as
it is; your submission here gets its own verdict, not combined with it", with "Practise it on its
own instead"). The first **submission** made there sends `follows_up_submission_id` (a run
doesn't: it isn't an attempt); later ones are ordinary attempts of that problem. The server stores
the link once, on that submission (`submissions.follows_up_submission_id`, migration
`b7e1f3a5c924`, set null if the earlier one is deleted), and only to this account's own passed
submission of a problem with a reviewed pair to this one: another account's is 404 like one that
doesn't exist, and a failed one or an unrelated problem's is 400 `not_a_follow_up`. Its result and
its page say "A follow-up to Two Sum, a different problem. Its own verdict, not combined with that
problem's or compared with it." It is never compared with the first problem's submissions (the
comparison is between submissions of the same problem). The first problem lists the follow-ups
submitted from it, each with its own verdict and counts, under "Follow-ups you submitted". The
export carries `follows_up_submission_id` on each submission.

**Checked:** `backend/tests/test_problem_followups.py` (7, SQLite and PostgreSQL; 12 negative
controls, all caught: the pass rule, runs counted, the not-attempted rule, dismissal, another
account's pass, the link's owner, pass and pair checks, the stored link, the export, and two gate
checks), `problemFollowUps.test.tsx` (6; 7 controls, all caught), and the software engineer's
journey (docs/PREPARATION_JOURNEY.md): after the resubmission passes in the sandbox, the offer is
under the result (in the Code tab at phone size), and "Two Sum in a Sorted Array" is solved and
judged for real, its verdict recorded as the judge gave it.

## Limits

Five relationships in two careers, and five coding pairs, Java only. Wider coverage is content
work: each new pair needs the same review. A passed follow-up shows that this problem passed too,
not that anything carried over.
