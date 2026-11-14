# Interview continuity across tabs and devices (Volume 7, prompt 3)

A learner can return to the right interview from any tab or device. They never get a duplicate
start, a lost answer, a reset clock or an unexplained 409. This extends the existing interview
engine (`app/services/interviews.py`, `question_rounds.py`) and the shared start-page hook
(`useActiveInterview`). There's no second engine, no lock service and no realtime channel.

## The policy

- **One interview in progress per account**, coding or question round. The database enforces
  it, so it holds however the requests are timed.
- **Any signed-in tab or device can continue it.** Nothing marks one device as the active one.
  The server's state is the only source of truth, and every write is checked against it:
  - **Start.** One wins. Every other Start gets a 409 with a Resume card naming the live
    interview: what it is, how far along, the time left, and the last activity. The losing request
    never reaches the AI, so the budget is spent once.
  - **A coding message** carries the transcript length it was written against (`after_seq`).
    - If the interview has moved on since (another tab or device), it is refused with 409
      `interview_advanced`. Nothing is appended and the AI isn't asked. The page loads the latest
      and keeps the text in the box.
    - Resending the same message (same `client_request_id`, after a lost response) returns the
      current state, not a second reply.
  - **A round answer.** The first answer the server gets for a question is the one kept.
    - The same text again is a retry: 200.
    - A different text is refused with 409 `question_answered_elsewhere`. That tab moves to the
      next question, and its unsent text stays on screen (and in that browser) until the learner
      copies it or dismisses it.
  - **Finish, end early, expiry** are one compare-and-set. If two happen at once, one evaluation
    runs, and both get its result.
- **Switching devices is deliberate but needs no ceremony.** Continuing on the device you're on
  is the takeover. The other tab learns of it on its next action, or when it gets focus again (a
  live interview is re-read on focus). It is told in words, and its unsent text is never
  discarded. Simultaneous typing isn't merged: each tab keeps its own text, and the server takes
  the first send per question or turn.
- **Time is the server's.** The deadline is stored when the interview starts. Resuming never
  resets it; every device counts down from the same deadline. An expired interview shows its
  results. Its Resume card disappears, and a new one can start.
- **Leaving is not ending.**
  - "Leave for now" keeps the interview in progress, and the page says the timer keeps running.
  - "End early" ends the assessed interview, after a confirmation that says so and points to
    "Leave for now".
- **Voice.** The microphone starts only on a click, never on resume.
  - A new question, whether answered here or in another tab, remounts the answer box, which stops
    the microphone.
  - Leaving the page stops it too.
  - Typing always works.
- **When something is unavailable:**
  - question rounds make no AI calls;
  - a coding interview falls back to the offline interviewer when the provider fails;
  - a spent AI budget is shown inline (429), and the interview and its saved turns stay valid;
  - finishing always produces feedback (offline if need be);
  - none of these makes Resume lead to a dead end.
- **Only the owner** can read, resume, answer or end an interview. Everyone else gets 404, and
  another account's Start is neither blocked by it nor told about it.

## How the server enforces it

| Guarantee | Mechanism | Tests (`backend/tests/test_interview_continuity.py`) |
|---|---|---|
| One live interview per account | partial unique index `uq_one_live_interview` on `practice_sessions(user_id)` for `status = 'in_progress'` and the interview modes. A Start's insert is flushed before the AI is asked anything and before the per-user AI lock, so the loser gets the useful 409, not "request in progress" | two round Starts at once: one 201 and one 409, with the Resume card. Two coding Starts at once: one interview, **one AI call** |
| One turn per position | unique `(session_id, seq)` on `interview_turns` | two answers to one question at once: stored once. A different answer racing the first: 409, not stored |
| No message out of context | `after_seq` on `POST /messages`. Without it (an older client), a message is taken as before | a stale tab's message: 409 `interview_advanced`, nothing appended, no AI call |
| A lost response doesn't double | `client_request_id` on `POST /messages`, kept in the turn's meta | the same message twice: one reply, no second AI call |
| One evaluation per interview | `_claim_close`: `UPDATE … WHERE status = 'in_progress'`. The loser refreshes and returns the winner's result | two Finishes at once: both 200, the same evaluation, **one AI call**, one completion event |
| Resume context | `InterviewSummary` gains `progress_done`, `progress_total`, `seconds_remaining`, `last_activity_at` (in progress only), also carried in the Start 409's `details.interview` | the list and the 409 carry them |
| Expiry | applied lazily on the next read or write (as before), now through the same compare-and-set | an expired round: 409 `interview_closed` on answer, results on read, no Resume card, a new Start works |
| Ownership | `_load` by owner (as before) | another account: 404 on read, answer and abandon; its own Start is unaffected |

Negative controls were run locally:
- With the two constraints removed from the schema, the five race tests fail: two interviews, or
  two stored answers.
- With the compare-and-set removed, two Finishes make two AI calls.

## Data repair (migration `8d9e0f1a2b3c`)

Before the constraints exist, the migration makes existing data consistent. It deletes nothing:
- Turns that share a position in one interview are renumbered in their stored order.
- Where a user has more than one interview in progress, the most recently started stays in
  progress. The others are closed as abandoned, with no evaluation (the review page already
  handles a missing evaluation). Completed, expired and abandoned interviews are untouched.
- Downgrade drops the constraints and reopens nothing.

`test_the_migration_repairs_duplicates_from_before_and_deletes_nothing` runs on PostgreSQL. It
upgrades a database holding a raced pair of interviews and a raced pair of turns, checks the
repair, and downgrades.

## In the browser

- `ResumeCard`, on both start pages, keeps the existing wording ("Resume it, or end it there to
  start another") and adds the context. On a refused Start, it uses the 409's own summary, so
  it names the interview the other device started.
- The coding page:
  - sends `after_seq` and `client_request_id` with each message;
  - on `interview_advanced`, loads the latest and gives the text back;
  - on a network error, re-reads the interview before deciding: if the message is there, it was
    sent, and the box clears;
  - a turn sent from another tab shows "Updated from another tab or device".
- The round page keeps a refused answer's text in a region named "Your unsent answer to question
  N", with Copy text and Dismiss. The draft stays in this browser's storage until it's dismissed.
- Tests:
  - `frontend/src/test/integration/interviewContinuity.test.tsx` covers each of these, and
    `interview.test.tsx` keeps the earlier Resume tests;
  - `frontend/e2e/interview-continuity.spec.ts` uses two browser contexts for one synthetic
    account, plus a stranger: resume with context, the same question and clock, a stale answer
    kept and dismissed, a reload, end early, the other device finding results, and the
    stranger's 404.

## Verified (locally, on the commits that add this)

- Backend, SQLite and PostgreSQL (as a role without RLS bypass):
  - `test_interview_continuity.py`: 11 on SQLite; 12 on PostgreSQL, with the migration test;
  - `test_question_rounds.py`: 14;
  - the earlier interview-related selection: 173 passed.
- Migration on PostgreSQL: upgrade, `alembic check` ("No new upgrade operations detected"),
  downgrade, upgrade.
- Frontend unit and integration: 754/754, with `interviewContinuity.test.tsx` (7) and the
  earlier `interview.test.tsx` Resume tests unchanged.
- Browser (Chromium, desktop project, real API and judge):
  - `interview-continuity.spec.ts` passed (two contexts and a stranger);
  - `interview.spec.ts`, `formats.spec.ts` and `display.spec.ts` (keyboard round with focus
    mode and End early) passed;
  - the controls audit's self-tests passed.

## Limits

- **No push between tabs.** A tab learns about another device's progress when it acts, or when
  it regains focus. Two tabs left open side by side don't update each other live.
- **Drafts are per device** (this browser's storage). A draft typed on one device isn't on another.
- **Nothing says which device is active.** The server doesn't track devices, so there's no "open
  on your laptop" message. Every device is told only when its own action meets newer state.
- **On PostgreSQL, one AI request per account at a time.** A coding message sent while another of
  the same account's AI requests is running gets 429 `ai_request_in_progress` (an existing lock).
  A retry after it finishes then meets `after_seq`.
- **Old clients.** A client that doesn't send `after_seq` gets the old behaviour for coding
  messages: they are appended. The turn-position constraint still stops two being stored in one
  place.
