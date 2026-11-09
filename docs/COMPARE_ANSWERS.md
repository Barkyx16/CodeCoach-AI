# Compare sample answers

Volume 10, prompt 6. Learners read two authored answers to one interview question, mark the
sentences that help or hurt each one, say why, and only then compare with an authored explanation.
This isn't rating your own answer (self-review) or comparing two versions of yours (retries): the
answers belong to nobody, and the point is the reasons, not the pick.

## Teaching purpose

An answer is useful when an interviewer can see and follow up what you did. Learners often copy the
style of a "model answer" (its length, its confident tone) without seeing why it works. Here they
have to point at the sentence and say what it does, so the lesson is the explanation they give, not
the wording they imitate. Each lesson has one teaching goal:

| Lesson | Kind | Teaching goal | Rubric |
|---|---|---|---|
| Specific evidence or general claims? | clear (B) | saying you have a quality vs showing what you did | situation, action, result |
| Answering the question, or the one next to it? | clear (A) | time spent on context instead of the question | relevance, method, example |
| Two different strengths | tradeoff | both answers are good in different ways; what each gives up | acknowledge, resolve, ownership |

In the clear lessons the weaker answer still has a strength the explanation names (Answer A's "I
listened to their side and explained mine"; Answer B's calm under pressure), so the lesson isn't
"one answer is all good". In the tradeoff lesson there's no better answer to choose.

All samples are fictional (a made-up delivery company, clinic and shop), written for practice and
checked for consistency, not reviewed by an outside interviewer. No learner's answer is ever used as
a sample, and lessons come only from `backend/app/seed/comparisons/`: an id can't reach any other
file, the sealed evaluation set included (a test probes it).

## Where it is

- `/compare` (signed in): the lessons; the dashboard's "More ways to practice", the command
  palette ("Compare sample answers") and Help ("Compare sample answers").
- A lesson: `/compare/<id>`.

## What a lesson is made of

A file in `backend/app/seed/comparisons/` (loaded by `backend/app/comparisons/__init__.py`):

| Field | Meaning |
|---|---|
| `id`, `version`, `title`, `teaching_goal` | `cmp-…`; the version is stored with every attempt |
| `question`, `rubric` | the interview question; what a useful answer does (id and label) |
| `kind` | `clear` (the explanation prefers one answer) or `tradeoff` (no preferred answer, no choice asked) |
| `samples` | two or three answers, labelled only "Answer A", "Answer B", …, each a list of sentences with ids |
| `explanation` | per sample: strengths and gaps (the sentence ids, a rubric criterion, why) and what stays uncertain; `preferred` (or null); `alternatives` (other good answers) |
| `next_step` | an explicit link: a drill, or a question for your own career |
| `review_status` | how it was checked |

`validate-content` refuses a lesson whose explanation cites a sentence that isn't in its samples,
uses a criterion that isn't in its rubric, leaves a strength or gap without a reason, labels a
sample anything but "Answer A/B/C", or is a tradeoff with a preferred answer.

## The page

- The question, the rubric ("What a useful answer does") and the samples. Side by side on a wide
  screen; on a narrow one, one sample is open at a time and each closed one says how many of its
  sentences you've marked, so the context isn't lost.
- Every sentence has **Strength** and **Gap** buttons (`aria-pressed`; keyboard as any button). A
  marked sentence asks "Why is it a strength?" (or gap); every mark needs a reason of at least three
  words before sending. Marks are shown with a border *and* the pressed button, never colour alone.
- In a clear lesson, "Which answer is more useful? (optional)": A, B or Not sure. A tradeoff lesson
  says "No single best answer" and asks for nothing.
- "Show the explanation now" asks first; if you read it before sending, the reading says so.
- Unsent marks are kept on this device (`compare-draft:<account>:<lesson>:v<version>`, cleared at
  sign-out) and offered back after a reload; a failed send keeps them on the page.

## The comparison

Fixed rules (`backend/app/comparisons/feedback.py`), not AI, on the snapshot the reading was made
against. For each excerpt you marked:

- **Matches the explanation**: it marks the same sentence the same way; its criterion is named.
- **The explanation reads it differently**: you called it a strength and it calls it a gap, or the
  reverse. Its reason is shown next to yours, with "both can have a point": not marked wrong.
- **Not covered by the explanation**: it doesn't single that sentence out; your reason may still hold.

Each result quotes the sentence from the stored version, shows your reason as plain text and the
explanation's reason. A choice is compared with the explanation's view and explained ("as the
explanation does. Check that your reasons match its reasons, not just its choice"; or "the
explanation prefers Answer B… If yours rest on excerpts it doesn't weigh, they may still be worth
keeping"). Nothing is scored, nothing changes your plan, progress or readiness, and a matching
choice isn't treated as mastery. The explanation then shows what each answer supports (quoted),
what isn't settled, other good ways to answer, and the next step.

## Versions, ownership, export

- Every send is a new row in `comparison_attempts` (migration `e7b3c1d9a842`) with a snapshot of the
  question, rubric, samples and explanation. An old reading shows the samples and explanation as
  they were, and says when the lesson has been edited since. An excerpt that isn't in the current
  version is refused (`unknown_excerpt`).
- Owner-only and under PostgreSQL row-level security (listed in `rls.ADDED_TABLES`); another
  account gets 404. In the data export as `comparisons`; deleted with the account; not restored from
  backups (results can't be verified from a file).
- Reasons are stored as text with control characters removed and shown as text.

## Where judgment stays qualitative

- The rules compare **where** you pointed and **which way**, never what your reason says. A sound
  reason on a sentence the explanation doesn't cover reads as "not covered", and a weak reason on
  the right sentence reads as "matches"; that's why both reasons are shown side by side for you to
  weigh.
- The explanation is one authored reading. It names what stays uncertain and other good answers,
  but it isn't the only defensible view, and it hasn't been reviewed by an outside interviewer.
- Three lessons, in English, for behavioural questions; they don't judge accent, grammar or
  cultural style, and the samples avoid making those the difference between answers.
- No AI. If AI clarification is added later, it must explain the authored reasoning and quote only
  the stored samples, never add a rule or a quote.
