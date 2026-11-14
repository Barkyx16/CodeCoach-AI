# Follow-up questions: the same idea, a different question

After repeated practice on one written question, the question page can offer an optional,
different question about the same thing, so the learner can see whether an improvement carries
over (Volume 12, prompt 4). Both answers are kept, each with its own score.

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

## Limits

Five relationships in two careers. Wider coverage is content work: each new pair needs the same
review. Coding problems have no follow-ups yet.
