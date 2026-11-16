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

**Hints inside the interview** (Volume 17, prompt 4): the room's **Hints** panel shows what a hint
would read, exactly as the workspace's does (`POST /ai/hint/preview` with the code last sent in the
interview), and asks bound to it (`POST /interviews/{id}/hint` with `approved_context`; refused with a
fresh preview if the code last sent changed). The feedback then reads that hints were used, in its
"How it ended" part, the same words the provider is sent: "How it ended: finished. Hints the
candidate asked for during it: level 1 (nudge)." (shown in the feedback's preview before anything is
sent). A hint asked for after "I've checked this" doesn't count as a change to the check, since how it
ends is compared apart.

**One request per interview and level** (Volume 18, prompt 2). An interview's hint at a level has one
request key, made from the interview and the level (`interview-hint_<id>_<level>`), whatever key the
page sent. And the coach, once it holds the account's AI turn (the PostgreSQL advisory lock that keeps
one coaching request per account at a time), looks again for the request's key before asking the
provider: a copy answered while it waited is that answer. So two tabs asking for the same new level
are one request. The second gets the first's hint, or, while the first is still being answered, is
told to wait ("Your previous coaching request is still being answered.") and then gets it, and the
provider is asked once. The same look after the wait applies to every keyed hint and code review. If
code was sent between the two tabs' checks, the second still gets the hint the interview has for that
level, not a refusal. The interview records it once. On SQLite, which has no AI turn to hold (local
runs only), two requests at the very same moment can both reach the provider; one is kept.

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
open. A message resent after a lost reply is answered once, as before. From 16 Nov 2026 a message
sent checked is marked so (`interview_turns.meta.checked`), and the interview's review lists which
were, with the feedback's check, as part of how it was given (docs/ATTEMPT_CONDITIONS.md, "Coding
interviews"; never help).

The interviewer's questions, phases, timing and the 30-message limit are unchanged. Previews share
the 60-a-minute limit with the others, call nothing, spend nothing and store nothing; only the
fingerprint travels. A preview of an interview whose time is up says so and doesn't close it (the
next read does, with its feedback, or housekeeping within about a minute: "When time runs out",
below). An interview that runs out of time is scored without a preview:
there's no request to check, and it reads exactly what the feedback preview lists, with "How it
ended: time_expired." The review then says what it read and that it wasn't checked ("What the feedback
read", below). Without `approved_context` (an older page, or the API used directly) a message or a finish
works as before.

## What the feedback read (Volume 15, prompt 8)

Every interview's feedback records what it read, when it's scored, and the review shows it under
**What the feedback read**:

- each part by its label and size ("The conversation so far · 1,234 characters"), with what was
  replaced in it (secret-looking strings, names you listed), and who read it. Never a second copy of
  the text: the transcript and your code are already in the review, as you wrote them;
- the fingerprint of exactly that material, how it ended (finished, ended early or time ran out) and
  whether you checked it: "You checked this before it was scored.", "You didn't check this before
  it was scored.", or **"You didn't check this before it was scored: time ran out."**;
- for a career interview, its own material ("Your answer to question 1 · 412 characters"), read by
  CodeCoach's own fixed rules on its server: nothing left CodeCoach, so there was nothing to check;
- for an interview scored before this was recorded: "What it read wasn't recorded then.", never a
  reconstruction.

**Shortly before time is up** (2 minutes: `FEEDBACK_CHECK_MARGIN_SECONDS`, sent with the interview
as `feedback_check_margin_seconds` while a coding interview is running), the page offers **Check
what the feedback will read**. It's said once, as it appears (its words don't change with the clock,
so a screen reader doesn't repeat it), and checking doesn't stop the clock. Finishing from the check
carries its fingerprint as before; if what's read changed since, the finish is refused as before
(`409 context_changed`) and the page says why. A preview itself stores nothing; what a time-out
says about a check made before it is below. Nothing extends an interview's time or changes its
scoring. The data export carries each interview's record (`interviews[].feedback_read`).

### A check before time ran out (Volume 16, prompt 3)

Under the feedback's check, **I've checked this** keeps that check with the interview
(`POST /interviews/{id}/feedback/confirm` with the preview's fingerprint): the fingerprint, the time,
the labels of the parts it covered and a digest of each part (`plan.feedback_check`), never the
text. Each confirmation replaces the last. It's bound like a finish: if what the feedback would read
changed since the preview (a message was sent, perhaps from another tab, or the code changed) it's
refused with `409 context_changed`, "What the feedback would read changed since you checked it (a
message was sent or your code changed, perhaps in another tab), so this check wasn't kept. Check
what it reads now.", and the panel shows what it reads now. Confirming sends nothing, scores
nothing, spends nothing (it shares the previews' 60-a-minute limit) and doesn't stop the clock. The
page then says, once: "Checked. If time runs out before you finish, the review will say you checked
this, or name what changed after."

When the interview is scored without a checked finish (time ran out, or a finish or End early sent
unchecked), the last confirmed check is compared with what the feedback read, part by part (how it
ended aside, since a check is made before it ends): the record keeps `confirmed` (its time and
fingerprint, whether it matched, the labels that changed). The review says **"You checked this
before time ran out."** with when, or **"You checked an earlier version before time ran out; it
changed after: The conversation so far."**. If the code checked was in the editor and hadn't been
sent, it adds "The code you checked was still in your editor, not sent, so it read the code last
sent." (a time-out reads the code last sent, as it always has). With no confirmed check it says what
it said before. A career interview has nothing to check (`409 wrong_interview_kind`): nothing of
theirs leaves CodeCoach. The export carries the check's time, fingerprint and labels
(`interviews[].feedback_check`) and the comparison (`interviews[].feedback_read.confirmed`), never the
text nor the digests.

**What changed, shown (Volume 17, prompt 1).** A check now also keeps a short digest of each line of
each part (never a line) and how many turns there were. When the interview is scored, each part that
changed after the check says how, under the sentence above: **"The conversation so far: 2 messages
sent after your check"**, or **"Your code: 4 lines added, 3 lines removed"**, with the added lines
shown by number from the code the interview keeps (the first 20; the review's code view has the
rest). The lines are matched in order (a line moved counts as removed and added). Only numbers and
counts are recorded with the feedback (`confirmed.changes`), so the export carries them and no line
of text. A check kept before this has no line digests: it names the parts, as it did.

## When time runs out (Volume 17, prompt 1)

An interview past its deadline used to close only when someone next read it, so an export, History
or the dashboard read before that showed it still running. Now housekeeping's **interviews_expired**
step (`interviews.close_overdue`, run every minute by the jobs thread and by `python -m app.cli
housekeeping`) closes each in-progress interview past its deadline exactly as a read would: the same
`_expire_if_due`, the same reason (`time_expired`), the same feedback-read record. A coding interview
is scored as it would be on read, with the learner's own coaching budget (the built-in interviewer
when none is left that day); a career round is closed by CodeCoach's own rules, nothing sent.

- **Bounded.** At most 50 a pass, oldest deadline first; the next pass takes the rest.
- **Once.** A read and the step racing close it once: the existing claim (`_claim_close`) decides.
- **Across accounts, narrowly.** Finding them reads ids and owners across learners through the
  maintenance read, with its reason logged; each is then closed in its own session bound to its
  learner, so row-level security applies to the close, and one failing doesn't stop the others.
- **Nothing else changes:** how long an interview lasts, its scores, and a kept check.
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

When time runs out (Volume 17, prompt 1): `backend/tests/test_interview_time_runs_out.py` (one pass
closes an interview past its time and it reads the same as one closed on read; one not yet due is
untouched; a read and a pass close it once, scored once; a pass is bounded, oldest deadline first; a
career round is closed without the coach; an export after a pass shows it ended; housekeeping runs
the step and the jobs thread every minute; a changed code part says which lines were added, by
number, and how many removed, and the conversation how many messages came after; only line digests
are kept with the check, never a line; a check kept before this says what it said), on SQLite and
PostgreSQL as the app's role, and `feedbackCheck.test.tsx` (+2: each changed part said, the added
lines read from the kept code; an older check names the parts only).

A check before time ran out: `backend/tests/test_feedback_check.py` (a check then a time-out is
recorded as checked, with its time, and the interview's conditions say so; a check, a message, a
time-out names "The conversation so far"; no check is unchanged; code checked in the editor but never
sent is said; a confirmation after another tab moved the interview on is refused with a fresh preview
and keeps nothing; each confirmation replaces the last; confirming sends nothing, scores nothing,
keeps the clock and stores no text; another account can't confirm or read it; a career interview has
nothing to check; the export carries its time and fingerprint, never the text) and
`frontend/src/test/integration/feedbackCheck.test.tsx` (the button, the one-sentence status, the
refusal from another tab, the review's wording with the time).

## Limits

- Every coaching operation is previewed: the code review, hints, failure explanations and the coding
  interviewer (its messages and its feedback). An interview that runs out of time is scored without a
  preview, from the material listed above; a check confirmed before it is compared part by part,
  and each changed part says how (lines added and removed, messages sent after), the added code
  lines shown from the kept code. Lines are matched in order, so a moved line counts as removed and
  added; only the first 20 added lines are listed. A check kept before Volume 17 names the parts
  only.
- An interview past its time is closed by housekeeping within about a minute (the jobs thread's
  pace), or sooner by a read; a deployment that runs no jobs thread (`BACKGROUND_JOBS_IN_API` off
  and no worker) closes it on read only, as before.
- An explanation's choices apply to the first one asked for: one is kept per submission, so asking
  again with more (or less) shows the kept one.
- The preview shows what CodeCoach sends. What an outside service does with it is governed by
  that service's terms (docs/PRIVACY.md); CodeCoach can't make promises about it.
- Secret-looking strings are found by patterns (keys, tokens, `password = "…"`); other personal
  text in code is sent as written, and the preview is where you see it.
