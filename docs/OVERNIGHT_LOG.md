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
| B4 | Concurrent submissions and stale feedback | done, see checkpoint | this change |
| B5 | Diagnostics and bounded performance | next | |

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
