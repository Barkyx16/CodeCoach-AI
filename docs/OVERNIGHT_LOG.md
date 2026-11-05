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
| 2 | P05: more ways to describe a real action (rubric v7, protocol v4) | done, see checkpoint | `8e492d3`, this change |
| 3 | P06: every feedback quote earns its place (with playbook 04) | done, see checkpoint | this change |
| 4 | B06 + P08: provider faults and a budgeted live evaluation, prepared, no calls | done, see checkpoint (live run not done: not authorized) | this change |
| 5 | B07: the remaining session-isolation cases (done before P05's measurement, while its set was being written) | done, see checkpoint | this change |
| 6 | P10: one more career, with a sealed set written by a separate session | done, see checkpoint | this change |
| 7 | B08 + P09: freeze, grade the sealed set once, final suites, CI on the exact commit | done, see checkpoint and final handoff | `84dc1ee`, `0b78ebb`, `51c040f`, `a1ec679`, this change |

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

## Checkpoint: P05, the action criterion (rubric v7)

- Criterion written first (protocol v4, `labeling.action_criterion`), then a development set
  written against it by a separate session (`career_action_wording.json`, 126 minimal pairs),
  graded once under rubric v6 as the baseline before any change.
- Baseline → v7: reworded actions credited 34/72 → 64/72; controls wrongly credited 6/36 → 4/36
  (all four irrelevant actions, open); paraphrases graded like their base 42/72 → 64/72. Other
  sets: one changed decision in the old development set (`rn-dev-08`, a team answer whose label
  predates the criterion; label not edited), two contradicted points no longer credited.
- A first draft brought back the fixed defect `contradicting-statements-credited`; the defect
  register's gate caught it, and a contradiction's scope now includes the statement that follows
  in support of it.
- By design not read as done: a story in the present (7 cases, open in the register, with the
  reason). The action advice no longer asks for "I did …" sentences only.
- New gate `career.action_controls` (and a weakened grader that fails it on all 32 gated
  controls); register entries for the two fixed and three open defects.
- Checks: ruff, ruff format, mypy (`app`); career, harness, evals and protocol tests, 288 passed
  on `8e492d3`.

## Checkpoint: P06, the evidence contract (with playbook 04, Unicode offsets)

- Contract and validator: `app/careers/evidence.py`, applied wherever stored feedback is sent
  (answers and re-evaluations). Spans stored in code points, sent as UTF-16 offsets; legacy rows
  labelled, never given positions or regraded; failing quotes omitted, not replaced.
- Measured on rubric v7: 1,536 of 1,536 quotes valid and relevant on all six career sets (16
  widened to their sentence start, no negation restored). New check `evidence_contract`, gate
  `career.evidence_contract`, metrics `quote_validity` / `quote_relevance` (protocol v5).
- Page: "Show it in your answer" (marks the quote in the reviewed answer, moves focus), legacy and
  omitted labels, one line saying what each kind of feedback is (five surfaces), and a notice when
  the draft no longer matches the reviewed version.
- Provider path: evidence quoting text the request didn't contain is dropped (coach prompt
  `coach-2026-11-04b`, reply handling only).
- Checks: ruff, ruff format, mypy (`app`); backend career, harness, evals, protocol, AI coach,
  evidence, OpenAPI snapshot and answer-review tests, 341 passed; full SQLite suite on
  `8e492d3` (before this change): 2079 passed, 386 skipped, exit 0; frontend lint, typecheck,
  `api:check`, `vitest run` (56 files, 587 tests), build and bundle budgets passed.

## Checkpoint: B06 + P08, provider faults and a budgeted live evaluation (prepared, not run)

- Provider boundary: a reply valid against its schema but unusable (empty required text, a
  complexity with no Big-O notation, a failure explanation with no evidence or with evidence it
  wasn't given) now falls back like other failures, without a retry. Fault scenarios 33 → 38, all
  fall back. Coach prompt `coach-2026-11-04c` (reply handling only).
- The learner sees a plain status line when the built-in coach answered instead of Claude
  (hints, reviews, failure explanations).
- Live evaluation, ready but **not run** (no authorization or key): `--check-provider` (presence
  only), `--plan` (dry run with the worst case and where the budgets stop it), `--max-calls` and
  `--max-output-tokens` reserved before each request, `--concurrency` 1–4, outcomes by reason,
  retries, models seen, cost only from given prices with an upper bound, `live.status` in every
  report. Tested with fake clients only (`tests/test_live_eval.py`, 16 tests); no live call made.

## Checkpoint: P10, customer service representative (rubric v8, protocol v6)

- `app/careers/support.py`: per-career evaluation status, owner, source, review status, version,
  formats and sets. The catalog and every answer say whether the career's feedback is measured;
  unmeasured careers get a plain note (never a refusal); "Explains … correctly" points say they
  check discussion, not correctness.
- Sets: `career-csr-families-dev` (separate session) and `career-csr-sealed` (another separate
  session; not opened; graded with the frozen candidate). One development keyword list rewritten
  by its author after the cross-split duplicate check (only ids shared).
- The first measurement (v7) found an attack credited; fixed in rubric v8 (two general patterns,
  no other decision changed anywhere, corpus clean). Open: advice paraphrased back is credited
  (the rewritten keyword list); a contradiction withholds one more point than the labels expect
  (by design, left). The CSR self-correction, benign and attack families are gated; keyword lists
  not yet.
- Boundaries tested (`tests/test_career_scope.py`): nursing, customer service, coding and an
  unmeasured career; another career's question graded by its own rubric; a career change keeps
  earlier answers and progress apart.
- Also prepared for the final step: `python -m evals.run --sealed` and `python -m evals.release`
  (aggregates only).

## Checkpoint: B08 + P09, freeze and the sealed measurement

- Frozen: candidate `ffb116b` (recorded at `84dc1ee`): rubric v8, coach prompt
  `coach-2026-11-04c`, protocol v6, every dataset hash, dependency files
  (`backend/evals/results/freeze-2026-11-04.json`).
- Graded once: both sealed sets with the candidate and with the rubric v2 baseline (`20bd00f`, in a
  worktree with the frozen harness and datasets). Release rule on `career-rn-sealed`: passes every
  item. Not better, and reported as such: contradiction detection 0/9 on the nursing sealed set,
  contradicted points still credited 7/11 → 9/11, meaning-changed points still credited 7/12 → 8/12
  (customer service 14/25 → 16/25). Results: docs/AI_EVALUATION.md, "The sealed measurement".
- A scripting mistake graded the sealed sets a second time with the candidate (identical,
  deterministic); its files were deleted unopened and `evals/sealed/ACCESS.md` says so. Case-level
  results were not opened and are kept out of the repository.
- Since the freeze, the code changed only in the learner-facing note for the two measured careers
  (`app/careers/support.py`), the release tool's reading of aggregate-only reports,
  `.gitignore` and two end-to-end tests; scoring, rubric, prompts and datasets are as frozen.

## Final handoff (second queue)

**Branch** `claude/gallant-galileo-hapob6`. Not merged, not deployed, no PR.

### Done

| Brief | Outcome | Commits |
|---|---|---|
| B05 + P07 grader instructions | rubric v6: attacks found however written (folded text, markup, delimiters, paraphrases); only the attack cut from a run-on; 90-case challenge set by a separate session; gate `career.grader_boundary` | `56039e0`, `63f8b6e`, `f835c25`, `d43add8` |
| B07 session boundary | stale rollbacks can't write one account's data into the next one's cache; a sign-out the server never heard is finished on the next load | `9b96189` |
| P05 action criterion | rubric v7: written criterion; team actions, past perfect, asides, passives by the learner, irregular verbs; 126-case set by a separate session; gate `career.action_controls` | `8e492d3`, `1df64ea` |
| P06 evidence contract | every quote checked against the answer before display, UTF-16 offsets, legacy labelled, "Show it in your answer", feedback kinds, changed-draft notice | `9418469`, `65c5d9b` |
| B06 + P08 provider and live evaluation | unusable replies fall back; fault scenarios 38/38; visible fallback status; live evaluation ready (plan, credential check, budgets reserved before each request, concurrency 1–4), **not run** | `de718be` |
| P10 second career | customer service representative: development and sealed sets by separate sessions, per-career measurement status, honest notes for the other 108 careers, boundary tests; rubric v8 | `ffb116b` |
| B08 + P09 freeze and final measurement | freeze record, sealed sets graded once, release rule passes, results with what didn't improve | `84dc1ee`, `0b78ebb`, `51c040f`, `a1ec679`, this commit |

### Checks on the final code

- Backend SQLite: 2120 passed, 386 skipped (sandbox, PostgreSQL-only and other environment-bound
  tests), exit 0, on `51c040f` (later commits change docs and two end-to-end tests only)
- Backend PostgreSQL: 2122 passed, 384 skipped, exit 0, on `a1ec679`
- Frontend (app code unchanged since `ffb116b`; only two end-to-end tests changed since): `api:check`
  and `vitest run` 58 files / 591 tests passed on `ffb116b`; lint and typecheck clean after the test
  change; build passed; size check: shell 283.6 KB gzip (budget 300 KB), largest lazy chunk 674.5 KB
  gzip (budget 700 KB)
- E2E (Playwright, real backend, Chromium desktop and mobile, PWA), on `a1ec679`: 82 passed,
  3 skipped, 1 failed. The failure was in the test: answer review read the whole evidence block,
  which since P06 also holds the "Show it in your answer" button. Fixed in this commit (it reads the
  quote's paragraph, and now also checks by keyboard that the button puts focus on the quote); that
  spec then passed 2 of 2. On CI (run 136, `21b87dc`) it passed, and onboarding failed instead: the
  tour's Finish closes the panel at once and saves in the background, and the test's full page load
  straight after cancelled that save (the log's diagnostics list it as never answered), so the
  dashboard offered to resume the tour. Reproduced locally by slowing that one request; the test now
  waits for the save before leaving, as a person would (onboarding and answer review then passed
  10 of 10, each run twice).
- Not run here: the sandbox job (Docker and gVisor), Docker image builds, the dependency audit, a
  real phone, real speech recognition, a screen reader, and any live Claude call.

### CI

Reported with the handoff message, job by job, as read from GitHub for the final SHA; nothing
here claims it. Intermediate pushes' runs were cancelled by the next push. Run 135 (`a1ec679`) and
run 136 (`21b87dc`) each passed every job but end-to-end, which failed on one test each (above).

### Known issue found in the final checks

- Finishing the tour and reloading the page in the same instant can lose the "finished" mark (the
  save is cancelled with the page); the dashboard then offers to resume or dismiss the tour. In-app
  navigation doesn't cancel it. Not changed now: sending it with `keepalive` would need a CORS
  preflight, which browsers don't all allow for keepalive requests, and that wasn't tested here.

### Not done, and why

- **No live Claude evaluation**: no paid calls are authorized and there is no key here. Everything
  for it is ready and tested with fake clients (docs/AI_EVALUATION.md, "Measuring Claude").
- **No human label review**: every label, sealed ones included, is model-written.
- **The playbook's briefs 06–28** arrived truncated after brief 05; nothing was done for them.

### Open defects (`backend/evals/regression.json`)

Contradictions that need word meaning (and the sealed result: 0/9 on nursing answers);
contradicted points credited by other words; vague and generic claims credited; scene and
preparation cues missed; result credited by any number; a story told in the present not read as
done; irrelevant actions credited; "felt" as an examination missed; advice paraphrased back
credited.

### Next recommended actions

1. Have a person review a sample of the development and sealed labels; until then every number
   rests on an AI's labels.
2. Contradiction handling is the weakest measured area (0/9 on unseen nursing answers): any fix
   needs new sealed sets to measure it, because the current ones are used.
3. With authorization and a budget, run `python -m evals.run --plan …` and then the live
   evaluation (docs/AI_EVALUATION.md, "Measuring Claude").

### Review description (for a PR, if one is opened)

Volume 4, second queue: the written-answer coach's grader-instruction boundary (v6), action
criterion (v7) and two more attack forms (v8); an evidence contract for every quote shown; the
provider boundary for unusable replies and a prepared, budgeted live evaluation; session-boundary
fixes; a second measured career. Measured on development sets written by separate sessions, then
once on sealed sets against the rubric v2 baseline: the protocol's release rule passes (precision
87% → 91%, recall 79% → 84%, unsupported credit 57% → 37% on the nursing sealed set, small samples,
model-written labels), and contradiction handling did not generalise (0/9). Risks: labels unreviewed;
no live Claude data; heuristics in `app/careers/grading.py` and `questions.py` are tuned on
development data. Checks: as above.

## Third queue: Learner Experience Upgrade Pack (14 briefs)

Started from `2e88dc5` (all seven CI jobs green, run 137) on `claude/gallant-galileo-hapob6`, with
PR [#10](https://github.com/Barkyx16/CodeCoach-AI/pull/10) open into `feature/premium-frontend` at
the learner's request (the pack itself says not to open one; the learner's instruction wins).
Same rules as before: no new service, dependency, migration, paid call or persistent draft
storage; synthetic data only; structural coaching, never clinical correctness.

## Checkpoint: LX01, the learner journey as it is

The journey traced (career questions; coding shares the dashboard and History):

| Step | Screen / route | Data it uses |
|---|---|---|
| Choose | `/dashboard` (CareerDashboard: Continue, Up next, stats), `/problems?view=questions` (library: level tabs, search, format, skill, status, sort in the URL) | `GET /me/resume`, `GET /careers/{t}/progress`, `GET /careers/{t}/questions`, `GET /explore/…` |
| Answer | `/careers/{t}/questions/{id}` | draft in this browser (existing per-account key); `POST …/answers` |
| Feedback | FeedbackCard on the same page (score or "not enough to score", points with checked quotes, rubric and question version) | the answer record: `score`, `evidence_level`, `rubric_version`, `content_version`, `coach`, `points` |
| What next | nothing on the page after feedback; the box is emptied; "Your past answers" in the sidebar | `GET …/answers` (this account's answers to this question) |

Obstacles found by reading the code; each is confirmed by a failing-first test in the brief that
fixes it (or marked otherwise):

1. **Dead end after feedback (06, 07).** No next action follows the feedback: no retry aimed at a
   missing point, no next question; the answer box is emptied, so a revision starts from nothing.
2. **Past answers lose their identity (05, 08, 09).** Choosing one in "Your past answers" reuses
   the just-sent slot, so an old answer is titled "Feedback" as if it were new; the list doesn't
   say which was the first try; the choice isn't in the URL (a reload drops it); scores from
   different rubric versions sit side by side; an answer too short to score shows its capped
   number (e.g. 35/100) beside a card that says "Not enough to score".
3. **"Up next" overclaims (04).** It looks at the first 60 questions of one level and, when none
   of those is unanswered, says "You've answered every {level} question" without checking the
   level's real total; it never says why these questions were picked.
4. **Progress numbers don't name their unit (03).** "Answered N of 300" counts distinct questions
   (retries don't add, an answer too short to score does); "Strong answers" counts questions whose
   best score is 85+; neither says so.
5. **No route to the weakest answers (05).** The API already sorts answered questions by lowest
   score; nothing links there.
6. **A broken question link offers only "Try again" (02, 13).** A removed or mistyped question id
   shows the generic error and a retry that can't help, with no way back to the questions.
7. **The breadcrumb drops the list's filters (09).** "{Career} questions" goes to the unfiltered
   library even when the learner came from a filtered one.
8. **A lost response can duplicate an answer (10).** Career answers have no idempotency key; after
   a network error the message says "try again", and if the server had saved it, a second copy is
   saved.
9. **"Reset" in the coding workspace doesn't say what it resets (11).** It replaces the code with
   the starter; past submissions are kept, which the confirmation doesn't say.

Not obstacles (already right, left alone): Continue lists only genuinely saved work, labels a
finished question "Review feedback", and never changes saved work; the library keeps its filters
in the URL and BackLink uses browser Back; the feedback card shows its rubric and question
version and marks changed questions; drafts are per account; interviews confirm before ending.

Queue scope: 02–13 as bounded changes to the career question journey and the dashboard on
existing APIs, plus a backend status filter value if 05 needs one (no migration). Not in scope:
a stored link between an answer and the one it revised (needs a column: proposal only), changing
what `best_score` means across the five services that compute it (proposal only).

## Checkpoint: LX02 + LX13, start, continue and unavailable links

- Continue (already right, unchanged): only genuinely saved work, in a fixed priority (interview
  in progress, unsent answer, coding draft, unsolved problem, last answered question, which is
  labelled "Review feedback", not "continue"). A saved draft for a question that's since been
  removed now leads to the state below instead of a dead end.
- Changed: a question link that's mistyped or removed (API 404) says "This question isn't
  available" and links to that career's questions (or the library for an unknown career); no
  "Try again". The same for a coding problem. Server errors still offer a retry. Public content
  only: ownership-sensitive "not found" messages (notes, applications, shares) are unchanged.
- Checks: `learnerJourney.test.tsx` (5, four failed before the change), `workspace.test.tsx`.

## Checkpoint: LX03 + LX04, progress units and a transparent Up next

- Definitions, as computed by `GET /careers/{t}/progress` (unchanged) and now shown:
  "Questions answered" = distinct questions with at least one answer (retries don't add; an
  answer too short to score counts as answered); "Strong answers" = questions whose best score is
  85+; "Skills practised" = skills with at least one answered question (the analytics page's word).
- Up next (`features/dashboard/upNext.ts`, unit-tested): level = the first of easy, medium, hard
  with fewer than 10 answered questions, else hard; within it, in library order, up to 2
  questions whose best score is under 70, then up to 3 unanswered. The card says this, and where
  the learner is ("You're on Easy (1 of 10 answered there…)"). Evidence window: all of the
  learner's own answers on this career; nothing from other accounts; no model.
- Fixed: it read the first 60 questions of a level and could say "You've answered every easy
  question" when the level held more; it now reads the whole level (100, the API's page limit,
  which no level exceeds) and claims "done" only when the listed count equals the level's total.
- Added: "Review your answered questions, lowest score first", the library's existing filter
  and sort (brief 05's entry point).
- Not changed (proposal): `best_score` includes answers too short to score (capped at 35), so a
  question tried only with a few words shows "best score 35". Excluding them is a cross-cutting
  contract change (careers, explore, activity, roadmap); left as is and noted.
- Checks: `upNext.test.ts` (4), `careerDashboard.test.tsx`, `progress`, `plan`; e2e text updated.

## Checkpoint: LX05–LX08, past answers, the recap, targeted retry and comparison

Data contract: `GET /careers/{t}/questions/{id}/answers` (this account's answers, newest first,
at most 20) and each answer's own fields; no API, schema or storage change.

- LX05 Review: the entry point is the dashboard link (LX04) to answered questions, lowest score
  first. On the question page each past answer is "Try N" (1 = first) when the list is complete;
  with 20 listed the first tries may be missing, so they're labelled by date and the list says
  "your 20 most recent". Choosing one puts `?answer=<id>` in the URL (replace, keeping the
  page's navigation state), so a reload or Back keeps it; it's titled "Feedback on try N from …",
  never "Feedback" (which only the answer just sent gets; before, choosing an old answer reused
  the just-sent slot and its title). An answer too short to score is listed as "Too short to
  score", not by its capped number. A changed question keeps its existing note (answered
  version N); a missing answer id keeps its existing warning.
- LX06 Recap ("What next", under the feedback): what this try covered ("covered 2 of 3 points the
  rubric looks for. To add: …", or "too short to score yet (N words)"), the comparison below,
  and one primary action: revise when a point is missing or it was too short, otherwise the next
  unanswered question at this level (library order, after this one, wrapping; "every other …
  question here has an answer" only when the whole level was listed, with a link to the library).
  The way back is the breadcrumb at the top; a second "Back to … questions" in the recap
  duplicated it and the existing "Back to results" (the full e2e run caught it) and was removed.
  Structural wording only; nothing about whether details are right.
- LX07 Targeted retry: "Revise this answer" (or "Add to this answer") fills the box with that try's
  text only if the box is empty (unsent text is never replaced; the note says so), names the
  first missing point and its advice, and asks for only what really happened. "Start from a blank
  box" has an Undo; "Hide this note" only hides the note. Sending saves a new try through the
  same `POST`; earlier tries are never changed. The draft uses the existing per-account,
  per-question draft key; nothing new is stored. Not offered offline or for a retired question.
  How tries stay distinguishable: separate answer ids and times; there is no stored link from a
  revision to the try it revised (proposal: a nullable `revises_answer_id` column, which needs a
  migration, so not done).
- LX08 Comparison rule (`features/careers/tries.ts`, unit-tested): two tries are compared only
  when they have the same question version, rubric version and coach, and both were long enough
  to score; then the points gained and lost are named and the two scores given as numbers (no
  arrow, no percentage, no claim that the learner improved). Otherwise: "Not directly comparable
  with try N: …" with each reason. The past-answers list adds each answer's rubric when they
  differ, and says their scores aren't directly comparable.
- Checks: `tries.test.ts` (6), `learnerJourney.test.tsx` (9 for these briefs; all 9 failed on
  the previous page), History back-navigation test and e2e title updated ("Feedback on try 1").

## Checkpoint: LX09–LX11, list context, unknown saves, reset scope

- LX09: the question page's breadcrumb went to the unfiltered library; it now returns to the list
  the question was opened from (its URL, with level, search and filters), and "Next question"
  carries that list along (`listFrom` in navigation state, accepted only for `/problems` paths).
  BackLink (browser Back) is unchanged. Direct links with no list fall back to the career's
  library. Private answers never go in URLs or state: only ids. Not restored: scroll position
  after the breadcrumb (it's a new navigation; browser Back restores it).
- LX10: career answers have no idempotency key, so a reply lost after the server saved would make
  "try again" save a duplicate. Now, when no reply comes back (network error, status 0), the page
  reloads this account's answers and, if a new one with the same text is there, shows it as saved;
  otherwise it says the outcome is unknown, keeps the text, and asks the learner to look at their
  past answers before resending. Definite refusals (the server answered) keep their error and
  retry. Limit: if the server saves it after that check, a resend can still duplicate it
  (proposal: an idempotency key on this endpoint, as code submissions have; needs a column).
- LX11: the question page had no reset; the new "Start from a blank box" clears only the box (Undo).
  The coding workspace's "Reset" keeps its short visible label (a longer one pushed the toolbar's
  buttons, Save among them, under the editor in a narrower panel; the full e2e run caught it), with
  the accessible name "Reset code", a tooltip, and a confirmation that says the starter code
  replaces the editor's unsent changes and past submissions are kept (it already only reset the
  local draft). Interview "End the interview" already said what it ends. No retention change.
- Checks: `learnerJourney.test.tsx` (5 more; the 3 behaviour tests failed on the previous page).

## Checkpoint: LX12 + LX14, narrow screens and the whole journey

- LX12: inspected at 1440, 375 and 320px (Chromium, emulated viewports): the dashboard (stat
  tiles in two columns, Up next with its rule), the question page's recap and the revision note.
  No sideways scroll; the recap's buttons wrap and stay touch-sized; long "Next question: …"
  titles wrap. No layout fix was needed beyond the new styles. Not checked: a physical phone, an
  on-screen keyboard over the answer box, a screen reader.
- LX14: `e2e/learner-journey.spec.ts` against the real backend: sign-up, Up next's rule, a send
  dropped before it reaches the server (nothing saved, outcome stated as unknown, text kept),
  feedback and the recap, a revision for the missing point, the two tries compared, try 1
  reopened from its URL after a reload, the recap at 320px, the dashboard counting the question
  once. Review of the learner-facing diff: one comparison phrase reworded; the tour's last step
  and Help updated to name What next and numbered tries; no duplicate confirmations added; no
  answer text in URLs or navigation state. The full e2e run found a duplicated back link and a
  label that broke the coding toolbar; both fixed (LX06, LX11).

## Final handoff (third queue: Learner Experience pack)

**Branch** `claude/gallant-galileo-hapob6`, PR #10 into `feature/premium-frontend` (open, not
merged, not deployed). Started at `2e88dc5`.

| Brief | State | Evidence |
|---|---|---|
| 01 Map the journey | done | checkpoint LX01 (nine obstacles, what's already right) |
| 02 Start and continue | done (Continue already right; unavailable links fixed) | `3d3f5ab`; `learnerJourney` "A link to a question that isn't there" |
| 03 Progress denominators | done (labels; definitions unchanged) | `9f84224`; `careerDashboard` test |
| 04 Transparent next practice | done | `9f84224`; `upNext.test.ts` |
| 05 Missed-item review | done | `9f84224` (lowest-score link), `e143483` (numbered tries, URL, titles) |
| 06 Recap with a next action | done | `e143483`; "What next, after feedback" tests |
| 07 Targeted retry | done (no stored link between tries: proposal) | `e143483`; "A revision aimed at one missing point" tests |
| 08 Comparable attempts only | done | `e143483`; `tries.test.ts` |
| 09 Navigation context | done | `e143483`; "The list a question was opened from" tests |
| 10 Honest saving states | done (idempotency key: proposal) | `e143483`; "Sending an answer when no reply comes back" tests, e2e dropped send |
| 11 Restart and reset | done | `e143483` (blank box with Undo; "Reset code" scope) |
| 12 Narrow screens | done (inspection, e2e at 320px) | checkpoint LX12 |
| 13 Empty and unavailable states | done for question/problem links; other states inspected, unchanged | `3d3f5ab` |
| 14 Verify and hand off | done | this section |

**Definitions now shown to learners** (computed as before): questions answered = distinct
questions with at least one answer; strong answers = questions whose best score is 85+; skills
practised = skills with at least one answered question; Up next = the stated fixed rule; tries =
this account's answers to one question in time order (numbered only when all are listed);
comparable = same question version, rubric version and coach, both scoreable.

**Decisions still needed (proposals, not done):**
1. `best_score` counts answers too short to score (capped at 35). Excluding them changes five
   services' numbers; needs a product decision.
2. A stored link from a revision to the try it revised (`revises_answer_id`, a migration).
3. An idempotency key for `POST …/answers` (as code submissions have), so a resend after a lost
   reply can never duplicate; the page's check covers most cases, not a save that lands later.

**Checks on the final code:**
- Frontend: lint, typecheck, `api:check` clean; `vitest run` 61 files / 621 tests passed; build
  passed; size: shell 286.4 KB gzip (budget 300; was 283.6), largest lazy chunk 674.5 KB (700).
- E2E (Playwright, real backend, Chromium desktop, mobile, PWA), full suite at `b537ad3`: 81 passed,
  3 skipped, 3 failed, all from this queue: two from the recap's duplicate "Back to …" link, one
  from the longer "Reset code" label hiding the coding toolbar's buttons under the editor. Both
  fixed in the final commit; then the affected specs (careers, display, progress,
  learner-journey, explore, answer-review, onboarding, controls-audit) passed 19, skipped 1. The
  full suite was not re-run locally after the fix; CI runs it.
- Backend: no backend code changed in this queue; not re-run locally (CI runs it).
- Not run here: the sandbox job (Docker and gVisor), a physical phone, a screen reader.

**CI:** reported with the handoff message for the final SHA, job by job.

**Known issue found (not changed):** the coding workspace's editor toolbar hides its buttons
(Save/Submit among them) under the editor when they don't fit on one line, as a slightly longer
label showed at the default panel width; a learner who narrows the panel may hit it.

**Next concrete action:** decide proposal 3 (an idempotency key is the smallest of the three and
closes the remaining duplicate-answer gap), then proposal 1.

## Fourth queue: Durable Saves, Honest Scores & Reliable Revisions (18 briefs), then Release Readiness & Recovery (16 briefs)

## Checkpoint: NX01, reconciled state

- Verified (not taken from the report): branch `claude/gallant-galileo-hapob6`, HEAD = remote =
  `eae8088`, clean working tree; PR #10 open, base `feature/premium-frontend` (`7ace293`), head
  `eae8088`. Not touched: the PR's description, comments, base or reviewers.
- Already satisfied, kept: What next, numbered tries, version-aware comparison, filtered
  breadcrumbs, the lost-reply lookup (it stays as recovery support once keys exist).
- Gaps confirmed in code: answers have no request key (code submissions do:
  `Submission.client_request_id`, unique per owner, `_replay` compares problem, mode and code);
  no stored revision link; `best_score` is a raw `max(score)` in five places (careers, explore,
  activity, roles, roadmap) plus per-answer labels (activity feed, learn, stories); the coding
  toolbar can hide its buttons; tour completion can be lost by a reload. API schemas ignore
  unknown fields (`APIModel` has no `extra="forbid"`), so an older server would silently drop a
  key: the client must not claim protection without a capability signal.
- Practice answers are never restored from a backup (`services/restore.py`, `_RESULTS`), so keys
  and revision links can't collide on restore. Interview rounds also write answers (unkeyed).
- The older playbook's briefs 06–28 never arrived; nothing is assumed about them.

## Checkpoint: NX02, the coding toolbar

- Cause (reproduced): `.editor-toolbar` is a flex item in the editor pane's column with
  `min-height: 44px`, which replaces the content-based minimum; in a short pane the column shrank
  it to 44px and its wrapped second row was painted under the code editor.
- Fix (`styles/features.css`): the toolbar doesn't shrink (`flex-shrink: 0`); its actions wrap
  among themselves (right-aligned). Labels unchanged ("Reset", named "Reset code", confirmation
  says submissions are kept).
- Check: `e2e/workspace-toolbar.spec.ts` (Chromium, desktop layout): a 960×640 window, a
  1440×900 window narrowed to 940×640 after the editor loaded, and 1280×720 with the app's larger
  text; it asserts the toolbar really wrapped, hit-tests every toolbar button (the element under
  its centre is the button), then clicks Save attempt without force. It failed before the fix
  ("Editor settings" covered at 960×640) and passes after. Screenshots inspected at 960 and 1440.
  Not checked: browser zoom itself (the app's text size stands in), a physical device.

## Checkpoint: NX16, the e2e collection error ("reading 'DEV'")

- The failing run kept only its last 25 lines (24 × `TypeError: Cannot read properties of
  undefined (reading 'DEV')`, then `Error: No tests found`); its working directory wasn't recorded.
- Reproduced the same signature: Playwright run without the frontend config (from the repository
  root) collects the Vitest files under `frontend/src`; they import `src/lib/diagnostics.ts`, which
  reads Vite's `import.meta.env.DEV` at load, giving 51 such errors and no tests. With the config
  (`frontend/playwright.config.ts`, `testDir: ./e2e`) no app module is imported by any spec.
- Not changed: no app code (guarding `import.meta.env` would only hide a wrong invocation). Not
  proven: that the failed run lacked the config. Procedure: run e2e as `npm run e2e` (or
  `npx playwright test`) from `frontend/`, as CI does; if the signature reappears, record the
  working directory and `npx playwright test --list | head`.

## Checkpoint: NX03, tour completion survives an immediate reload

- Origin and transport: the API is cross-origin (5173 → 8000) with a bearer header and JSON, so a
  `keepalive` PATCH needs a CORS preflight that not every browser allows for keepalive requests;
  not used. Instead a small recoverable intent: Finish writes "finish pending" for the signed-in
  account before sending (`features/onboarding/finishIntent.ts`: account id and time only, in
  localStorage, never treated as confirmation). Any reply from the server settles it; a definite
  4xx refusal settles it and refetches the server's state; a network failure or 5xx keeps it.
- On the next load `TourFinishReconciler` (mounted once in the layout for the signed-in account)
  asks the server, not the cache: a tour still running or paused there gets "complete" sent again
  (the server applies it only to a running or paused tour, so a repeat or a duplicate Finish is
  harmless); anything else drops the note. Meanwhile the tour panel and the resume banner treat
  the tour as finished. Another account's note is never read.
- Found by the browser regression: React's development double effects discarded the only request
  (a cleanup flag marked it stale and the once-per-load guard skipped the second run); fixed with
  a current-account ref, and a strict-mode case added.
- Checks: `tourFinish.test.tsx` (9: re-send on load, panel hidden meanwhile, strict mode, already
  completed, another account, lost reply kept, refusal dropped, Finish settles, Finish without a
  reply keeps; 6 failed on the previous code), onboarding and session-isolation tests;
  `e2e/tour-finish.spec.ts` (real backend: the Finish PATCH aborted, immediate navigation, the
  next load's "complete" answered `completed`, no resume banner, still finished after a reload).
- Limits: a browser with storage blocked can't keep the note (the finish still saves normally;
  only the after-reload repeat is lost); the note is retried once per load, not in the background.

## Checkpoint: NX04 + NX06 + NX09 (server), keyed answer saves and revision links

Migration `c4d5e6f7a8b9` (additive, nullable): `practice_answers.client_request_id` (String 64),
`request_fingerprint` (String 80), `revises_answer_id` (FK to `practice_answers.id`,
`ON DELETE SET NULL`, indexed), unique `(user_id, client_request_id)`. Existing rows get no key,
fingerprint or link; nothing is rewritten.

- Contract (`POST /careers/{t}/questions/{q}/answers`, documented in the OpenAPI spec): optional
  `client_request_id` (8–64 of `A-Za-z0-9_-`, the code-submission rule). Same owner + same key +
  same request → the saved answer, 200, `Idempotent-Replayed: true`, exactly as graded then (never
  regraded, answered before the rate limit and before a retirement check). Same key + different
  request → 409 `idempotency_key_reused`. A stored fingerprint this code can't compute (another
  version) → 409 `idempotency_key_unverifiable`, never a match. Another account's identical key is
  a different key. `/capabilities` `answer_request_keys: true` says this server enforces it
  (absent/false on older servers, which would ignore the field).
- Request identity: `"v1:" + sha256` of track, question, answer text exactly as sent, story and
  revised answer; stored with the row, so a resend is compared with the original request even if
  the story or the revision link is cleared later.
- Persistence boundary: the database's unique constraint, not process memory; a racing duplicate's
  insert fails and is answered with the saved row (`replayed_concurrent`). Guarantee scope: at
  most one saved answer per owner and key. Grading is the built-in coach, local and
  deterministic; concurrent duplicates may each grade, only one row is kept. No external call is
  made on this path. Not covered: a request sent without a key, or a resend with a new key.
- Revision links: `revises_answer_id` must be the learner's own answer (else 404, no existence
  disclosed) to the same question (else 400 `revision_other_question`); it's part of the request
  identity (a replay can't change it); deleting the earlier answer leaves the revision unlinked.
  Never inferred for older answers. The account export adds each answer's `id` and `revises`
  (keys aren't exported: they're operational, not the learner's data). Practice answers are never
  restored from a backup, as before.
- Signals: span `answer.save` (action `keyed`/`unkeyed`; result `created`, `replayed`,
  `replayed_concurrent`, `key_conflict`, `key_unverifiable`); no key, text or id in labels.
- Checks: `tests/test_answer_keys.py` 29 passed on SQLite and on PostgreSQL 16 (resend,
  unkeyed, 3 conflict shapes, other question, two owners, no regrade, before rate limit/after
  retirement, unknown fingerprint version, 4-way concurrent resends, a deterministic barrier race
  (both past the lookup) for the same and for a conflicting request, a failure before commit, a
  reply lost after commit, 7 invalid keys saving nothing, size limits and 32 distinct keys,
  revision ownership/question/replay/deletion, capability and export). Neighbouring suites: 333
  passed. Migration on a disposable PostgreSQL database (`codecoach_rehearsal_nx`): upgrade head,
  `alembic check` clean, downgrade base. The migration chain doesn't run on SQLite (a pre-existing
  migration alters constraints without batch mode); SQLite is test-only (`create_all`), as
  docs/DATABASE.md says; an existing SQLite dev database made by `create_all` must be recreated.

## Checkpoint: NX05 + NX10 (client), send identity and revision links shown

- Keys only where honoured: the question page sends `client_request_id` only when `/capabilities`
  says `answer_request_keys: true`; an older server (absent or false) gets no key and the page
  claims no protection (its lost-reply message keeps "look under Your past answers first").
- Identity (`features/careers/sendKey.ts`, unit-tested): a key is reused only for the same send
  (account, question, text, story, revised answer) resent after no reply or a failure; edited text,
  another question or account, or a new try after a confirmed save gets a new key. Keys live in
  memory: after a reload the old key is gone, the saved-answer lookup remains the recovery, and no
  duplicate prevention is claimed for the lost key. Nothing is written to browser storage.
- With keys, the lost-reply message says sending the unchanged answer again is safe (the server
  returns the saved one). The existing saved-answer lookup still runs first.
- Revision links: sent only from an explicit Revise/Add (not after "Hide this note", not for a new
  try that merely follows a viewed answer). Shown from the stored link only: "Try 2 revises try 1."
  in the recap, "revised from try 1" in the list, "revises an earlier answer that isn't in this
  list" when the parent isn't listed; the comparison uses the revised try when it's listed, under
  the same rules (version, rubric, coach, scoreable), and never claims improvement.
- Checks: `sendKey.test.ts` (2), `keyedSends.test.tsx` (7; 5 failed on the previous page),
  learnerJourney revision test now expects the link; e2e `answer-replay.spec.ts` (real backend:
  the POST saved, its reply and the lookup dropped, the resend carried the same key and got 200
  `Idempotent-Replayed: true`, one try listed) and `learner-journey.spec.ts` (revision link and
  comparison wording); frontend suite 639 passed after the update, lint, types, API contract clean.

## Checkpoint: NX07 + NX08, score eligibility, defined and applied

Policy (`backend/app/careers/eligibility.py`): an answer's stored score counts in summaries only if
the answer was long enough to score: `evidence_level` recorded as `sufficient`; for answers saved
before that field (legacy), the recorded `word_count` ≥ 40. Too short: `insufficient`, or a legacy
count under 40 (stored score capped at 35, not a measurement). Unknown: neither field recorded
(nothing in this code base writes such a row; reported as unknown, never zero or a score). The
legacy rule is a documented contract: `word_count` stored and MIN_WORDS = 40 with the 35 cap since
the first grader (`f3bb14d`). The rule never looks at the score: 0 and 35 can be real scores.
Raw scores, answer rows and "answered" counts are unchanged; nothing is regraded or rewritten.

| Consumer | Before | Now |
|---|---|---|
| `GET /careers/{t}/questions`, question detail | `best_score` = raw max | `best_score` kept (raw, documented); added `best_scored`, `score_status` |
| `GET /careers/{t}/progress` | answered, strong | same; added `scored`, `too_short`, `unknown` counts |
| explore status, "lowest score first" | raw max; unscored ranked lowest | `best_scored`, `score_status` added; sort by scoreable best, answered-without-score after, unanswered last |
| activity feed, filter, facets | every answer "Scored N/100" | `too_short` status and label ("Too short to score (N words)"); filter and counts split; unknown labelled |
| career analytics (skills, weekly trends) | raw best / raw average | scoreable best; `questions_scored`; trend averages from scoreable answers, `answers` counts all; `questions_practiced` still every answered question |
| job targets (coverage, suggestions) | raw best | scoreable best; "none long enough to score yet"; "Retry: your answer was too short to score" |
| practice plan (roadmap) | raw best = answered | `answered` set separate; scores from scoreable answers; too-short-only questions retried with "too short to score" wording |
| learn link label, story rehearsals | "scored N/100" | "answered (too short to score)"; story list says "too short to score" (`too_short` flag added) |
| frontend: library rows, question badge, Up next, analytics table | raw `best_score` | `best_scored`/`score_status`; Up next retries too-short-only questions with that reason |
| Left on raw scores, deliberately | interview review workspace (`review.py`: worst answer, averages, retry score change), review queue scheduling thresholds, question-round average, shares' snapshot score | each is about one interview or one shared answer, shows the answer itself; recorded here as not migrated |

- Compatibility: every change is an added field or a new status value; `best_score` keeps its
  meaning (raw) for existing clients. Generated types and `docs/openapi.json` regenerated.
- Checks: `tests/test_score_eligibility.py` (7: the rule incl. legacy and unknown; summaries with a
  too-short answer whose capped score beats a real 12; progress counts; lowest-score order;
  activity labels, filter and facets; analytics and trends; targets, suggestions and plan) on
  SQLite and PostgreSQL 16 (JSON operators differ); affected suites 267+ passed (two existing tests
  updated to the policy: progress counts, the baseline retry no longer quoting a capped score);
  frontend 642 passed (Up next too-short case, library/explore mocks, `scoreEligibility.test.tsx`).

## Checkpoint: NX11 + NX12 + NX13, rubric v9 (development data only)

- NX11, denials: an I/we refusal or denial, or "instead of", blanks the rest of its own clause
  (at most ten words) for cue matching; inability, a missing opportunity, "without", "not only",
  "didn't just" and someone else's negation aren't denials; a new I/we statement ends the clause,
  so dictated run-ons keep their second half. New register entry `denied-actions-credited`
  (fixed). A first, broader draft lost 11 valid points and was narrowed before commit.
- NX12, contradictions: explicit contradictions are already reported in every written form
  probed (full stop, comma splice, dictated run-on, never/did) and the controls (self-correction,
  later action, quoted speech, unrelated negation) are clean: no bounded defect shown, so no rule
  changed; the probe is now a test. Meaning-based contradictions stay open.
- NX13, reported advice: "Advice I was given: …" and "I was told to …" are read as someone else's
  advice, not the learner's account (fixes `paraphrased-guidance-credited`); the CSR
  `keyword_list` family is now gated (protocol v7).
- Measured (v8 from `59f267f` via `--career-grader git:HEAD` → v9 `27bdc8f`, comparison
  `evals/results/rubric-v8-vs-v9.md`): 0 regressions, 7 fixed, recall unchanged on every set;
  meaning-changed false awards 10/18 → 8/18 (nursing) and 8/11 → 6/11 (customer service);
  unsupported credit 23 → 21 and 26 → 21; CSR keyword false awards 1/9 → 0/9. Exposed
  development data, not an independent measurement; the sealed sets weren't graded.
  `support.py` still records v8 as the measured rubric.
- Checks: `tests/test_rubric_v9.py` (29), eval, careers, scope, harness (incl. loading v8 from
  git) and eligibility suites passed; lint, format, types clean.

## Checkpoint: NX14, a human label review packet (prepared; human review pending)

- `backend/evals/review_sample.py` makes a bounded, seeded sample of development and exposed
  historical cases (never a sealed set). Strata: `disagreement` (10 cases where rubric v9 and a
  label differ, or the labeller was unsure; chosen on purpose, not representative) and `random`
  (2 per set by sha256(seed:set:case), 14). It has a blind first pass and a reveal pass with
  adjudication.
- The blind pass hides proposed labels, coach decisions and case ids (ids name the variant). The
  form asks for label, uncertainty, needs-expertise and rationale, and flags points worded as if
  they judged correctness. Structural and domain judgements are kept apart.
- Imports and adjudications need `--human` and a named reviewer, so model labels can't be recorded
  as a review. Agreement is reported only with two or more people on the same points.
- Committed: `evals/reviews/samples/sample-2026-11-05.json` (24 cases, 119 points, status
  "prepared; human review pending"). No ratings file exists. Nothing was shared or sent.
- Label changes: documented as a new dataset version with a `label_changes` audit trail, old
  reports kept as they are (EVAL_PROTOCOL.md, "When a review changes a label"). The validator
  now enforces each entry's fields and later version, and that it matches the set's current
  label.
- Checks: `tests/test_review_sample.py` (6) and a new validator test in `test_eval_protocol.py`.
- Unresolved: no reviewer has taken part, so this needs people; next action is a person running
  `python -m evals.review_sample packet sample-2026-11-05`.
