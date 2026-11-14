# What the coach reads

Some coaching sends your material to a coach: the built-in coach on CodeCoach's own server, or,
when the server is set up for it, Claude by Anthropic, an outside service. This page lists what
each operation sends, and how the code review shows it to you first (Volume 12, prompt 2).

## Every coaching operation

| Operation | What's sent | Previewed? |
|---|---|---|
| **Code review** (problem page, Your coach → Code review) | The problem (public). Your code as in the editor, after secret-looking strings are replaced and long input cut. CodeCoach's own checks of that code (worked out from it). Optionally the judge's verdict on your submission | **Yes**: shown and approved before it's sent (below) |
| Hints | The problem and its reference hint for the level (public), your code as in the editor (the same replacing and cutting) and CodeCoach's checks of it | Not yet |
| "Explain my failure" | The problem, the submitted code (the same replacing and cutting), CodeCoach's checks, the verdict, the compiler output (judge lines removed), the first failing public test with your program's output, and pass counts. Hidden tests never, beyond counts. One explanation per submission, kept | Not yet |
| Coding interviewer (each reply, and the end-of-interview evaluation) | The problem, the phase and time left, the conversation so far as written (your messages aren't checked for secret-looking strings; only code is), your code (replaced and cut) and CodeCoach's checks | Not yet |
| Written answers, career interviews, practice labs, drills, scenarios, code-review exercises, story help, offer comparisons, whiteboards | Nothing: they're checked by fixed rules on CodeCoach's server | Nothing to preview |

The coach's fixed instructions are CodeCoach's own, the same for everyone, and aren't shown.
Everything you wrote is given to the coach as material to read, never as instructions: the
instructions say so, and your text sits inside marked, numbered blocks.

## Code review: check, then send

**Review my code** shows **What the coach will read** before anything is sent:

- **Read by**: the built-in coach ("nothing leaves it") or Claude by Anthropic ("an outside
  service"), and, for the outside one, that the built-in coach answers from the same material if
  it can't be reached, labelled as such.
- Each private item, **exactly as it's sent**, as plain text: your code after secret-looking
  strings were replaced (and how many), cut to the size limit if it was (and said); CodeCoach's own
  checks, marked **Worked out by CodeCoach**; and the judge's verdict on your latest submission,
  marked **Optional** with **Send the judge's verdict** to leave it out. Your code and its checks
  are **Needed**, with why.
- **Also sent**: the problem, public and the same for everyone, explained rather than removable.
- That checking is free and sending uses one of today's coaching requests.

**Send for review** sends the review **bound to what you checked**: the preview's
`context_fingerprint` goes with it as `approved_context`. The server builds the material again
the same way, checks the submission is still yours, and sends only if it's identical, including
what you chose (which submission, verdict or not). Otherwise nothing is sent and nothing is spent:
the answer is `409 context_changed` with what would be sent now, which the page shows with "What
the coach would read changed since you checked it, so nothing was sent." That covers code changed
after checking (the page also says so before you send, with **Check again**), and a submission
that's gone or isn't yours any more ("It isn't available any more, so it won't be sent"; the same
words whether it never existed or is another account's).

**Cancel** sends nothing. A preview never calls a coach, never uses the daily budget and stores
nothing; previews are limited to 60 a minute per account.

**Retries and replays.** The request key stands for the approved material, so sending again after
a lost reply gets the first answer back with no second call, and the same key can't later carry
different material (`409 idempotency_key_reused`). A left-out verdict reads to the coach exactly
like no verdict ("none given"), so leaving it out says nothing about whether there was one.

**Without a preview.** A review sent without `approved_context` (an older page, or the API used
directly) works as before; the page always previews.

## Checked by tests

`backend/tests/test_coach_context.py` captures what a provider receives (the Claude adapter over a
fake client): the context equals the preview byte for byte (code, checks, verdict) and the prompt
holds exactly those texts; a left-out verdict's text never reaches it, through a lost-reply replay,
a reused key and a widened approval; code changed after checking is refused with a fresh preview
and nothing spent; a deleted submission is left out and said; previews call nothing, spend nothing
and are rate limited; another account's submission reads the same as a missing one; instructions
written in code are shown as text and leave the coach's instructions unchanged; with the coach
down, the labelled built-in coach answers from the approved material.
`frontend/src/test/integration/coachContext.test.tsx` covers the page.

## Limits

- One operation is previewed: the code review. Hints, failure explanations and the coding
  interviewer aren't yet; this page lists what they send.
- The preview shows what CodeCoach sends. What an outside service does with it is governed by
  that service's terms (docs/PRIVACY.md); CodeCoach can't make promises about it.
- Secret-looking strings are found by patterns (keys, tokens, `password = "…"`); other personal
  text in code is sent as written, and the preview is where you see it.
