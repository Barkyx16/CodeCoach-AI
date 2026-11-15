# One connected preparation journey

One real path through the app, from a target requirement to the material a learner takes into an
interview, checked end to end in a browser against the real API (Volume 12, prompt 10). It proves
the path it exercises on the candidate it ran on: not that everything else works, and not that
practising this way helps anyone learn.

There are two: a registered nurse's (written answers, checked by the built-in coach's fixed rules)
and, since Volume 13, prompt 10, [a software engineer's](#the-software-engineers-journey) (code
judged in the gVisor sandbox, with approved coach context). Together they cover both kinds of
practice.

- The journey: `frontend/e2e/preparation-journey.ts`, run by `preparation-journey.spec.ts`
  (desktop) and `preparation-journey-mobile.spec.ts` (a Pixel 7 phone).
- The branches: `frontend/e2e/preparation-branches.spec.ts` (desktop).
- Logs and traces: `backend/tests/test_journey_canary.py`.
- The latest record: [Record](#record) below.

## The journey

A registered nurse, on a fresh synthetic account. Each step checks what the learner sees, and
records the ids it created.

| # | Step | What it checks (as the learner sees it) |
|---|---|---|
| 1 | A target requirement | A posting with "Perform patient assessment and triage for incoming patients" and "Administer medications and monitor patient responses" becomes a workspace listing both; its short targeted session is the patient-assessment question first |
| 2 | Approved coach context | **Absent for this path.** Only the code review shows and binds what the coach reads (docs/COACH_CONTEXT.md); written answers, career interviews and story help send nothing to a coach, so a nurse has nothing to approve. It's exercised on a software-engineer account by `e2e/coach-context.spec.ts`, not here |
| 3 | A baseline attempt | The targeted session starts from the target; three answers saved; the patient-assessment answer's score is recorded (72/100 with the journey's text) |
| 4 | Its recorded assistance | The answer says "In-app help before this attempt: No in-app help recorded": no lesson prepares this question and no hint was shown (docs/ATTEMPT_CONDITIONS.md). The "Hint shown" case isn't on this path |
| 5 | Feedback review | The replay's "Work on next" names "Explains why it matters", missing in 3 of 3 answers |
| 6 | An accepted improvement | Accepted as a weekly action; the target's requirement lists "Accepted improvement “Explains why it matters”" |
| 7 | Its calendar placement | The plan schedules two weeks; the schedule shows it in the first week, not yet done |
| 8 | A related follow-up attempt | A retry from the replay (compared with the interview answer and labelled partly comparable: the conditions differed) makes two scored answers, so "A related question" offers "Checking your medication administration work", not previously attempted; answered from the offer, it's its own attempt linked to the retry, shown with its own score, and listed on the first question beside its tries, "Scores aren't combined" |
| 9 | Final preparation material | A story for the requirement; an application, an interview and its kit; the kit's checklist reads the same action ("Explains why it matters · 0 of 2 weeks done") and the printable pack lists it with the story |
| 10 | Found again | After a reload, in a second tab and after a fresh sign-in in another browser: the kit, its story and the follow-up's score; then, by the API with a new token, every id and the links between them (requirement ids; the action, its interview and two occurrences; the review's link to it; the three answers and the follow-up's link to the retry; the kit's action and story; the story's requirement) |
| 11 | No secret in the logs | The API's access log for the run doesn't contain the canary typed into the story |

**Honest outcomes.** The follow-up's score is whatever the server gives (52/100 with the journey's
text, lower than the baseline's 72): the journey records it and checks the page shows that number,
uncombined, with no "improved" wording. Nothing is replaced by an invented improvement.

## The branches

Each on its own fresh account, seeded through the API up to the point it tests, then checked in the
browser. Each has a negative control: the protection removed, the branch fails.

| Branch | What it checks | Negative control (caught) |
|---|---|---|
| Disputed advice | Disputing "Explains why it matters" on the baseline answer labels the accepted improvement "It stays as it is; it's yours to keep, move or mark done." and keeps it | `disputes.for_action` never matches |
| Incompatible comparison | A retry too short to score says "too short to score: compare what you wrote, not the numbers" and shows no score change | the too-short rule removed from `careers/comparability.py` |
| Stale evidence | Editing the story's result after it was chosen: the kit says "The story changed since you chose it for this kit (version 1, now 2)…" and the pack shows the version prepared | `result` dropped from the fields freshness relies on |
| A deletion race | An event added after the delete preview: "What this affects changed since you looked. Nothing was done…", and the application still exists | the previewed fingerprint not compared |
| A lost response | The first accept is saved but its reply is lost; accepting again finds the same action (one action) | the existing action not looked up |
| Another account | The kit page says "This interview kit isn't available", the interview isn't found, and the action, target and kit are 404 by the API | the kit found by its ids alone |
| Logs and traces (backend) | With every log at DEBUG and traces on, a canary in the posting, answers, story, kit notes and a search query never appears in a server log record or trace span | the access log recording the query string |

## What's real and what's substituted

- **The coach**: the built-in offline coach (`AI_PROVIDER=offline`): a real mode of the app, which
  checks written answers by fixed rules on CodeCoach's server. No outside AI provider is called; the
  journey records `/api/v1/capabilities` (`ai_provider: offline`).
- **The judge**: not used. A nurse's path has no code to run (`code_execution: false` recorded); no
  step is a judge step.
- **Email**: the e2e API writes would-be emails to a file outbox; the journey sends none.
- **Database**: a fresh SQLite file per run (`backend/e2e[-N].db`), deleted at start. The backend
  suites cover PostgreSQL.
- **Time**: the real clock; dates are relative to the run.

## How to run it

On a clean checkout of the commit to test (the runner records the commit and says if anything
differs from it, before or during the run):

```bash
cd frontend
E2E_PORT_OFFSET=60 npm run e2e -- e2e/preparation-journey.spec.ts e2e/preparation-branches.spec.ts --project=desktop --repeat-each=2 --trace off
E2E_PORT_OFFSET=60 npm run e2e -- e2e/preparation-journey-mobile.spec.ts --project=mobile --repeat-each=2 --trace off
```

`test-results/e2e-provenance.json` names the candidate; `test-results/journey/*.json` holds each
run's steps, checks, ids and facts (scores, provider).

## Record

**Candidate**: `c150811` (the commit that added the journey), on 14 November 2026, in a clean
checkout of it. Before and after each run the e2e runner reported "runtime inputs unchanged from
the commit" (`differs_at_start` and `changed_during_run` empty in `e2e-provenance.json`), so the
results are evidence for that commit.

**Environment**: a Linux container; Playwright's Chromium at 1440×900 (desktop) and emulating a
Pixel 7 (phone); the API under uvicorn on a fresh SQLite database; port offset 60.

| Run | Tests | Outcome |
|---|---|---|
| The journey and its branches, desktop, twice (`--repeat-each=2`) | 14 passed | passed |
| The journey at phone size, twice | 2 passed | passed |
| The full browser suite, every project (includes the journey once on each viewport) | 177 passed, 5 skipped | passed |

**Steps**, the same in all six journey runs (two desktop, two phone, and one of each in the full
suite), with the same checks and the same scores:

| # | Step | Outcome |
|---|---|---|
| 1 | A target requirement | passed |
| 2 | Approved coach context | absent (not part of this career's path; above) |
| 3 | A baseline attempt | passed: 72/100 |
| 4 | Its recorded assistance | passed: "No in-app help recorded" |
| 5 | Feedback review | passed: "Explains why it matters", missing in 3 of 3 |
| 6 | An accepted improvement | passed |
| 7 | Its calendar placement | passed: two weeks |
| 8 | A related follow-up attempt | passed: the retry 92/100, partly comparable; the follow-up **52/100, lower than the baseline**, shown as that |
| 9 | Final preparation material | passed |
| 10 | Found again (reload, second tab, fresh sign-in, API with a new token) | passed |
| 11 | No secret in the logs | passed |

Every id the journey created was found again with the same links: the target and its 8
requirement ids, the interview, the action and its 2 occurrences, the 3 answers (baseline, retry,
follow-up, linked to the retry), the story (linked to the patient-assessment requirement), the
application, the interview event and its kit.

**Substitutes and skips**: the coach was the built-in offline coach (`ai_provider: offline`, no
outside provider called); the judge wasn't used (`code_execution: false`, real judge off); no email
was sent. Skipped: step 2 (absent for this career); in the full suite, the four judge tests (they
need Docker, gVisor and the sandbox image) and the opt-in controls audit.

**Canary**: not in the API's access log, the e2e outbox, or anything the three runs printed
(including the API server's own output). With every log at DEBUG and traces on,
`test_journey_canary.py` passes on SQLite and PostgreSQL.

**Negative controls**: 7, each caught: one per branch in the browser, and the logs check.

**Found on the way**, both fixed before this candidate (test only), and both in it:
- The first full browser run (on an earlier candidate) failed two older specs, learner-journey.spec.ts
  and review.spec.ts, which still expected comparison wording from before prompt 6; CI run 314 failed
  the same two. Fixed in `87fc649`.
- CI run 315 failed disputes.spec.ts once: on a slow runner the dashboard's plan request built the
  plan before the spec's weak answer existed, and a plan isn't rebuilt for an answer outside it.
  Fixed in `020eeb1`; the spec now holds that request until the answer is saved.

An earlier candidate with the same journey code, `66e9418`, gave the same results before those
hashes changed (the commits were replayed on top of the fixes).

## The software engineer's journey

The parts the nurse's journey couldn't use: approved coach context and the real judge (Volume 13,
prompt 10). A software engineer on a fresh synthetic account; each step checks what the learner sees
and records the ids it made, what it ran on (`uses`: the real judge, the built-in coach) and the
judge's verdicts as the judge reported them (`judged`).

- The journey: `frontend/e2e/engineer-journey.ts`, run by `engineer-journey.spec.ts` (desktop) and,
  for the steps with a phone layout of their own, `engineer-journey-mobile.spec.ts` (a Pixel 7).
- The branches: `frontend/e2e/engineer-branches.spec.ts` (desktop).
- Where it runs: CI's sandbox job, which installs gVisor and builds the sandbox image, runs all three
  twice on fresh accounts (`--repeat-each=2`) with `E2E_JUDGE=1`, prints each run's record as a
  `[journey-record]` line and keeps `test-results/journey/` with `e2e-provenance.json` as the
  `engineer-journey-record` artifact. Elsewhere the journeys skip, saying they need the real judge
  (Docker, gVisor and the sandbox image). With `E2E_JUDGE=1` but no ready judge, the first step
  fails with the judge's state and the record says `stopped`: no verdict is ever recorded that the
  sandbox didn't give.

| # | Step | Uses | What it checks (as the learner sees it) |
|---|---|---|---|
| 1 | The judge is ready | | `/capabilities`: code execution on, the judge `ready`, the coach `offline` |
| 2 | A target requirement | | A posting with "Strong knowledge of data structures and algorithms" becomes a requirement, not practised yet, offering "Problem: Two Sum · Coding practice for arrays, hash maps"; the link opens the workspace |
| 3 | Approved coach context: a hint | built-in coach | Checking shows the code the coach will read for a level 1 hint (nudge) and uses nothing; the request then sent carries the preview's fingerprint and exactly the code it showed; the hint is shown and one request is used |
| 4 | A coding baseline, judged for real | real judge | Submitted in the workspace and judged in the sandbox: the verdict, tests passed, hidden tests passed and time in the method, as the results panel shows them |
| 5 | Its recorded help | | The submission's page says "In-app help before this attempt: Hint shown" with "Level 1 hint (nudge)" (docs/ATTEMPT_CONDITIONS.md) |
| 6 | An approved code review | built-in coach | The preview lists what the coach will read; the review request carries its fingerprint and the code it showed, is answered (200, "What's working") and uses one request |
| 7 | Feedback review: a coding interview | built-in coach | A coding interview on the same problem, finished; its feedback's "Work on next" lists the built-in interviewer's lowest rubric skills |
| 8 | An accepted improvement | | The first of them accepted as a weekly action, from that interview |
| 9 | Its calendar placement | | The plan schedules two weeks; the schedule shows it in the first week, not yet done |
| 10 | A resubmission, judged for real | real judge | A correct solution, judged in the sandbox; its own help reads "No in-app help recorded" (a hint belongs to the attempt after it). **Not compared**: coding submissions have no comparison verdict (docs/COMPARING_ATTEMPTS.md), so History lists both with their own verdict and help, the improvement says "This kind of improvement has no practice linked to it yet: mark it done when you've done it." rather than claiming the resubmission, and the requirement reads what the server says ("Some practice") |
| 11 | Final preparation material | | An application, an interview and its kit; the checklist reads the same action ("Problem solving · 0 of 2 weeks done") and the printable pack lists it |
| 12 | Found again | | After a reload, and after a fresh sign-in in another browser: both submissions with their verdicts and the baseline's hint, and the kit; then by the API with a new token: the requirement ids, both submissions' verdicts, the action (its interview and two occurrences), the review's link to it and the kit's |
| 13 | No secret in the logs | | The API's access log doesn't contain the canary typed into the code and the kit's notes |

**At phone size** (`engineer-journey-mobile.spec.ts`): the workspace's own phone layout, its
Problem, Code and Coach tabs. A hint checked then asked for in the Coach tab, the baseline and the
resubmission judged from the Code tab, an approved code review in the Coach tab, and the baseline's
recorded help with no sideways scroll. The other steps' pages are the desktop ones in one column,
checked at phone width by their own specs.

### Its branches

| Branch | What it checks | Negative control (caught) |
|---|---|---|
| Code changed after the preview | By the API, the preview's fingerprint with other code is 409 `context_changed`, with what the coach would read now, and nothing is used; in the browser, a review request that leaves with other code than the preview showed (as a stale tab would send it) is refused: "What the coach would read changed since you checked it, so nothing was sent. This is what it would read now.", the new code shown, no review | the fingerprint comparison in `services/ai/service.py` removed |
| A judged resubmission | After a hint, a failed and a passing submission (both judged) and an improvement from a coding interview: History gives each its own help ("Hint shown" once, "No in-app help recorded" once), the resubmission's page its own verdict, and the plan says no practice is linked to the improvement | a hint counted for every later attempt (`services/conditions.py`); an improvement with no stored link reported as linked with nothing found (`services/related_practice.py`) |
| Another account's submission | Its page says "This submission isn't available"; the API says 404 `not_found`; a code review or a failure explanation preview naming it is 404; its conditions aren't returned; the owner still has it | the submission found by its id alone (`api/routes/submissions.py`) |

The changed-code and another-account branches don't need the judge and run in every e2e run; the
resubmission branch skips without it.

### What's real and what's substituted

- **The judge**: real. The API's worker sends each submission to the runner, which runs it in the
  sandbox image under gVisor (`runsc`), with no network. The verdicts are the API's copy of the
  runner's result, recorded as given: status, its detail, tests passed and total, hidden tests
  passed and total, the time in the method across the tests and per public test, both as the judge
  reported them; and, by the server's clock, the time from the request to the verdict.
- **The coach**: the built-in offline coach (`AI_PROVIDER=offline`), labelled as such in every
  preview; no outside AI provider is called. The coding interview's interviewer is the built-in one.
- **That the coach was sent what it showed**: proved by the request the page sent, not by the
  server: the API doesn't expose what was sent (by design). The server's side, that a request not
  matching its preview is refused, is the changed-code branch; the byte-for-byte check is in
  `backend/tests/test_coach_context.py`.
- **Email, database, time**: as for the nurse's journey (above).

### How to run it

Needs Docker with gVisor and the sandbox image (`docker build -t codecoach-java-sandbox:21
runner/sandbox-image`):

```bash
cd frontend
E2E_JUDGE=1 E2E_PORT_OFFSET=60 npm run e2e -- e2e/engineer-journey.spec.ts e2e/engineer-branches.spec.ts e2e/engineer-journey-mobile.spec.ts --repeat-each=2 --trace off
```

### Its record

**In CI**: pending, the sandbox job of the run on the commit that adds the journey. The next commit
records that run, its commit and the verdicts here.

**Before CI** (not the record; the development check): a Linux container with gVisor (`runsc`,
`4.19.0-gvisor`) and the sandbox image, on 15 November 2026, on `626276c` plus the journey's files
(the runner named them). All three specs twice: 10 passed, `real_judge: true`, nothing changed
during the run. Both desktop runs: the same 13 steps passed with the same checks; both phone runs
the same 6.

| Submission | Verdict | Tests | Hidden | In the method | Request to verdict |
|---|---|---|---|---|---|
| Baseline (desktop, both runs; phone, both runs) | FAILED, "Some tests failed." | 2 of 7 | 0 of 4 | 1 ms | 3.7-4.2 s |
| Resubmission (desktop, both runs; phone, both runs) | PASSED, "All tests passed." | 7 of 7 | 4 of 4 | 1-2 ms | 3.8-4.0 s |

The coding interview's feedback listed "Problem solving; Code quality" both times; "Problem solving"
was accepted. The requirement read "Some practice" after the resubmission. Negative controls: 4,
each caught (above). Without `E2E_JUDGE`, the two judge-free branches passed and the rest skipped,
saying why.

## Limits

- The nurse's path: one career, a registered nurse. The coach-context step is absent for it (above);
  the "Hint shown" assistance label isn't on it (the software engineer's journey has it); the judge
  isn't used.
- The software engineer's path: one problem (Two Sum), Java only. Coding submissions aren't
  compared with each other (no comparison verdict exists for them yet), and an improvement from a
  coding interview has no practice linked to it, so nothing ties the resubmission to the improvement
  except the learner. The target's requirement links to the problem, not to the submissions.
- The journey links the follow-up and the accepted improvement only by order. Since Volume 13, prompt 4, a
  follow-up to the improvement's question is listed under its Related practice (docs/ACCEPTED_ACTIONS.md);
  the recorded journey above predates that and doesn't check it.
- The practice packet can't hold accepted improvements, so the final material is the interview-day
  kit.
- Phone size is Chromium emulating a Pixel 7, not a real phone; no screen reader, Safari or Firefox.
- The e2e server logs warnings only; traces are checked by the backend test, not in the browser run.
- It proves this integration path on this candidate, not universal correctness or learning effect.
