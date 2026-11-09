# When an action fails (Volume 7, prompt 6)

A failed request leaves the learner with their work on screen and one clear next step, shown next
to the control that failed. A timeout is never treated as proof that nothing happened. A request
that may have arrived is sent again only in a way the server recognises, so nothing is done twice.

## Before and after

> **Before.** On a train, a learner presses **Get a hint**. The server answers; the connection
> drops on the way back. The page says "Can't reach the CodeCoach server". They press the button
> again: the AI is asked again, a second of their 50 daily requests is used, and the hint may
> read differently.
>
> **After.** The page says: *"The hint didn't go through. No reply came back, so we can't tell
> whether it arrived. Trying again is safe: it won't be done twice."* They press **Try again** and
> get the hint the server had already written. The counter shows 49/50 left, not 48/50. Their
> code was never touched.

The same goes for Submit: pressed again with the code unchanged, it sends the same request, and
the server returns the submission it already made. That is shown in the browser against the real
API (`frontend/e2e/recovery.spec.ts`).

## One pattern, where it fits

`ActionError` (`frontend/src/components/ActionError.tsx`) shows a failed action next to its
control:
- what didn't happen ("Your submission didn't go through."), and why in the learner's terms;
- the wait the server asked for, counted down;
- **Try again**, enabled once the wait is over;
- **Sign in again** when the session ended;
- a short reference for support, only for a fault on our side.

Only the first sentence is announced (`role="alert"`), once. The countdown sits outside it, so it
isn't read out every second. Nothing replaces the page.

| Kind (`failureKind`) | From | The way on |
|---|---|---|
| offline | no reply came back | try again; "safe" said only where the request is keyed or deduplicated |
| busy | 429 | the server's wait, then try again |
| unavailable | 503 | the server's message (and wait, if any), then try again |
| invalid | 400, 413, 422; a wrong password | fix the input (sign-in marks the field) |
| signed_out | 401 for a lost session | sign in again; the draft stays |
| forbidden, not_found, conflict | 403, 404, 409 | the server's message; no retry |
| server | other 5xx | try again, with a reference for support |

**Waits.** `ApiError.retryAfterSeconds` is read from `details.retry_after_seconds` or the
`Retry-After` header, in seconds or as an HTTP date. The API now exposes that header to the page
(CORS). Only the action that was refused waits; everything else stays usable:

| Refused | What waits | What stays usable |
|---|---|---|
| Submissions (too many, server busy) | Run and Submit | the editor, the coach |
| AI budget spent, or another AI request running | the hint, or the review | the editor, Run, Submit |
| Interview Start | Start | — |
| Sign-in | Sign in | the email and password fields |
| Data export | Download | — |
| Resend verification | Send a new code | — |

## How a write whose answer was lost is reconciled

| Action | Mechanism | Sending it again |
|---|---|---|
| Submit / Run | `client_request_id`. The same code and mode reuse the key: from **Try again** or from the main button | the same submission. A changed code is a new submission |
| Hint, code review (new) | `client_request_id`, unique per account (migration `9a0b1c2d3e4f`) | the stored answer; no provider call, no budget used, even if the budget ran out since |
| New story (new) | `client_request_id` while the form is unchanged since the attempt | the story the first request made |
| Written answer (career questions) | keyed route, and a check of the saved answers after a dropped connection | the same answer |
| Interview Start | one in progress per account (database) | `409` with the Resume card |
| Interview message | `client_request_id` + `after_seq`; the page re-reads after a dropped connection | found in the transcript, not sent again |
| Round answer | one answer per question (database) | the same text: 200; different text: 409, kept on screen |
| Finish / end early | compare-and-set | the same evaluation |
| Notes (create) | `client_request_id` | the same note |
| Explain a failure | cached per submission | the same explanation |
| Restore | the same file changes nothing | no change |

**Can't yet be retried safely** (a repeat may do something twice or misread itself):
- **Story, kit and note *updates*.** These are revision-checked. A save whose answer was lost, sent
  again, meets its own new revision and is shown as a conflict with both versions. Nothing is lost,
  but it reads as "changed elsewhere".
- **Note "save mine as new"** (after a conflict). Unkeyed: a lost answer, retried, can make a
  second note.
- **Guest sessions.** A lost answer leaves an unused guest account, removed by guest retention.
- **Register.** A lost answer, retried, gets `409 email_taken`. Signing in then works. The page
  doesn't recognise this case itself.

## Cancelling

Nothing in the app cancels server work, and no page claims to.
- **Judge polling.** After 15 minutes the page stops checking and says the submission will still
  be judged.
- **Interviews.** "Leave for now" keeps the interview running, and says the clock keeps going.
- **Leaving a page with a hint or review in flight.** The browser stops waiting, but the server
  finishes. The hint ladder and History show the answer later.
- **Leaving a page** releases that page's microphone and listeners, and nothing of another tab's.

## Other fixes

- **Workspace.** A failed submit no longer replaces the results panel: the last verdict stays. A
  failed refresh of a shown result says so beside it. A judge outage (`judge_unavailable`,
  `judge_busy`, `execution_disabled`) refreshes the judge banner at once, not on the next page
  load.
- **Live interview.** A failed refresh (focus, the clock, the check after a dropped send) used to
  replace the interview with an error page. Now the interview stays, with a notice and **Check
  again**.
- **Session ends mid-work.** The draft (code, written answer) stays on screen until someone signs
  in. Before, the editor switched to the signed-out copy, and the work seemed to vanish.
- **Sign-in.** A malformed email is marked on its field, not shown as "Request validation failed".
- **Verification resend.** Any 429 counts down the server's wait, not only `resend_cooldown`.
- **History filters.** Two changes in quick succession (a career, then an activity type) used to
  keep only the second: each built on the URL of the last render. The full browser run caught it
  on a loaded machine. Each change now builds on the latest one; a test fails on the old code.

## Tests

- **Backend**, `backend/tests/test_recovery_requests.py` (7):
  - a hint sent again: the first answer, one coach call, the budget used once, even when spent
    since;
  - a review sent again: the same; without a key, a new review as before;
  - a key for a different action or level: 409;
  - keys are per account;
  - a story created again: the same story;
  - waits in body and header, and the header readable cross-origin.

  Negative control: with the replay removed, 3 of them fail.
- **Frontend:**
  - `src/lib/retry.test.ts` (28): Retry-After in both forms; failure kinds; wait wording.
  - `src/test/integration/recovery.test.tsx` (13):
    - Submit after a lost answer reuses the key;
    - a judge outage keeps the last result and refreshes the banner;
    - a submission rate limit holds Run and Submit, but not the coach;
    - the wait ends, and Try again works from the keyboard;
    - a lapsed session keeps the draft;
    - a lost hint or review is retried with the same key, and Review again is a new review;
    - `ai_request_in_progress` waits, then comes back;
    - sign-in: a countdown, the fields kept, the field error;
    - interview Start: an AI budget wait;
    - a lost story create reuses the key;
    - a live interview whose refresh fails stays.

    Negative controls: with each of the four fixes removed (key reuse, hint keys, lapsed scope,
    interview refresh), its test fails.
- **Browser**, `frontend/e2e/recovery.spec.ts`. Against the real API, a submission and a hint are
  done on the server and their replies dropped:
  - Submit again returns the same submission id;
  - Try again returns the same hint, and the budget counter drops by one.

## After a reload (Volume 8, prompt 1)

A key used to live only in the page's memory, so a lost reply followed by a reload could do the
same thing twice. Now, for the actions below, the key is written to this browser **before** the
request is sent. After a reload the page asks the server what that key made, and shows it; it
doesn't send again.

- **What's kept:** the account id, the kind of action, its target (a problem's slug, or "new" for a
  story), the key, a fingerprint of exactly what was sent, and the time. Never the content (code
  and story text stay in their own draft storage) and never a credential. It's stored under
  `codecoach.pending.v1.<account id>` in this browser.
- **How long:** until the action is resolved (answered, refused, or checked after a reload), and at
  most 24 hours; at most 20 records per account, oldest first out. A deliberate sign-out deletes
  the account's records. A session that lapsed keeps them for the same account; another account
  never reads them.
- **The check is a read.** `GET /api/v1/me/requests/{key}` searches only the caller's own
  submissions, AI requests, stories, answers and notes. It says what the key made (and whether a
  submission is still queued) or 404, "no record". A key is never permission for anything.
- **What the learner sees** (`EarlierActionNotice`):
  - "Your submission from 21:04 arrived. Its result is below."
  - "The submission you sent at 21:04 never arrived. … Sending now is a new submission."
  - "Couldn't check … It may have arrived. Sending the same thing again is safe", with **Check
    again**.
  - When the code in the editor differs from what was sent, it says so. The current code stays
    the draft; nothing old is replayed under it.
- **Same content, same key, across tabs.** Pressing the button again with unchanged content, from
  this tab after a reload or from another tab, reuses the stored key, so the server makes it once.
  Changed content is a new intent with a new key.
- **Nothing costly starts by itself.** A reload only reads. A hint, review or submission is sent
  again only when the learner presses its button.

| Action | Survives a reload | Result shown after a reload |
|---|---|---|
| Submit and Run | yes | the submission's result (or "saved, not run yet") in the results panel |
| Hint | yes | the hint in the ladder (from saved history), charged once |
| Code review | yes | a link to the saved review in History |
| New story | yes | a link to the saved story; the page keeps the draft |
| Career answer, interview answer or message, note, drill, story update | **not yet**: their keys still live in the page | — |

Tests:
- `frontend/src/lib/pendingIntents.test.ts` (5): one key per intent across tabs, changed content,
  no content kept, per account, expiry and bound, storage refused.
- `frontend/src/test/integration/durableActions.test.tsx` (6):
  - submission found;
  - never arrived;
  - can't check, then checked, with the changed-code note;
  - hint found and charged once;
  - story found;
  - another account doesn't check, and sign-out removes the record.
- `backend/tests/test_request_outcome.py` (4) and the cross-account route walk.
- In the browser against the real API, `frontend/e2e/durable-actions.spec.ts`: a submission and a
  hint whose replies are dropped, a reload, the same records, one charge, and a second reload that
  asks nothing.

## Limits

- The updates listed above still read a lost-then-retried save as a conflict.
- Waits come from the server. A proxy that rate-limits without `Retry-After` gives no countdown,
  only the message.
- The judge's 503s carry no `Retry-After`, so there's no countdown for them.
- Submissions, hints, reviews and new stories keep their key across a reload (above). The other
  keyed actions still keep it in the page's memory: a lost answer followed by a reload starts a
  new key, and may be done twice. History shows both.
- The browser record needs local storage. When this browser refuses it (some private modes), the
  key lives in the page only, as before.
- The server keeps the evidence as long as the record exists. If what a key made was deleted
  (account or guest clean-up), the check says "no record", which is then all anyone can know.
- On SQLite (local development), two copies of the same AI request at the same instant can both
  reach the provider. The database keeps one answer, and both get it. PostgreSQL's per-account
  lock prevents the second call.
