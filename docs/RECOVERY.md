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
| Hint, code review (new) | `client_request_id`, unique per account (migration `9a0b1c2d3e4f`), bound to the exact code, level and submission (`06088140741a`) | the stored answer; no provider call, no budget used, even if the budget ran out since. Other code under the key: 409 |
| New story (new) | `client_request_id` while the form is unchanged since the attempt | the story the first request made |
| Written answer (career questions) | keyed route, and a check of the saved answers after a dropped connection | the same answer |
| Interview Start | one in progress per account (database) | `409` with the Resume card |
| Interview message | `client_request_id` + `after_seq`; the page re-reads after a dropped connection | found in the transcript, not sent again |
| Round answer | one answer per question (database) | the same text: 200; different text: 409, kept on screen |
| Finish / end early | compare-and-set | the same evaluation |
| Notes (create) | `client_request_id` | the same note |
| Note "Keep both" after a conflict | `client_request_id` per decision + `copy_of`, and a copy receipt (Volume 8 prompt 4) | the same copy. Made, then deleted: 410 `copy_deleted`, not made again |
| Story, note, kit, whiteboard draft, reflection (update) | `client_request_id` per save, and a receipt kept with the update (migration `7045bdb6a532`, Volume 8 prompt 3) | "your save went through as version N". Changed since: both versions, compared |
| Explain a failure | cached per submission | the same explanation |
| Restore | the same file changes nothing | no change |
| Guest start, register (new) | this browser's HttpOnly anchor cookie, recorded with the account (Volume 8 prompt 6) | the same guest; the same account, with the right password, and no second email. Without the anchor: as before (below) |

**Can't yet be retried safely** (a repeat may do something twice or misread itself):
- **Guest sessions without the anchor** (another browser, cookies blocked or cleared, over an
  hour). A lost answer leaves an unused guest account, removed by guest retention.
- **Register without the anchor.** A lost answer, retried, gets `409 email_taken`. Signing in then
  works.

## Cancelling

Nothing in the app cancels server work, and no page claims to.
- **Judge polling.** After 15 minutes the page stops checking by itself, says the submission stays
  in the queue and will still be judged, that leaving the page doesn't stop it, and offers **Check
  again** (one read). A submission that was accepted can't be cancelled.
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

## What a key identifies (Volume 8, prompt 2)

A key (`client_request_id`) stands for one account's one intent. Sent again unchanged, a request
gets the first result back. Sent with anything different, it's refused with **409
`idempotency_key_reused`**. It isn't answered with the old result, isn't executed, and isn't
charged. Before this, several creates matched a key alone or only part of it. A hint resent with
different code got the old hint back. A story, application, event, schedule entry, drill attempt
or shared-link feedback resent with different content got the first record back, and the new
content was silently dropped.

The server compares what it was sent. It never takes a hash from the browser. Where the record
can be edited later, it keeps a digest of the create's validated input beside the record
(`request_fingerprint`, `"v1:" + sha256`, migration `06088140741a`;
`backend/app/services/request_keys.py`). Where the record never changes, it compares the record
itself.

| Operation | A key is unique per | Compared on a resend |
|---|---|---|
| Submit / Run | account | problem, mode, code (the saved submission) |
| Hint | account | action, problem, level, the code as sent (digest) |
| Code review | account | action, problem, the code, the submission it's about (digest) |
| Career answer | account | track, question, answer, story, revised answer (digest, since Volume 7) |
| New story | account | the create's fields (digest; the story may be edited since) |
| Application, application event | account; per application | the create's fields (digest) |
| Schedule entry | account | activity, date and time, duration, note (digest; it may be moved since) |
| Drill attempt | account | drill, words, source, timed seconds (the saved attempt) |
| Interview message | interview | the message text (the saved turn) |
| Shared-link feedback | link | the reviewer (account, or the name a guest gave) and every word |
| New note | account | what it's a note on. Text may differ: autosave resends a lost create with newer text, gets the note back, then saves the text as an update with its revision check |

- **Not an editor conflict.** `idempotency_key_reused` means "this key was already used for
  something else": send it with a new key. A revision conflict (`story_conflict`, `note_conflict`,
  `interview_advanced`) means "this changed elsewhere since you loaded it". They're different
  codes with different choices.
- **Another account, another reviewer.** Keys are looked up within the caller's own records (a
  link's feedback within that link). Another account's identical key is simply a different key. On
  a shared link, where several people send feedback, another reviewer who sends someone's key
  gets the same plain 409, whatever words they send. It carries no id, content, time or
  fingerprint, so it reveals nothing about the first request.
- **A blank key is no key.** `""` or spaces used to be stored as a key, so a second, different
  create with a blank key came back as the first. Blank now means none, on every route.
- **Older clients.** Rows from before the digest have none. They're matched as before (a hint on
  action, problem and level), so a resend from an older page still gets its answer. Older routes
  still accept the short keys they always did (drills, schedule, applications, events).
- **The browser side.** Each form keeps one key per exact content (`useRequestKey`, and the
  persisted intents of prompt 1), so an edited retry is sent as a new request rather than refused.
  A hint's key now covers the code too, and a review's covers the submission.

### What is guaranteed, and what isn't

| | Guarantee | How |
|---|---|---|
| **Database effects** | A keyed create makes at most one record per key, even with two copies at once. A copy that loses the race gets the winner's record if it's the same intent, and a 409 if not | the unique constraint on (owner, key), with the intent compared again in the losing path, which used to return the winner without looking. Two event copies at once used to break the constraint with a 500 |
| **Budget** | A keyed hint or review is charged once. A resend after the budget ran out still gets its answer. A refused or failed request is never charged | the charge is the saved interaction, in the same transaction as everything else: no record, no charge. On PostgreSQL, a per-account turn makes the count exact |
| **External calls** | On PostgreSQL, two copies of one request can't both reach the provider: the second gets **429 `ai_request_in_progress`** (`Retry-After: 2`), then the stored answer. **Not exactly-once.** If the server dies after the provider answered but before the answer was saved, nothing is recorded or charged, and the next press calls the provider again | the provider (Anthropic's Messages API) takes no request key, so there's nothing to reconcile with. The call is bounded (25 s per attempt, at most 45 s, at most `AI_MAX_CONCURRENT_CALLS` at once) |

**The crash windows**, for a hint or review on PostgreSQL. The record, the charge, the progress
event and the per-account turn are one transaction, held across the bounded provider call. So:

- **Before admission** (validation, replay check, unlock check): nothing has happened. The lookup
  says "no record". A resend is a fresh request.
- **After the budget check, during the call, or after the answer but before it's saved:** if the
  process dies, PostgreSQL ends the transaction. Nothing is recorded or charged, and the turn is
  released with the connection. There's no reservation row to go stale and lock the learner out,
  and nothing retries by itself. The provider may have billed that call. The learner sees "the
  hint didn't go through", and pressing again makes one new call.
- **While it's still running,** the lookup answers **429 `request_in_progress`** instead of "no
  record" (it sees the turn in `pg_locks`, without taking it). The reloaded page says "still being
  answered", asks again once by itself after the wait, then offers **Check again**.
- **Failure:** a provider error is answered by the offline coach, recorded once, labelled as a
  fallback. Any other error rolls everything back, as above.

The trade: the transaction holds a database connection for up to 45 s. That's measured and capped
(`docs/HARDENING.md`, the load test). A reservation table would free the connection, but it would
bring stale reservations and a clean-up job. We kept the shorter list of failure modes.

### How long a replay is supported

As long as the record the key made exists: for an account, until it's deleted; for a guest,
until the guest retention clean-up (30 days by default). The browser asks about a key for at most
24 hours (prompt 1), well inside that. Once the record is gone, the lookup says "no record" and a
resend is new work, charged once. Nothing pending is deleted while it can still complete: a hint
or review in flight has no record to delete until it's saved.

Tests:
- `backend/tests/test_request_identity.py` (16, SQLite and PostgreSQL):
  - hint key with other code, level, problem or action; review key with other code or submission;
  - rows without a digest, matched as before;
  - the digest is never in history, lookups or exports;
  - the race path: a different request with the same key, saved in between, is refused, not
    returned;
  - two copies at once, synchronised by a gate in a synthetic provider (no sleeps): one call, one
    row, one charge. On PostgreSQL the second gets 429, and the lookup says "still being answered";
  - a crash after the provider answered: nothing recorded or charged, then one clean retry;
  - provider failure, then fallback, recorded once;
  - the record deleted: "no record", and a resend is new;
  - stories, applications, events, schedule, drills, notes, interview messages and shared-link
    feedback with changed content;
  - two simultaneous events (a 500 before);
  - another reviewer's key on a link reveals nothing;
  - blank keys.
- Negative controls: each fix undone in turn fails its test (all ten, the lookup one on
  PostgreSQL).
- `backend/tests/test_shares.py`: a changed retry is now refused. It used to be asserted as
  "duplicate", with the new words dropped.
- Frontend: `requestKey.test.ts`, the in-progress notice in `durableActions.test.tsx`.

## Recovering a save whose reply was lost (Volume 8, prompt 3)

Stories, notes, kits, whiteboard drafts and reflections are saved against the revision the page
started from, and a newer revision is a conflict. A save that went through, but whose reply never
arrived, used to meet its own new revision when the page sent it again. It then read as "changed
in another tab", with the learner's own text on both sides. Now each save carries a key, and the
server keeps a **receipt** of the accepted save in the same transaction as the update
(`update_receipts`; `backend/app/services/update_receipts.py`).

A receipt records the entity, the revision the save started from, the revision it produced, and a
digest of the update. It holds no content. A retry with that key, the same entity, the same base
and the same content is answered with the entity as it is now, plus `save_replay:
{accepted_revision, current_revision}`:

- **Same revision** (`current_revision == accepted_revision`): "Your earlier save went through as
  version N." Only what was sent is marked saved. Text typed after sending stays unsaved and is
  saved next, against version N.
- **Changed since** (`current_revision > accepted_revision`, another tab or device saved after
  it): the page doesn't replace itself with the newer version, and nothing is overwritten. The
  comparison panel opens, saying "Your save went through as version N. This story was changed after
  that", with the learner's version beside the newer one. The learner chooses, as for any conflict.

What stays protected:
- **A real conflict is still one.** Another tab's save, with its own key, gets the usual
  `stale_revision` / `note_conflict` with both versions. Its panel still says "not saved".
- **The same key with other content, another base or another entity** is refused (409
  `idempotency_key_reused`). It can't be used to skip the revision check.
- **Proof is the receipt, never a resemblance.** A record that happens to equal what was sent isn't
  taken as evidence. Without a receipt (no key, an older page, or it expired), a stale save is a
  conflict, as before.
- **Deleted or not yours:** the owner-scoped lookup comes first (404). A retry never recreates a
  deleted story, and never shows another account's version. Keys are per account.
- **Two copies at once** (PostgreSQL): the second waits on the row lock, then finds the first's
  receipt. One revision results, and both replies say so.

| Endpoint | Key in | Base | On a recovered save |
|---|---|---|---|
| `PATCH /me/stories/{id}` | `StoryUpdate.client_request_id` | `expected_revision` | the story now + `save_replay` |
| `PATCH /me/notes/{id}` (text changes) | `NotePatch.client_request_id` | `base_revision` | the note now + `save_replay` |
| `PUT …/events/{id}/kit` | `KitUpdate.client_request_id` (with `expected_revision`) | `expected_revision` | the kit now + `save_replay`, also when the copy lost the race |
| `PUT /me/whiteboard/{prompt}/draft` | `WhiteboardDraftIn.client_request_id` | `expected_revision` (0 for the first) | the draft now + `save_replay`; a discarded draft: 404, not recreated |
| `PUT …/events/{id}/reflection` | `ReflectionIn.client_request_id` | `expected_revision` (0 for the first) | the reflection now + `save_replay`; deleted since: 404 |

**The browser side.** Each editor keeps one key per exact save (`useRequestKey`), so pressing Save
again after a lost reply resends the same save. Note autosave keeps typing, so after a lost reply
it first resends that exact save, with its key, to learn what happened, then sends the newer text
against the accepted revision. Its own earlier save is never mistaken for a change made elsewhere.
Pin and archive changes on notes aren't revision-checked and need no receipt.

**How long.** Receipts are kept 7 days (`UPDATE_RECEIPT_DAYS`). The browser retries within the
visit, and a persisted intent lasts at most a day. Housekeeping deletes older receipts daily. An
expired receipt means the retry is treated as a new save, which is a conflict if it's stale: safe,
and the learner chooses. Receipts aren't exported, aren't copied by `copy-db` (a retry from before
a move is a save like any other), and go with the account. They're outside row-level security,
because they hold no content and housekeeping purges them across learners; every lookup filters by
account (`db/rls.py`).

Tests:
- `backend/tests/test_update_replay.py` (8; SQLite and PostgreSQL):
  - lost, then retried twice: one revision;
  - another device's later save kept and reported;
  - a real conflict, and a reused key with other content or base;
  - a deleted story, and another account;
  - expired evidence, and housekeeping;
  - a receipt holds no content;
  - two copies at once (PostgreSQL);
  - notes, kits, reflections and whiteboard drafts.
- `frontend/src/test/integration/updateReplay.test.tsx` (4): recovered as the learner's own save;
  changed on another device (both shown, nothing replaced); a real conflict still says "not
  saved"; note autosave resends the lost save, then the newer text.
- Negative controls: 5 backend and 4 frontend, each caught.
- In the browser against the real API, `frontend/e2e/update-replay.spec.ts` (2). The second is the
  full demonstration: a save whose reply is dropped; another tab saves version 3; Save again; both
  versions shown, the newer one kept on the server
  (`docs/screenshots/durable/lost-save-recovered.png`).

## "Keep both" makes one copy (Volume 8, prompt 4)

After a note conflict, **Keep both** saves the learner's version as a separate note and puts this
note back to the saved version. It used to be an unkeyed create, so a double click or a retry after
a lost reply could make two copies.

- **One decision, one key.** The text on the page when the button is pressed is captured. The
  decision gets one key, written to this browser before sending (`note_copy`, the persisted intents
  of prompt 1). A double click, Retry same copy, or a reload sends that key. Changed text, or Make a
  new copy, is a new decision with a new key.
- **The server** (`POST /me/notes` with `copy_of` and `client_request_id`;
  `NoteService.copy`) writes the note and a copy receipt in one transaction. The receipt says which
  note the key made, and holds a digest of the text, not the text. The same key returns that note,
  even when two copies arrive at once (the note's unique key, then the receipt). The same key with
  other text is a 409. A copy that was made and then deleted, even after it was purged, is
  **410 `copy_deleted`**, never made again by a retry.
- **The source note is only read.** It's never changed. The copy takes the source's question or
  problem link if the source is the caller's own. Another account's note id is treated exactly
  like a missing one, so the response doesn't reveal whether it exists. No link back to the source
  is kept. Nothing else is carried over (no pin, archive, key points or share).
- **What the learner sees:**
  - while sending: "Saving your version, as shown above, as a separate note…", with the button
    disabled;
  - no reply: "We couldn't confirm the copy of your version. It may have been made", with **Check
    copy** (a read) and **Retry same copy** (the same key). There's no unqualified create button;
  - made then deleted: "That copy was made, then deleted. Nothing was made again", with **Make a new
    copy**.

  **Copy my text** stays available throughout. Neither a failure nor a pending copy closes the
  panel or touches the text on the page. When the copy is made, focus moves to the result, with a
  link to the new note. Text typed after pressing Keep both isn't in the copy: the page says so,
  keeps it, and leaves the conflict open.
- **After a reload:** the note's page checks the stored key (a read) and says "Your copy of your
  version from 21:04 arrived" with **Open the copy**, or that it never arrived. It never sends it
  again.
- **How long:** a duplicate is refused for as long as the copy exists. After a deletion, the
  receipt keeps a retry from remaking it for 7 days. The browser asks for at most a day.

Tests:
- `backend/tests/test_note_copies.py` (7; SQLite and PostgreSQL):
  - a double click and a retry make one note, and the source is unchanged;
  - changed text under a key, and a deliberate second copy;
  - made then deleted, and then purged;
  - a missing source and another account's source look alike;
  - a key is required;
  - the receipt holds no content, and expires;
  - two at once (PostgreSQL).
- `frontend/src/test/integration/noteCopy.test.tsx` (6):
  - a double click, and focus on the result;
  - a lost reply, then Retry same copy;
  - Check copy;
  - made then deleted, then a new copy;
  - text typed after pressing;
  - a reload.
- Negative controls: 4 backend, each caught. One finding: removing only the up-front check isn't
  caught, because the note's unique key and the race path still return the copy (two layers, by
  design). Removing both is caught.

## Starting as a guest or registering (Volume 8, prompt 6)

A guest start and a registration each make an account and a session in one request. If the reply
was lost, the page had neither: retrying made a second guest (the first left unused), or answered
"email taken" for the account the first request had just made.

- **An anchor first.** Before either, the page calls `POST /auth/create-anchor`. The server sets
  `cc_create`: a random value in an HttpOnly, SameSite=Strict cookie, sent only to `/api/v1/auth`,
  for an hour. Page scripts can't read it and other sites can't send it. A browser that already
  has one keeps its value (renewed). If this call fails, the create goes ahead as before.
- **The create records it.** In the same transaction as the account, `create_intents` stores the
  anchor's SHA-256 hash, the kind and the account (migration `fa8c2d7ff836`). Not the anchor, not
  the password, not a token.
- **Sent again from the same browser:**
  - a **guest start** returns the guest that anchor made: `200` with `X-Account-Resumed: guest` and
    a new session, not a second guest. A guest has no password or email; this browser's anchor is
    what ties it to the guest, as the session cookie would have. Two tabs starting at once get one
    guest;
  - a **registration** is resumed only when the email and the password are right too, as a sign-in
    would be: `200` with `X-Account-Resumed: register`. No second verification email. Without both,
    the usual `409 email_taken`.
- **Never resumed:** another browser (its own anchor); a made-up value (an unknown hash; a short
  one is ignored); no anchor; an anchor over an hour old; after a deliberate sign-out on this
  browser (its intents are deleted, so even a cookie whose removal never arrived finds nothing);
  after sign-out everywhere; a guest that has since become a full account; a deleted account. A
  request id in page storage plays no part, and no email, guessed id or key grants anything.
- **The page** (`createAccount` in AuthProvider): when the reply is lost, it first asks whether the
  lost reply's session cookie arrived (a refresh). That session is used only if it is the account
  being made (a guest, or the address being registered); then nothing is sent again. Otherwise it
  sends the same request once more and the anchor check answers. If that reply is lost too, it
  says: "We couldn't confirm your account was created. It may have been. When you're online again,
  press the same button again: on this browser it finds what was made instead of making another."
  It says nothing about whether the address has an account. Any other answer (a validation error,
  `email_taken`, a rate limit) is shown as before, without a resend.
- **Unchanged:** rate limits (the resend counts like any request), session rotation, the
  verification screens and their honest delivery status, the return path after sign-up, guest to
  account conversion, and guest retention. Nothing is merged or transferred by an email match.
- **How long:** an intent lasts an hour from the create, and the daily housekeeping purges older
  ones. The cookie lasts an hour from the last anchor request.

What this doesn't do: it makes **fewer** orphan guests, not none. A retry from another browser,
with cookies blocked or cleared, or after an hour makes a new guest, and the earlier one, if
unused, goes with guest retention (30 days by default). Registration's `email_taken` answer
already says that an address has an account; that public answer is unchanged here.

Tests:
- `backend/tests/test_create_recovery.py` (10; SQLite and PostgreSQL):
  - the anchor cookie's flags, and that it's kept for a retry;
  - a lost guest start resumes the same guest; without an anchor, a new guest each time;
  - another browser, made-up anchors, and a sign-out (with the old cookie sent again);
  - an expired anchor, and a guest that became an account;
  - a lost registration resumed once with one email; the wrong password or another browser gets
    the usual answer, and signing in works;
  - sign-out everywhere, two tabs at once, and the hourly purge.
- `frontend/src/test/integration/createRecovery.test.tsx` (7): the resend, a session cookie that
  arrived, a session that isn't the account being made, a resumed registration, a double loss and
  pressing again, an ordinary error without a resend, and no anchor.
- `frontend/e2e/create-recovery.spec.ts` (2, real API): a lost guest reply and a lost registration
  reply, each answered by the same account (one verification email); the anchor isn't readable
  by the page; another browser gets its own guest.
- Negative controls: 8 backend, 4 frontend, 1 browser, each caught. One finding: removing the
  server-side forget on sign-out was missed at first, because the cookie's removal alone hid it;
  the test now sends the old cookie again.

## When the judge is busy, unavailable or still judging (Volume 8, prompt 7)

A run or submission the judge refuses is not a job: nothing was queued or saved, and its request
key isn't used up. The page keeps the code and the last result, says which case it is, and offers
the way on that fits. Nothing is sent again by itself, and no wait is invented.

| Case | Answer | A wait? | The way on |
|---|---|---|---|
| Too many submissions in a minute | 429 `rate_limited` | yes: when the oldest of the last minute's submissions leaves the window (counted from the saved rows) | Try again, enabled when the wait is over |
| Still being judged (one pending per account by default) | 429 `submission_pending`, with the caller's own pending submission's id, problem and mode | no: how long judging takes isn't known | **Show its status** (or Open that problem). No Try again |
| Queue full (all accounts) | 503 `judge_busy`, "Nothing was saved" | only when the judge finished something in the last 5 minutes: the average gap between those completions (roughly how often a place frees up), at least 5 s and at most 120 s. It's a hint for when to try again, not when anything will be judged, nor a queue position | with a wait: Try again after it, and the page says what the wait means. Without: **Check availability** and Try again |
| Judge unreachable, not ready or misconfigured (Run only; Submit still queues) | 503 `judge_unavailable` | no: the server only knows it's down | **Check availability** (one capabilities read; the server probes the judge at most every 15 s), **Submit instead (it waits in the queue)** |
| No judge on this server | 503 `execution_disabled` (Run); Submit saves without a verdict | no | **Save attempt instead**, **Ask the coach for a review**. No Try again: it can't help |
| Accepted, reply lost | (prompt 1) | — | the same key, sent again or checked after a reload, finds the job |
| Accepted, still running when the tab returns | 202, then polling | — | the result panel polls (1.5 s, then 5 s after a minute, stops after 15 min with Check again) |

Every case also offers **Copy code**. The draft itself is kept in this browser as before.

- **Waits are counted from a deadline**, the moment the answer arrived plus the wait, so a tab the
  browser suspended shows the right time when it wakes, and "You can try again now." is said once
  when it's over (the seconds themselves aren't announced). Its end enables the button; it never
  sends anything.
- **What counts as a wait:** whole seconds or an HTTP date. A date is read against the server's
  `Date` header when there is one (now exposed to the page), so a wrong clock on this device doesn't
  stretch or skip it. Malformed, negative, or longer than a day: no wait (Check availability or a
  deliberate retry instead). Another 429 after a wait starts a new countdown from its own deadline.
- **Two tabs at once:** the same code in two tabs carries the same key, so the server makes one
  submission. Different code in two tabs is admitted one at a time per account (a PostgreSQL
  advisory lock around the admission checks), so "one pending" holds; on SQLite (development) two
  simultaneous presses can both be admitted. The queue-full check is across accounts and isn't
  locked: under a burst it can let a few more in than the limit.
- **Labels:** when the editor has changed since, the result says it's for the code as submitted
  (or as run) and when, so an earlier verdict is never read as the current code's.
- **What this doesn't measure:** the busy wait is derived from completions, not from the number of
  workers or the queue's length, and promises nothing about when a submission would be judged.
  The real judge (gVisor) path is exercised by CI's sandbox job on every push; it wasn't run here
  (no gVisor in this environment), and no test fills the real judge's queue.

Tests:
- `backend/tests/test_judge_admission.py` (9; SQLite and PostgreSQL): the measured wait and its
  bounds, no wait with nothing finished, "still being judged" naming only the caller's own
  submission, a refusal that saves nothing and uses no key up, the same key after a lost reply,
  Run while unavailable and not configured, and two tabs at once (PostgreSQL).
- `frontend/src/test/integration/judgeAdmission.test.tsx` (12): a wait across a suspended tab
  with nothing sent at its end; Check availability; malformed, over-a-day and absurd values; an
  HTTP date against the server's clock; another 429; Show its status; not configured; unavailable
  Run; the result label; Check again. `src/lib/retry.test.ts`: the parser's bounds.
- Negative controls: 1 backend (the lock removed: both tabs admitted), 4 frontend, each caught;
  the over-a-day test was strengthened after its first control was missed (its value was also
  refused by the length check).

## When a session ends (Volume 8, prompt 8)

A session can end two ways, and they're kept apart:

| | A session that ended by itself (expired, or revoked elsewhere: sign out everywhere, a password change) | A deliberate sign-out on this device |
|---|---|---|
| Work on screen | Stays. Public pages (a coding problem, a career question) keep showing it; account-only pages go to sign-in, and their unsaved text is still in this browser | Gone, after a warning if anything is unsent |
| Unsaved drafts in this browser | Kept, under that account. Shown only when that account is signed in here again | Deleted (OFFLINE.md lists every kind) |
| Unresolved actions (prompt 1's records) | Kept, under that account, for the same 24 hours | Deleted |
| Saving to an account | Nothing is saved to an account until someone signs in; the banner says so | — |
| What the banner says | "Your session ended. Please sign in again.", what's kept and for whom (it names nobody), and **Sign in again**, which comes back to this page | Nothing: going home is the answer |

- **Signing in again as the same account:** the page reloads its data as that account. Drafts
  come back as they were (the editors that compare against a saved revision still do, so a story
  or note changed elsewhere meanwhile is compared, not overwritten). Unresolved actions are
  checked with a read; nothing is sent again, and no hint, review, submission or transcription
  restarts because a session was renewed. The microphone never starts by itself.
- **Signing in as another account:** that account sees its own drafts or the starter content.
  Nothing of the earlier account's is shown, checked, sent, attached or moved, because drafts and
  action records are kept per account and read only for the account signed in. The earlier
  account's copies stay where they were, locked to it.
- **Another tab signs in** while this tab's session had ended: this tab checks once (one refresh,
  when the device's record changes) and carries on as whoever is now signed in on this browser,
  with the same per-account rules.
- **Storage unavailable:** the banner says this browser can't keep a copy, and to copy anything
  needed before leaving the page.
- **Failed sign-in, unverified account:** the sign-in page shows its usual answer; the banner
  stays until a sign-in succeeds; nothing loops. The return path is the existing validated one:
  the page's own path, never its text.

Example, same account. Ada has unsaved code in Two Sum and a submission whose reply was lost.
She signs out everywhere from her phone. Back on the laptop, her next request (asking for a
hint) finds the session ended: the code stays, the banner offers Sign in again. She signs in,
comes back to Two Sum, her code is there, and the page says "Your submission from 21:04
arrived" (one read of its key). Nothing was sent twice; the hint isn't asked again by itself.

Example, another account. Same start, but Bea signs in at the laptop. Two Sum shows Bea's own
code (the starter); no lookup of Ada's key is made as Bea. Ada's code and her pending record stay
in this browser under Ada's account. If Bea signs out and Ada signs in later, Ada's code is
there.

Limits: copies kept under an account that isn't signed in are still in this browser's storage,
readable by anyone with access to this browser's files or developer tools. They aren't
encrypted, and nothing here promises otherwise. They're deleted when that account signs out
here, or with the browser's site data. A deliberate sign-out, or storage the browser cleared,
can't be undone by the app. An account-only page that was open when the session ended can't
keep its form on screen (its data belongs to the account), so its unsaved text is offered back
after signing in as that account.

Tests:
- `frontend/src/test/integration/sessionLapse.test.tsx` (4): the same account back, with a
  failed sign-in first; another account; another tab signing in; storage that can't keep copies.
- `frontend/e2e/session-lapse.spec.ts` (2, real API: the session revoked by sign out
  everywhere): the same account back with its code and no repeated hint; another account sees
  its own code, the earlier account's stays locked and returns after it signs in again.
- Negative controls: 4, each caught (no sign-in link; no cross-tab check; a lapse that forgets
  pending actions; the lapsed account's draft scope outliving the next sign-in).

## Limits

- Updates sent without a key (an older page), or retried after their receipt expired (7 days),
  still read a lost-then-retried save as a conflict. Nothing is lost; the learner chooses.
- Other revision-checked writes (story restore, role targets) don't keep receipts yet.
- Waits come from the server. A proxy that rate-limits without `Retry-After` gives no countdown,
  only the message.
- The judge's full queue gives a wait only when something finished in the last 5 minutes (below);
  otherwise, and for an unavailable or unconfigured judge, there's no countdown, only Check
  availability or a deliberate retry.
- Submissions, hints, reviews and new stories keep their key across a reload (above). The other
  keyed actions still keep it in the page's memory: a lost answer followed by a reload starts a
  new key, and may be done twice. History shows both.
- The browser record needs local storage. When this browser refuses it (some private modes), the
  key lives in the page only, as before.
- The server keeps the evidence as long as the record exists. If what a key made was deleted
  (account or guest clean-up), the check says "no record", which is then all anyone can know.
- On SQLite (local development), two copies of the same AI request at the same instant can both
  reach the provider. The database keeps one answer and one charge, and both get it. PostgreSQL's
  per-account turn prevents the second call. SQLite can't tell the lookup that a request is still
  running either: there it says "no record" until the answer is saved.
- The provider is called at most once per press on PostgreSQL, not exactly once per key: a crash
  between its answer and the save means the next press calls it again (charged once here, billed
  by the provider each time).
- The interview flows (start, message, finish) take the same per-account turn, and also hold
  their transaction across a bounded provider call. Their keys are checked as described above.
  Their crash windows behave the same way.
