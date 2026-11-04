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
