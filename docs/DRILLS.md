# Communication drills

Short exercises to do between full mock interviews: one objective each, a prompt written for the
learner's own career, and feedback that describes what's in their words. It isn't another
interview system, and it doesn't replace question replay or spaced review.

## The drills

Five to start, each with a stated objective and what helpful feedback looks for, shown before the
learner begins:

| Drill | Objective | Feedback looks for |
|---|---|---|
| Introduce yourself briefly | Who you are, what you do, one reason you fit, in about a minute | What you do; one concrete strength or experience; a link to this kind of role |
| Answer with a concrete example | One specific example, not a general statement | Answers the question; one specific situation; what you did and what happened |
| Explain it to a non-specialist | An idea from your work that an outsider would follow | Main point first; everyday words; an example or comparison |
| Ask a clarifying question | Questions that would change how you answer an open request | Asks rather than answers; specific to the request; says why it matters |
| Respond to a follow-up | More detail than you first gave | A new detail; stays on the follow-up's point; brief |

Prompts are built from the career's own profile (its skills and situations), so a nurse gets
"Tell me about a time patient assessment really mattered…" and a software engineer gets one
about their own work. Only the introduction has a target length (60 seconds), because length is
part of that objective; it's labelled a guide, not a score. Nothing else mentions time, and
nothing rewards a shorter or faster answer.

## Attempts

- **Type or speak.** Speaking uses the same browser speech recognition as the voice studio
  (`useDictation`): a clear Speak / Stop state, words appear in the answer box, and the box is
  always editable before sending. If the browser has no speech recognition, the page says so and
  typing works the same. A blocked microphone gets a plain message; typing still works.
- **Nothing to review isn't an attempt.** Fewer than three words (silence, an aborted
  recording, a failed transcription, filler sounds only) is refused with `400 too_little` and
  nothing is saved.
- **Unsent words are kept on this device** until they're sent, so a failed request or a closed
  tab loses nothing. A retry after a failure carries the same request id, so it's saved once.
- **Audio is never uploaded or stored.** Only the text is sent; recognition happens in the
  browser.

## Feedback

- **Observations**: for each point the drill looks for, whether it's there, with a short detail
  from the learner's words (for example "The first sentence is 41 words long").
- **Broad claims** ("hard worker", "team player", "always") are pointed out when nothing
  concrete stands beside them, as a suggestion, not a penalty.
- **Measured** is only what was measured: the word count of the text, and spoken time only when
  the browser timed a recording (the microphone's on time). A "time to say it aloud" figure is
  labelled an estimate (150 words a minute) and never stands in for spoken time. Typed answers
  never get a spoken time.
- **Transcript artifacts are not the learner's speech.** Filler sounds that speech recognition
  writes down ("um", "uh") are left out of the counts, and the feedback says so and that they
  aren't marked down. Pauses, accents, disability and choosing to type are never judged.
- **Delivery measurements can be turned off** (spoken time and the target length). The choice is
  remembered on this device.
- It's built-in rules, not a reviewer, and says so: it can miss a good answer phrased
  differently. Results are kept separate from coding correctness and from anything like a hiring
  prediction; drills don't feed analytics or readiness.

## Repeats

Every attempt is kept as sent. Each one after the first is compared with the previous attempt at
the same drill, **only if both were checked with the same rubric version**: "Now there: gives
one specific situation", "Not there this time: …", or "The same points are there as last time".
Attempts under different rubric versions say they aren't compared. Shorter isn't treated as
better. Any attempt can be opened from the history beside the drill; its address
(`/drills/<id>?attempt=<attempt id>`) works after a reload and with Back.

## Saving and scheduling

A drill can be bookmarked or added to a collection with the same controls as questions and
problems (it shows as "Communication drill" in Saved and opens from a practice queue), and put on
the schedule ("Add this drill to my schedule"; a scheduled drill counts as done only when an
attempt is sent after it was scheduled). There are no notifications, streaks or rankings.

## Privacy and limits

Attempts are owner-only, in the data export (`drill_attempts`) and deleted with the account.
Sending is rate-limited with the existing practice limiter (`429`), and each drill keeps up to
200 attempts.

## Verified, and not

See the V2-07 entry in [RESUME_LIFTER.md](../RESUME_LIFTER.md) for the exact runs.

Not verified here: real speech recognition (Chromium's needs a network service, so the browser
test uses a stand-in that delivers a fixed transcript), screen readers, Safari and Firefox, and
real phones. Spoken time is the time the microphone was listening, which includes pauses; it
isn't speech-activity detection.
