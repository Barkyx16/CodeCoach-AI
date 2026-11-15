# What the coach reads

Some coaching sends your material to a coach: the built-in coach on CodeCoach's own server, or,
when the server is set up for it, Claude by Anthropic, an outside service. This page lists what
each operation sends, and how the code review (Volume 12, prompt 2), hints and failure explanations
(Volume 13, prompt 2) and the coding interviewer (Volume 14, prompt 3) show it to you first.

## Every coaching operation

| Operation | What's sent | Previewed? |
|---|---|---|
| **Code review** (problem page, Your coach → Code review) | The problem (public). Your code as in the editor, after secret-looking strings are replaced and long input cut. CodeCoach's own checks of that code (worked out from it). Optionally the judge's verdict on your submission | **Yes**: shown and approved before it's sent (below) |
| **Hints** (problem page, Your coach → Hints) | The level you ask for; your code as in the editor (the same replacing and cutting) and CodeCoach's checks of it. Public: the problem and its reference hint for that level | **Yes** (below) |
| **"Explain this failure"** (a failed submission's results) | The submitted code (the same replacing and cutting), CodeCoach's checks, the verdict and the pass counts; optionally the compiler output (judge lines removed) and the first failing public test with your program's output. Hidden tests never, beyond counts. One explanation per submission, kept | **Yes** (below) |
| **Coding interviewer** (each message, and the feedback on Finish or End early) | Your message and the conversation so far (secret-looking strings replaced in both), your code (replaced and cut), CodeCoach's checks, and where the interview is (the phase and your messages in it) or, for the feedback, how it ended. Public: the problem. The opening turn sends only the problem and the time available | **Yes** (below) |
| Written answers, career interviews, practice labs, drills, scenarios, code-review exercises, story help, offer comparisons, whiteboards | Nothing: they're checked by fixed rules on CodeCoach's server | Nothing to preview |

**Names you listed** (Settings → Names kept in; docs/PRIVACY.md, "Names you listed") are replaced
with [name] in every one of these, wherever your own text is sent: your code, your message, the
conversation so far, the compiler output and what your program printed. Each item's notes say how
many ("1 name you listed was replaced with [name]."), and so does the check as a whole
(`names_replaced`, `names_note`), so you see it before anything is sent. What's sent is what was
previewed: the replaced text is part of what the fingerprint covers. Your own code, transcript and
submissions keep the names. Only the names on the list are found.

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

## Hints and failure explanations: the same check

**Get a hint** (or **Unlock level N**) and **Explain this failure** show **What the coach will read**
first, built by the same code as the code review's (one place renders each text, for the preview and
for the prompt), and send only what was approved (`approved_context`, rebuilt and compared on the
server; otherwise `409 context_changed` with a fresh preview, nothing sent, nothing spent).

- **A hint** lists the level asked for ("Requested hint level: 2 (concept)."), your code and
  CodeCoach's checks of it, all needed. Above them: the level ("Level 2 of 4: Concept."), and why it
  differs from what you've had ("You've seen level 1 (Nudge) for this problem, so this one goes
  further.", or "You've had level 1 before: this asks for it again…"); which levels you've seen isn't
  sent. **Also sent**: the problem, and its reference hint for the level, public and the same for
  everyone, listed but not shown, so checking doesn't give the hint away. The ladder is as before: a
  preview of a locked level is refused the same way (`hint_locked`), and so is a level the problem
  hasn't got. Code changed after checking: **Check again**, and the send button waits.
- **An explanation** says which submission it explains ("Explains your submission of 14 November
  2026, 10:42 UTC (failed tests).") and that one explanation is kept for each. Needed: the submitted
  code, its checks, the verdict and the pass counts (hidden tests are counted, never described).
  **Optional**: the compiler output (**Send the compiler output**) and the first failing public test
  with what your program printed or threw (**Send the failing public test**); left out, the coach
  reads as if there were none. The approval names the submission: a newer submission is explained
  only after its own check. Asked again for a submission already explained, the preview says so and
  the button shows the kept explanation; nothing is sent, so a retry can never add material.

Previews of all three operations share the 60-a-minute limit; none calls a coach, uses the budget or
stores anything. Without `approved_context` (an older page, or the API used directly) a hint or an
explanation works as before, everything included.

## The coding interviewer: one action away, or every time

During a coding interview, **What the interviewer reads** (under the answer box) shows what your next
message would send, and **What the feedback reads** what Finish would send, in the same panel as the
other operations, titled **What the interviewer reads**. It stays out of the way: Send sends straight
away unless you tick **Check every message, and the feedback, before it's sent** (kept in this
browser only), when Send, Finish and End early show the check first and send from it.

- **Your message**, exactly as sent: secret-looking strings replaced, and how many ("1 secret-looking
  string replaced with [REDACTED].").
- **The conversation so far**: every message in the interview, in order, as the interviewer reads it
  (an interview has at most 30 of yours, each up to 4,000 characters). Secret-looking strings are
  replaced here too, every time the conversation is read, though the transcript you see keeps what
  you wrote.
- **Your code** and **CodeCoach's own checks** of it, built by the same code as the code review's.
  On another device, with nothing sent from its editor yet, the code is the one last sent with a
  message ("As last sent with a message"): a resumed interview previews from the server's state.
- **Where the interview is** (worked out by CodeCoach): the phase and how many messages you've sent
  in it. The time left isn't sent with a message.
- For the feedback: the conversation, the code (on Finish the editor's; on End early the code last
  sent, as ending early always has) and **How it ended**. With no coaching requests left today, the
  built-in interviewer scores it, free, from the same material, as before.
- **Read by**: the built-in interviewer ("nothing leaves it") or Claude by Anthropic; with Claude,
  the built-in interviewer answers from the same material if it can't be reached.

A checked message carries the preview's `context_fingerprint` as `approved_context`; the server
builds the material again and sends only if it's identical. Otherwise nothing is stored or spent:
`409 context_changed` with what the interviewer would read now, which the panel shows with "What the
interviewer would read changed since you checked it, so nothing was sent." Before sending, the page
says when your message, your code or the conversation changed since the check (**Check again**; the
send waits). Finish and End early are bound the same way, and a refused one leaves the interview
open. A message resent after a lost reply is answered once, as before.

The interviewer's questions, phases, timing and the 30-message limit are unchanged. Previews share
the 60-a-minute limit with the others, call nothing, spend nothing and store nothing; only the
fingerprint travels. A preview of an interview whose time is up says so and doesn't close it (the
next read does, with its feedback). An interview that runs out of time is scored without a preview:
there's no request to check, and it reads exactly what the feedback preview lists, with "How it
ended: time_expired." Without `approved_context` (an older page, or the API used directly) a message or a finish
works as before.

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

`backend/tests/test_coach_context_hints.py` does the same for hints and explanations with a recording
provider: a hint's and an explanation's context and prompt equal the preview byte for byte; code edited
after a hint's preview is refused with the new code shown and nothing spent; a resent hint gets the
first answer and its key can't carry other material; the ladder's levels, locks and budget are as
before; twenty previews call nothing and spend nothing; a left-out failing test or compiler output (with
canaries) never reaches the coach, also on a retry asking for more; a wider choice than approved is
refused; a newer submission needs its own preview; a hidden test's row smuggled into the public results
never appears; another account's submission reads the same as a missing one.
`frontend/src/test/integration/coachContextMore.test.tsx` and `frontend/e2e/coach-context.spec.ts`
cover the pages (the browser test against the real API and the built-in coach, with axe in both
themes).

Negative controls (each caught): a hint or an explanation sent without comparing the approval; a
widened explanation retry sent again instead of the kept one; a left-out failing test sent anyway; the
public-results check bypassed (a hidden row leaks); a preview that calls the coach; the reference hint
shown in the preview; another account's submission explained; on the page, a hint sent without its
approval, a refused hint not said, the explanation's choice not sent, a kept explanation not said, what
the request is for not shown, and a server wait not blocking the send; in the browser, changed code
still sendable and a hint preview that spends a request. Not a meaningful control: dropping the
approval from a hint's request key, because the key already stands for the code and level, which are
all a hint's material.

`backend/tests/test_coach_context_interviewer.py` does the same for the coding interviewer: a
message's and the feedback's prompt holds every previewed item byte for byte; secret-looking strings in
the message, in earlier messages and in code never reach the provider; changed code, other words or a
conversation that moved on are refused with the new preview and nothing stored or spent; a refused
finish leaves the interview open; End early reads the code last sent; a resumed interview previews from
the server; another account's interview isn't found; a replayed bound message is answered once; twenty
previews call, spend and store nothing and are rate limited; a preview past the deadline evaluates
nothing; the built-in interviewer is labelled as such.
`frontend/src/test/integration/interviewerContext.test.tsx` covers the panel and the every-message
setting, and `frontend/e2e/interviewer-context.spec.ts` the page against the real API (check, send,
change the code, see a stale request refused with the new preview; axe in both themes).

Negative controls for the interviewer (each caught): a message or the feedback sent without comparing
the approval; any approval accepted; a message's or an earlier message's secrets not replaced; a
replayed message asked again; a preview that spends a request; on the page, a checked message or the
feedback sent without its approval, Send ignoring the setting, the setting not kept, a changed message
still sendable, a refusal not shown, End early unchecked with the setting on; in the browser, the
server sending a stale request, a message's secret not replaced, changed code still sendable. Not a
meaningful control: leaving the conversation out of the approval, because the phase item counts your
messages in the phase, so any message sent in between changes the approval anyway.

## Limits

- Every coaching operation is previewed: the code review, hints, failure explanations and the coding
  interviewer (its messages and its feedback). An interview that runs out of time is scored without a
  preview, from the material listed above.
- An explanation's choices apply to the first one asked for: one is kept per submission, so asking
  again with more (or less) shows the kept one.
- The preview shows what CodeCoach sends. What an outside service does with it is governed by
  that service's terms (docs/PRIVACY.md); CodeCoach can't make promises about it.
- Secret-looking strings are found by patterns (keys, tokens, `password = "…"`); other personal
  text in code is sent as written, and the preview is where you see it.
