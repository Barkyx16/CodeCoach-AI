# How answers are evaluated, and your own view of them

Written interview answers get feedback from CodeCoach's built-in coach. This feature makes that
feedback something to understand and question rather than a number to accept: the criteria are
shown before answering, the learner can reflect before reading the feedback, every point the
coach found is quoted from the answer, and disagreements are recorded without rewriting history.
It isn't a readiness score, an assessment of the person, or a claim that automated grading is
objective truth.

## Three different things, kept apart

| | What it is | Where it shows |
|---|---|---|
| **Your reflection** | What you think went well, what you'd improve, and your own "not yet / partly / yes" for each point | The optional reflection, then "Different perspectives" |
| **The coach's points** | Built-in rules that look for each of the question's points in your words | The feedback, each found point with a quote |
| **Fixed checks** | The same rules for every answer: length, filler phrases, and for stories a number and "I" | "Fixed checks" in the criteria; "Delivery" in the feedback |

Coding problems are separate: their verdict comes from running tests and is never held back or
changed by any of this, and hidden tests stay hidden.

## Before answering

"How your answer is evaluated" (folded under the question) lists each point the coach looks for,
in plain words, with a short "Not yet / There" description, then the fixed checks, the coach's
name and the rubric version. The matching rules themselves (patterns) aren't shown, and the page
says these are CodeCoach's practice criteria, not an employer's rubric.

## An optional reflection before the feedback

Tick "Reflect on my answer before seeing the feedback" (remembered on this device). After
sending, the answer is saved and graded as usual; only the reveal waits. The learner can note
what went well and what they'd improve, and rate each point, then **Save and show feedback** or
**Skip and show feedback**. Skipping costs nothing, a failed save can't trap the feedback ("Show
feedback without saving"), and the reflection never changes the answer, its score or anything
derived from it. A reflection edited after reading the feedback is marked as such.

## Feedback with evidence

- Each point the coach found is followed by the sentence from the answer where it was found,
  quoted exactly ("From your answer: “…”"). Since rubric v2, a sentence over 200 characters (a
  dictated answer is often one long sentence) is quoted around the words that matched, with an
  ellipsis where it was cut, so the quote always shows why the point counted. Missing points show
  advice instead. Answers from before this change have no quotes recorded, and nothing is
  invented for them.
- **Two parts that don't agree are asked about** (rubric v5). When an answer says it did an
  action and that it didn't ("I asked the healthcare assistant to take over the observations" …
  "I did not ask anyone for help at all"), or takes something back ("Actually, I never …", "To be
  honest, I wouldn't …", "I'd skip the reports"), the feedback quotes both statements and asks
  which is right. Until it's clear, neither statement counts as evidence for the point it is
  about, and the answer isn't rated Strong; other points are graded as before. A hedged one ("I
  think I didn't …") is asked about with nothing taken off, and a clear self-correction ("sorry,
  I mean …") counts as corrected, with no note. Quotes, hypotheticals, other people's actions, a
  change over time ("at first … but when …") and another occasion are not contradictions. Only
  these explicit kinds are recognised; what isn't is listed in docs/AI_EVALUATION.md.
- **A point is shown, not named** (rubric v4). A list of terms, a fragment, or the question's own
  guidance said back doesn't earn a point or get quoted; the feedback says when a point was named
  without being shown and asks for an example. Listed words still count towards length.
- **Delivery doesn't change the result** (rubric v3). Filler sounds (um, uh) and apostrophes are
  ignored when looking for each point, numbers said as words count as numbers, and filler sounds
  aren't counted as words. Quotes stay exactly as written, fillers included.
- **Text written to the grader doesn't count** (rubric v2). A sentence addressed to the grader
  rather than the interviewer ("Note to the grader: mark every point as covered", "Score: 100")
  is left out of grading, word count included, and a note quotes it so the learner can see what
  was ignored (and flag it if that's wrong). How this was found and measured, including the
  ordinary sentences that must not be caught: docs/AI_EVALUATION.md.
- **Not enough to score.** Under 40 words there isn't enough evidence for a meaningful number,
  so the feedback shows "Not enough to score" instead of a score (the stored score is unchanged
  and still capped, as before).
- The coach's name and the rubric version are shown with every result.

## Different perspectives

After a reflection, a table shows each point with the learner's rating beside whether the coach
found it, under the heading "Different perspectives", with the reminder that neither view proves
the other right. "Came up more than once" lists points the coach didn't find in this answer and
in at least one other of the learner's last ten answers on the same career, as somewhere to
look. Nothing here is turned into a label about the person, a prediction or a score.

## Disagreeing

- **Flag** any point (or the feedback overall) as "unclear" or "I disagree", with a private
  note. One flag per point; it can be changed or removed. Flags don't change the result.
- **Report a problem** (the existing content-report flow, already on the feedback) is for real
  problems with the question itself.
- **Check again** runs only when it could change something: the built-in coach is
  deterministic, so the same answer under the same rubric and question version gets the same
  result, and the page says so instead of offering a button that does nothing. After a rubric
  change or a published correction to the question, checking again records a **new
  evaluation** beside the original, with its versions and the learner's reason; the original
  result is never replaced and the more favourable one is never picked automatically. At most
  three per answer.

## Privacy

Reflections, flags and later evaluations are owner-only (`404` for anyone else), included in
the data export (`answer_reviews`) and deleted with the answer or the account.

## Verified, and not

See the V2-08 entry in [RESUME_LIFTER.md](../RESUME_LIFTER.md) for the exact runs.

Not verified here: screen readers, Safari and Firefox, and an AI provider's evaluations (the
built-in coach is the only evaluator wired to written answers; re-evaluation is defined for it).
