# Overnight queue: checkpoints

A recoverable record of the Volume 4 / overnight queue, updated after each task. It states what
was done, on which commit, what was checked and what is left. Morning handoff at the end.

## Execution limits (stated up front)

- One cloud session (Claude Code on the web) on branch `claude/gallant-galileo-hapob6`. It runs
  only while a turn is in progress; there is no background service, and nothing here is
  "monitored overnight" unless a scheduling tool confirms a check-in, which this log will name.
- Commits are pushed to that branch (session policy). No PR, merge, deploy, production
  configuration, secrets change or paid provider call.
- The local container can run the backend suites (SQLite and a local PostgreSQL), the frontend
  suites and Playwright e2e. It can be restarted between turns, which kills background runs;
  a check is reported only when its output was read.
- CI conclusions are read with the GitHub tools for the exact commit; pending is reported as
  pending.
- Independent evaluation: the sealed set (`backend/evals/sealed/`) was written by a separate
  session and has not been opened by this one. It is graded once, for the frozen candidate
  (task 7). Everything else is development or exposed data.

## Queue and status

| # | Task (overnight plan; Volume 4 brief) | Status | Commit(s) |
|---|---|---|---|
| 1 | Baseline and evaluation protocol (brief 01) | done | `c07d3f8` and earlier; CI #114 success |
| 2 | Dictated answers and paraphrases (brief 02, rubric v3) | done | `e973e50`, `30a6dbd`; CI #115 success on `30a6dbd` |
| 3 | Unsupported keyword credit (brief 03, rubric v4) | done | `2e70d0b`, `8db564c`; CI #116 on `8db564c`: success, 7 of 7 jobs |
| 4 | Bounded contradiction handling (brief 04, rubric v5) | done | `cf028d9`, `e69ee77` |
| 5 | Provider failure boundary | done | `d211eba` |
| 6 | Session isolation regressions | done, see checkpoint | this change |
| 7 | Final verification and handoff | after the bonus queue (one final verification) | |
| B1 | Accessible answer and feedback flow | done | `fe39f2f` |
| B2 | Safe rendering of learner and provider text | done | `1ca34a4` |
| B3 | Backend ownership and account isolation | already satisfied; tests added | `1e077c5` |
| B4 | Concurrent submissions and stale feedback | done | `2d1a0e3` |
| B5 | Diagnostics and bounded performance | done, see checkpoint | this change |

## Checkpoint: task 4, contradictions (rubric v5)

- Rule, policy and limits: docs/AI_EVALUATION.md, "Results: rubric v5"; code
  `backend/app/careers/contradictions.py`; protocol v2 note in docs/EVAL_PROTOCOL.md.
- New development set `career_contradiction_pairs.json` (56 minimal pairs, tuning-session
  written, so optimistic) and gate `career.contradiction_controls`.
- Measured, v4 → v5, development data: pairs 0/16 → 13/16 reported (13/13 right), families
  0/9 → 3/9 (3/3 right), collateral 0/51 and 0/10; across 783 answer-like texts 2 points
  removed (both retracted examples), 0 gained.
- Open: 9 contradictions that need word meaning; 6 where the point is still credited by other
  words (`evals/regression.json`).
- Local checks run before the commit: ruff, ruff format, mypy; `tests/test_careers.py`,
  `test_evals.py`, `test_eval_protocol.py`, `test_eval_harness.py` (one test, which loads the
  rubric at `git:HEAD`, can only pass once the change is committed; it passed on `cf028d9`).
- Full SQLite suite started on `cf028d9`: 2004 passed, 386 skipped (PostgreSQL-only and sandbox
  tests), exit 0. Files were edited while it ran, so this is indicative; the final commit gets
  its own full runs (task 7).

## Checkpoint: task 5, provider failure boundary

- Audit: timeouts, lost connections, 429, 5xx, 529, refusals, cut-off and invalid replies, missing
  fields and invalid values already fell back (30 of 30); interview scores are bounded 1–4.
- Fixed: no overall time limit (SDK retries, about 3 minutes worst case) → at most 3 requests,
  25 s each, 45 s in all, retried only when a retry can help; 429 falls back at once. Retries
  were invisible to `--max-calls` → every request counts. Line references outside the learner's
  code are dropped. Failure reasons are logged as safe codes under `attrs` (the JSON formatter
  dropped other extra fields).
- Checks: 33 of 33 fault scenarios fall back; tests with a simulated clock and a fake client
  (`tests/test_ai_coach.py`, request-boundary section); a log test checks no learner text or key
  reaches a log record. Prompt version `coach-2026-11-04` recorded (request settings only).
- Not shown: anything about Claude's coaching quality (no live call was made).

## Checkpoint: task 6, session isolation (frontend)

- Inspected first: the session-generation fix (`20bd00f`) already covered a failed logout plus a
  stale 401, and one account's 401 never being retried as the next account's
  (`session.test.tsx`).
- Demonstrated gaps (tests fail on the previous code): only `me` queries were cleared on
  sign-in/sign-out, so one account's past answers to a question were shown to the next account
  while its own loaded; and a successful late response for the first account was delivered and
  cached after the second signed in.
- Fixed: the API client sets aside a successful response sent with an earlier session's token;
  sign-in and sign-out cancel and remove every cached query.
- Already satisfied, now tested: a query still retrying when the learner signs out sends nothing
  more.
- Checks: `npm run lint`, `npm run typecheck`, `npm test` (54 files, 553 tests) passed. E2E runs
  with the final verification.

## Checkpoint: bonus 1, accessible answer and feedback flow

- Inspected: label, description and error linking, `aria-invalid`, Enter in the answer box,
  draft kept on errors, busy button staying focusable, live regions while typing. All held.
- Demonstrated gap (test failed first): after a successful send, the emptied box disabled the
  focused button and focus fell to the page; the feedback's `role="status"` arrived with its
  content, which screen readers often don't announce. Fixed by moving focus to the feedback
  heading (or the reflection step, then the feedback).
- Tests: keyboard submit and focus, dictated line breaks don't submit, a failed send keeps text
  and focus, reflection-first focus; an axe scan of the page with feedback (runs with e2e).
- Not checked: no screen reader is available here; behaviour was checked through roles, focus
  and the accessibility tree, not by listening.

## Checkpoint: bonus 2, safe rendering

- Traced: learner answers, evidence quotes, coach feedback and hints, notes Markdown, problem
  Markdown, error messages, and every `href` built from data. No raw-HTML API anywhere.
- Already satisfied (tests added): markup in feedback, quotes and a hint renders as text and runs
  nothing; notes Markdown (existing test) drops HTML, images and `javascript:` links.
- Demonstrated gap (test failed first): a `javascript:` meeting link from the API became a live
  link (React 18 doesn't block it). Fixed: links from data follow the server's http(s) rule at
  render time (kit, application posting, scenario and lesson references); back links built from
  navigation state stay inside the app.
- Checks: lint, typecheck, `npm test` 55 files / 573 tests. Unverified surfaces listed in
  docs/SECURITY.md.

## Checkpoint: bonus 3, backend ownership

- Inspected the id-addressed endpoints for answers, interviews, coaching history and shares, and
  the existing per-feature privacy tests (answer review, interviews, rounds, submissions,
  scenarios, drills, shares).
- No gap found. New tests (`backend/tests/test_ownership.py`, 5) pin what wasn't covered: a
  question's answers listed only for their author (401 signed out); a `user_id` in the body is
  ignored; another account can't remove a flag or share an answer by id; every action on a
  question interview (read, answer, follow-up, skip, abandon, finish, review, comparison, retry)
  is a 404 for another account and leaves it unchanged; an AI history item is a 404 for another
  account. No refusal contains the owner's answer text. Story links were already checked
  (`check_story_owner`).

## Checkpoint: bonus 4, concurrent submissions and stale feedback

- Semantics (now written down in `QuestionPage.tsx`): the page that sent an answer owns its
  feedback. Moving to another question starts it afresh; an answer still on its way is saved and
  listed under its own question and in History, but its feedback isn't shown elsewhere. Leaving
  doesn't stop the server grading it.
- Demonstrated gap (tests failed first): the question route reused one page instance across
  questions, so question A's feedback (shown, or arriving late) appeared on question B. Fixed by
  giving each question its own page instance (keyed by track and id).
- Already satisfied, now tested: a second press while sending is ignored (one POST); a failed
  send keeps the text; mutations are never retried automatically, and a 401 resend happens only
  before the server handled the request (no duplicate answer).
- Checks: lint, typecheck, `npm test` 55 files / 576 tests.

## Checkpoint: bonus 5, diagnostics and bounded performance

- Inspected: request and trace ids are random or a validated client id (no learner text);
  span attributes pass an allowlist; the access log never carries share secrets (existing
  test); provider failures were already logged with a reason code (task 5).
- Added through existing instrumentation: the span `coach.provider` with outcome `ok` or
  `fallback_<reason>` and attributes `provider` and `attempt` (allowlisted), so fallbacks are
  counted by reason in `codecoach_span_duration_seconds`; a test checks the span, the metric line
  and that no learner text reaches either.
- Profiled scoring on synthetic answers up to the 6,000-character limit (docs/PERFORMANCE.md):
  6 ms typed, 18 ms dictated at the limit, 128 ms for an adversarial repetition. No defect, so
  no limit changed and no performance check added.

## Second queue: the remaining Volume 4 briefs ("do all the briefs")

Pack 1 bonus briefs B05–B08 and pack 2 prompts P05–P10, paired where they overlap, in this order.
The Long Overnight Upgrade Playbook (received truncated after its brief 05) maps onto it: its
01–03 and 05 were already satisfied, and its 04 (Unicode spans and offsets) is part of P06.

| # | Brief | Status | Commit(s) |
|---|---|---|---|
| 1 | B05 + P07: grader instructions beyond exact phrases (rubric v6, protocol v3) | done, see checkpoint | `56039e0`, `63f8b6e`, this change |
| 2 | P05: more ways to describe a real action | next | |
| 3 | P06: every feedback quote earns its place (with playbook 04) | queued | |
| 4 | B06 + P08: provider faults and a budgeted live evaluation, prepared, no calls | queued | |
| 5 | B07: the remaining session-isolation cases (done before P05's measurement, while its set was being written) | done, see checkpoint | this change |
| 6 | P10: one more career, with a sealed set written by a separate session | queued | |
| 7 | B08 + P09: freeze, grade the sealed set once, final suites, CI on the exact commit | queued | |

## Checkpoint: B05 + P07, the grader-instruction boundary (rubric v6)

- What changed, how and the limits: docs/AI_EVALUATION.md, "Results: rubric v6"; protocol v3 in
  docs/EVAL_PROTOCOL.md; threat model and residual risks in docs/SECURITY.md (section 2).
- New development set `career_injection_challenges.json` (90 minimal pairs written by a separate
  session from the protocol, questions and rubric text; read by this session while tuning, so
  its numbers are development figures). New gate `career.grader_boundary`; a deliberately
  literal boundary fails it (`tests/test_eval_harness.py`).
- First measurement (v5) → after tuning (v6), challenge set: attacks credited 4/45 → 0/45 (4
  kinds had one success each), quotes or points differing from the base 11/45 → 2/45 (quote
  window only), benign controls cut 0/27 → 0/27; families set attacks 1/9 → 0/9. Benign corpus
  506,971 sentences, 0 cut. Defect register: `unpunctuated-attack-drops-answer` fixed, and the
  rephrased or disguised attacks v5 credited recorded as fixed (5 cases, shown under v5, not v6).
- Found while writing the tests and fixed before the commit: an unclosed `<!--` emptied the
  answer; an attack without its full stop took the learner's first sentence; a "so this was…"
  after an attack was cut as its reason.
- Comparison `rubric-v5-vs-v6.md`: 9 case checks fixed, 2 regressions, both development cases now
  graded exactly like their base (explained in AI_EVALUATION; labels not edited).
- Scoring cost (docs/PERFORMANCE.md): the first draft was about 4 times slower than v5 on long
  typed answers; the fold is now skipped for ASCII text and the attack search runs once per
  sentence (`f835c25`, same results): 12 ms against v5's 7 ms at the limit, all cases under 50 ms.
- Checks: ruff, ruff format, mypy (`app`, as CI runs it); career, eval-harness, evals and protocol
  tests, 265 passed on the speedup; full SQLite suite on `56039e0`: 2056 passed, 386 skipped
  (sandbox and PostgreSQL-only), exit 0.

## Checkpoint: B07, the rest of the session boundary (frontend)

- Mechanism inspected: the API client's session generation (401s, set-aside responses), the
  provider's epoch (late refreshes), and sign-in/out clearing the query cache.
- Two gaps found, each reproduced by a test that failed before the fix:
  - optimistic rollbacks (a bookmark; a card move on the applications board) that fail after the
    account changes wrote the first account's snapshot into the next account's cache (4 tests:
    both changes, failing and set-aside success). Fix: `sessionMark()` / `isSameSession()` in
    `api/client.ts`; both rollbacks write back only in the session they started in;
  - a sign-out the server never heard left the refresh cookie valid, and a reload signed the
    learner back in. Fix: a pending-sign-out flag (`auth/pendingSignOut.ts`): no refresh while
    set, and each load finishes the sign-out first (2 tests: late refresh plus reload; offline
    reload, a 401 meanwhile, a new sign-in).
- Already held, now tested: a refresh for one account that answers after the next account signs
  in changes nothing, and every later request carries the new account's token.
- Not added: multi-tab session sharing (the app has none beyond the refresh lock, already
  tested); a test of every cache write (each was read; all but the two store the server's answer).
- Checks: frontend lint and typecheck clean; `vitest run`: 55 files, 583 tests passed.

