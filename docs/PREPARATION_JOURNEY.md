# One connected preparation journey

One real path through the app, from a target requirement to the material a learner takes into an
interview, checked end to end in a browser against the real API (Volume 12, prompt 10). It proves
the path it exercises on the candidate it ran on: not that everything else works, and not that
practising this way helps anyone learn.

There are two: a registered nurse's (written answers, checked by the built-in coach's fixed rules)
and, since Volume 13, prompt 10, [a software engineer's](#the-software-engineers-journey) (code
judged in the gVisor sandbox, with approved coach context). Together they cover both kinds of
practice. Since Volume 15, prompt 10, [a third](#two-devices-and-a-restore) follows one account
across two devices and a backup and restore.

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
| 10 | A resubmission, judged for real | real judge | A correct solution, judged in the sandbox; its own help reads "No in-app help recorded" (a hint belongs to the attempt after it). **Compared** with the baseline by the one comparison rule (since Volume 14, prompt 1; docs/COMPARING_ATTEMPTS.md, "Coding submissions"): under the result, "Partly comparable: the in-app help differed: before the earlier one, hint shown; before the later one, none recorded. The counts are from the same tests, so both are shown", both verdicts as judged; History lists both with their own help and the comparison on the later one; the improvement's related practice lists the resubmission ("Submission: Two Sum", passed, since Volume 14, prompt 2: the coding interview names its problem), without ticking it; and the requirement reads what the server says ("Some practice") and lists both submissions, newest first, with their verdicts. Once it passed, the reviewed related problem is **offered under the result** (since Volume 14, prompt 10; docs/FOLLOW_UPS.md, "Coding problems"): "Two Sum in a Sorted Array", "Not previously attempted in this app" |
| 11 | A related problem, judged for real | real judge | Opened from the offer beside Two Sum, the workspace says it's a follow-up with its own verdict; a two-pointer solution judged in the sandbox, its verdict recorded as the judge gave it; the result records the passed resubmission it follows ("A follow-up to Two Sum, a different problem. Its own verdict, not combined with that problem's or compared with it.") and isn't compared; Two Sum lists it under "Follow-ups you submitted" with its counts and offers it no more; the export carries the link |
| 12 | Final preparation material | | An application, an interview and its kit; the checklist reads the same action ("Problem solving · 0 of 2 weeks done") and the printable pack lists it |
| 13 | Found again | | After a reload, and after a fresh sign-in in another browser: both submissions with their verdicts and the baseline's hint, and the kit; then by the API with a new token: the requirement ids, both submissions' verdicts, the action (its interview and two occurrences), the review's link to it and the kit's |
| 14 | No secret in the logs | | The API's access log doesn't contain the canary typed into the code and the kit's notes |

**At phone size** (`engineer-journey-mobile.spec.ts`): the workspace's own phone layout, its
Problem, Code and Coach tabs. A hint checked then asked for in the Coach tab, the baseline and the
resubmission judged from the Code tab (the related problem then offered under its result, in the
Code tab, with no sideways scroll), an approved code review in the Coach tab, and the baseline's
recorded help with no sideways scroll. The other steps' pages are the desktop ones in one column,
checked at phone width by their own specs.

### Its branches

| Branch | What it checks | Negative control (caught) |
|---|---|---|
| Code changed after the preview | By the API, the preview's fingerprint with other code is 409 `context_changed`, with what the coach would read now, and nothing is used; in the browser, a review request that leaves with other code than the preview showed (as a stale tab would send it) is refused: "What the coach would read changed since you checked it, so nothing was sent. This is what it would read now.", the new code shown, no review | the fingerprint comparison in `services/ai/service.py` removed |
| A judged resubmission | After a hint, a failed and a passing submission (both judged) and then an improvement from a coding interview: History gives each its own help ("Hint shown" once, "No in-app help recorded" once), the resubmission's page its own verdict and its comparison with the first ("Partly comparable: the in-app help differed …"), and the improvement's related practice has none (both came before it was accepted) | a hint counted for every later attempt (`services/conditions.py`); an improvement with no stored link reported as linked with nothing found (`services/related_practice.py`) |
| Another account's submission | Its page says "This submission isn't available"; the API says 404 `not_found`; a code review or a failure explanation preview naming it is 404; its conditions aren't returned; the owner still has it | the submission found by its id alone (`api/routes/submissions.py`) |

The changed-code and another-account branches don't need the judge and run in every e2e run; the
resubmission branch skips without it.

### Its record

CI run 325 (`a11cd22`, the sandbox job, with the real judge; the `engineer-journey-record` artifact
and the job's `[journey-record]` lines): **10 passed**, nothing flaky or skipped.

| Run | Steps | Baseline (judged in the sandbox) | Resubmission (judged in the sandbox) | Compared |
|---|---|---|---|---|
| Desktop, first | 13 of 13 passed | FAILED, 2/7 (hidden 0/4), 0 ms in the method; verdict 3.6 s after the request | PASSED, 7/7 (hidden 4/4), 1 ms; 3.5 s | "Partly comparable: the in-app help differed: before the earlier one, hint shown; before the later one, none recorded. The counts are from the same tests, so both are shown. (Comparison rules v1)" |
| Desktop, second | 13 of 13 passed | FAILED, 2/7 (hidden 0/4), 1 ms; 3.5 s | PASSED, 7/7 (hidden 4/4), 1 ms; 3.6 s | the same words |
| Phone size, first | 6 of 6 passed | FAILED, 2/7 (hidden 0/4); 3.2 s | PASSED, 7/7 (hidden 4/4), "No in-app help recorded"; 3.4 s | (not on the phone path) |
| Phone size, second | 6 of 6 passed | FAILED, 2/7 (hidden 0/4); 3.3 s | PASSED, 7/7 (hidden 4/4); 3.3 s | (not on the phone path) |

The three branches passed in both repeats. Each run was a fresh account with its own ids (in the
record); the built-in coach answered the hint and the review, and `/capabilities` said the judge was
"ready" each time.

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

## Two devices and a restore

Volume 15, prompt 10. One account on a desktop window and a phone-sized one (Chromium emulating a
Pixel 7, its own browser context and sign-in) and then through a backup: what's chosen, saved and
dismissed on one is the same on the other, by id, and a version 2 backup brings the collection and
the accepted improvement back with their ids, versions and reviews, and its undo takes them away
again. Both contexts stay open from the phone's first step to the end, so each change made on one is
read on the other after a reload, not after a new sign-in. The record names the device that made
each change (`made_on`) and the one that read it back (`read_on`).

- The journey: `frontend/e2e/device-journey.ts`, run by `device-journey.spec.ts` (the desktop
  project; it opens the phone context itself).
- Where it runs: CI's end-to-end job, in its normal run and then twice more on fresh accounts
  (`--repeat-each=2`), printing each run's record as a `[journey-record]` line and keeping
  `test-results/journey/` as the `device-journey-record` artifact.

| # | Step | Made on → read on | What it checks |
|---|---|---|---|
| 1 | Two questions saved to a collection | desktop | Both added to a new collection from their pages; by the API, its id, its items' ids and the version each was added at |
| 2 | Answered twice, the second compared with the first | desktop | Try 2 is set beside try 1 ("Compared with try 1. …"), by the comparison contract |
| 3 | A follow-up question dismissed with Not now | desktop | "A related question" offered the follow-up; Not now took it away; by the API, one dismissal kept with the account |
| 4 | An improvement accepted | desktop | A three-question round answered on the desktop; the first point of its "Work on next" accepted |
| 5 | The phone reads the same | desktop → phone | The collection with the same two questions in order, both tries, the follow-up not offered, the one improvement; by the API with the phone's own sign-in, the same item ids, dismissal key, improvement id and answer ids |
| 6 | An answer on the phone, seen on the desktop after a reload, both open | phone → desktop | The phone answers the second question while the desktop has its page open; after a reload the desktop lists the phone's answer and score |
| 7 | A question in the collection corrected, and marked reviewed | phone → desktop | An admin (granted from the command line) corrects the second question; the phone's collection badges it "Source updated" and marks it reviewed at the new version; the desktop's copy shows it reviewed |
| 8 | A version 2 backup downloaded | desktop | Settings' "Include links between records (format version 2)" and "Download my data": the file carries the collection and the improvement by id |
| 9 | The collection and the improvement deleted | phone → desktop | Each deleted on the phone after its own confirmation; the desktop, after a reload, finds the collection gone |
| 10 | Restored from the file | desktop → phone | The preview offers the collection and the improvement as "1 new" each and nothing else; one restore batch, applied; by the API, the collection with the same id, item ids, order, added-at versions and review, and the improvement with the same id and source; the phone, after a reload, has both (still reviewed) |
| 11 | The restore undone | desktop → phone | "Remove what this added" removes both and keeps none; the batch is recorded as removed; by the API both are gone; the phone, after a reload, finds the collection gone; the dismissal still holds (a restore never touches it) |
| 12 | No secret in the logs | | The API's access log contains neither the canary typed into the desktop's answer nor the one typed into the phone's |

Every phone step checks the page doesn't scroll sideways at the phone's width.

**What isn't checked from the page, and what is instead.** Ids aren't on the page, so each id is
read by the API (step 5 with a second sign-in, the phone's own). The improvement's acceptance needs
an interview, made through the API and answered on the desktop's page. The admin's correction is
made through the API by an account granted from the command line, as an admin would.

**Found on the way.** Settings still said a version 2 download "can't be restored yet, so keep a
standard download for that", but since Volume 14, prompt 5 and Volume 15, prompt 6 it's the only
file that restores accepted improvements and collections: the label now says it keeps the ids
those need.

### Its record

**In CI**: run 343 (`690f000`), the end-to-end job, in its normal run and then in the step that runs
it twice on fresh accounts (the `device-journey-record` artifact and the job's `[journey-record]`
lines): **3 passed**, 12 of 12 steps each, every step's device named the same way: steps 1 to 4 and
8 made on the desktop; 5, 10 and 11 made on the desktop and read back on the phone; 6, 7 and 9 made
on the phone and read back on the desktop. Each run's collection came back from the backup with its
own two item ids, in order, and its review; each restore batch was applied and then removed:

| Run | Collection | Improvement | Restore batch | Added at | Reviewed at |
|---|---|---|---|---|---|
| Normal run | `126e299c…` | `88b476ef…` | `8cd94db5…` | e-inform-0 v1, e-inform-3 v1 | v2 |
| Step, first | `0335d0cf…` | `b755ad96…` | `0c74aea0…` | e-inform-0 v1, e-inform-3 v1 | v2 |
| Step, second | `7c4f769a…` | `eac1101f…` | `7326e2b8…` | e-inform-0 v1, e-inform-3 v2 | v3 |

(Corrections are shared content: the step's second run found the question at the version the first
left, and corrected it once more.) The phone was 412 × 839; the step took 1 min 2 s.

**Before CI** (the development check, not the record): this machine, on 15 November 2026, through
the e2e launcher, twice in a row on fresh accounts: 12 of 12 steps each, each step's device named;
the collection was restored with its two item ids, both added at version 1 (the second at version 2
in the second run: the corrections are shared content and accumulate), and its review at the
version the correction made (2, then 3). The whole browser suite on the same tree: 202 passed, 8
skipped (they need the real judge or are the opt-in controls audit) and one failed because the disk
filled up (`ENOSPC`); with space freed, that spec passed on its own (8 of 8).

## An engineer on two devices

Volume 16, prompt 10. The two-device journey above proves a nurse's account; the engineer's journey
proves the real judge on one device. This one does both: code judged for real on a desktop, read on
a phone signed in to the same account (Chromium emulating a Pixel 7, its own context and sign-in,
both open to the end), with this volume's kept check (prompt 3) and judged code as plan evidence
(prompt 7) in it. The record names, for every step, the device that made the change (`made_on`) and
the ones that read it (`read_on`), with the ids, and the judge's verdicts as it gave them.

- The journey: `frontend/e2e/engineer-devices.ts`, run by `engineer-devices.spec.ts` (the desktop
  project; it opens the phone context itself).
- Where it runs: CI's sandbox job, in the step that already runs the engineer's specs twice on fresh
  accounts with the real judge (`E2E_JUDGE=1`, `--repeat-each=2`); its record is in the step's
  `[journey-record]` lines and the `engineer-journey-record` artifact. No new job. Without the real
  judge it skips, saying why; with `E2E_JUDGE=1` but no ready judge it stops at its first step with
  the judge's state, never recording a verdict nobody judged.

| # | Step | Made on → read on | What it checks |
|---|---|---|---|
| 1 | The judge is ready | | `/capabilities`: code execution on, the judge "ready", the built-in coach |
| 2 | The plan to start from | desktop | Version 1, nothing new; the page says the plan reads the judge's verdicts on submitted code (not runs) |
| 3 | A hint, then a baseline judged for real | desktop | A level 1 hint from its preview; Two Sum's baseline judged in the sandbox (failed), recorded as judged |
| 4 | A resubmission judged for real, compared by the contract | desktop | Passed in the sandbox; compared with the baseline by the one contract, the sentence kept; never "improved" |
| 5 | Both read on the phone, the comparison word for word | desktop → phone | By id, the phone's own sign-in reads both verdicts as judged; the phone's comparison is the desktop's, word for word |
| 6 | The plan offers the judged code, accepted on the phone | phone | "2 submissions (1 not passed) since this plan.", by skill ("Arrays: “Two Sum” didn't pass (tests failed), then passed: …"), the rule; "Update my plan" makes version 2, which records both submissions it read, by id |
| 7 | The update seen on the desktop after a reload | phone → desktop | Version 2, "Code this update read as new evidence" linking both by id, nothing left to update |
| 8 | A coding interview checked on the phone, left to time out | phone | Started on the phone, code (with the phone's canary) sent with a message; with 75 seconds left "Check what the feedback will read" and "I've checked this", kept at its time; the clock runs out on the server, the page open |
| 9 | Recorded as checked, with the time, on both devices | phone → phone, desktop | "You checked this before time ran out." with the check's time, on the phone and the desktop (and by the API) |
| 10 | Nothing typed reached the API's log | | Neither the desktop's code canary nor the phone's is in the API's log |

Every phone step checks the page doesn't scroll sideways at the phone's width.

**What isn't checked from the page, and what is instead.** Ids aren't on the page, so they're read
by the API (step 5 with the phone's own sign-in). The shortest interview is 10 minutes, too long to
wait out twice in CI: once the code is sent, the interview's deadline is moved to 75 seconds away in
the browser suite's own database (`bringDeadlineNear`, the one direct write), then the clock runs out
for real, on the server, while the phone has the page open. Nothing else is written around the app.

**Negative controls, each caught by this journey with the real judge here:** the confirmed check not
kept when time runs out (step 9 fails on the review's words) and judged code not offered as plan
evidence (step 6 finds no offer).

**Found on the way.** The plan's sentence named a problem tried twice twice ("“Two Sum” didn't pass
(tests failed) and “Two Sum” passed"); it now names each problem once with its attempts in order
("“Two Sum” didn't pass (tests failed), then passed").

### Its record

**Before CI** (the development check, not the record): this machine, on 16 November 2026, with the
real judge in gVisor, through the e2e launcher: 10 of 10 steps, every step's device named (2 to 4
made on the desktop, 5 read on the phone, 6 and 8 made on the phone, 7 and 9 read back on the
desktop and both). The judge's verdicts as it gave them: the baseline FAILED, 2 of 7 tests (hidden 0
of 4), 4 ms in the method, 4.1 s from request to verdict; the resubmission PASSED, 7 of 7 (hidden 4
of 4), 3 ms, 4.1 s. The contract's outcome: partly comparable ("the in-app help differed: before the
earlier one, hint shown; before the later one, none recorded. The counts are from the same tests, so
both are shown."). Version 2 read both submissions; the check was kept and the review said "You
checked this before time ran out." with its time on both devices. The phone was 412 × 839; the run
took 1.8 minutes.

**In CI**: run 348 (`962a410`), the sandbox job's step that runs the engineer's specs twice on fresh
accounts with the real judge (the `engineer-journey-record` artifact and the job's `[journey-record]`
lines): **10 of 10 steps, both times**, every step's device named as above. The judge's verdicts as
it gave them, and the time from request to verdict:

| Run | Baseline | Resubmission | Check kept at | Interview |
|---|---|---|---|---|
| First | `10c52eed…` FAILED, 2 of 7 (hidden 0 of 4), 2.4 s | `c4f60fd6…` PASSED, 7 of 7 (hidden 4 of 4), 2.5 s | 03:38:07Z | `af2c3b3e…` |
| Second | `5cbcdbe0…` FAILED, 2 of 7 (hidden 0 of 4), 2.5 s | `dbfc4fdb…` PASSED, 7 of 7 (hidden 4 of 4), 2.4 s | 03:40:29Z | `cce9a806…` |

Both runs: partly comparable (the help differed), the comparison read the same on the phone (412 ×
839) word for word, version 2 read both submissions by id, "You checked this before time ran out."
with the check's time on both devices, and neither canary in the API's log. The step's 12 tests (this
journey, the engineer's journey, its branches and its phone journey, each twice) took 5.7 minutes.

## A second problem on a phone

Volume 17, prompt 10. The engineer's other journeys use Two Sum, and a requirement's compared code
had been checked at phone width once by hand, not by a committed test (Volume 16, rows 9 and 10).
This one is on a phone from start to finish (Chromium emulating a Pixel 7, 412 px wide) and uses a
second problem, **Valid Palindrome** (strings and two pointers; its Java reference passes in CI's
reference-solutions step), in Java, judged by the real judge, with a debugging exercise.

- The journey: `frontend/e2e/engineer-second-problem-mobile.spec.ts` (the mobile project).
- Where it runs: CI's sandbox job, in the step that already runs the engineer's specs twice on fresh
  accounts with the real judge (`E2E_JUDGE=1`, `--repeat-each=2`), added to that step's list; its
  record is in the step's `[journey-record]` lines and the `engineer-journey-record` artifact. No new
  job, no retries. Without the real judge it skips, saying why; with `E2E_JUDGE=1` but no ready judge
  it stops at its first step with the judge's state.

| # | Step | What it checks |
|---|---|---|
| 1 | The judge is ready | `/capabilities`: code execution on, the judge "ready" |
| 2 | A target whose requirement lists code | "Solid experience with string processing in Java", parsed from the job description, offers "Problem: Valid Palindrome", not practised yet; the link opens its workspace |
| 3 | A failing solution, its failed test shown | The reference with one line changed (letters compared with their case), judged in the sandbox: FAILED; the result names the failed public test, `s = "A man, a plan, a canal: Panama"`, expected true, got false |
| 4 | A passing solution, written plainly | Not the reference: letters and digits kept lower-cased, compared with their reverse (with a canary in a comment); PASSED, compared with the failing one by the one contract |
| 5 | The requirement lists both, compared, in the page's words | Newest first, each as "Passed · 8 of 8 tests passed (hidden 5 of 5)" and "Failed · 6 of 8 tests passed (hidden 4 of 5)", the outcome ("Comparable with the one before") and the line "1 compared with the one before; 1 not compared: the first judged submission of its problem."; the outcome opens the submission's own comparison, whose two lines say the same verdicts and counts word for word, with the contract's explanation |
| 6 | The lesson that prepares the exercise, read | "Fixing code from a failing test", from the exercise's "Learn first", marked as read |
| 7 | The debugging exercise, judged, its conditions shown | "Fix: Sentence Palindrome", repaired in the learner's own words (not the reference's text), PASSED in the sandbox; "Fixed: every test passes"; its page's conditions: "In-app help before this attempt: Hint shown" with "Lesson “Fixing code from a failing test” read" and its time |
| 8 | History lists both kinds, each opening its attempt | Both Valid Palindrome submissions and the exercise, each row linking to its own id; the exercise's and the failing one's rows open those attempts |
| 9 | Nothing typed reached the API's log | The canary typed into the passing solution isn't in it |

Every page in the journey (the target twice, the workspace with its failed result, the passing
submission's page, the lesson, the exercise with its debrief, its submission page and History) is
checked at 412 px and again at 360 px for sideways scrolling.

**What isn't checked from the page, and what is instead.** Ids aren't on the page: the submissions'
ids and the requirement's list order are read by the API too, and History's rows are found by the id
in their links. The verdicts are the judge's, read back by the API exactly as it gave them.

**Found on the way.** The requirement said "8 of 8 tests passed" where the submission's own page
says "8 of 8 tests passed (hidden 5 of 5)". The requirement's submissions now carry `hidden_passed`
and `hidden_total`, read by the same rule as the page (`public_result_view`), and both say their
counts through one formatter (`testsPassedWords`), so they can't drift.

**Negative controls, each caught by this journey with the real judge here:** the requirement's
counts without the hidden tests, as before (step 5: not the page's words); its outcome not opening
the submission's comparison (step 5: the URL); the hidden counts read by another rule than the
page's (step 5); and a debugging exercise's lesson read not recorded as help (step 7: its
conditions).

### Its record

**Before CI** (the development check, not the record): this machine, on 16 November 2026, with the
real judge in gVisor, through the e2e launcher, the sandbox step's five specs twice: 14 passed, this
journey 9 of 9 steps both times. The judge's verdicts as it gave them, the time inside the method,
and from request to verdict:

| Run | Failing | Passing | Exercise |
|---|---|---|---|
| First | FAILED, 6 of 8 (hidden 4 of 5), 1 ms, 3.8 s | PASSED, 8 of 8 (hidden 5 of 5), 1 ms, 4.0 s | PASSED, 10 of 10 (hidden 6 of 6), 1 ms, 3.8 s |
| Second | FAILED, 6 of 8 (hidden 4 of 5), 1 ms, 3.9 s | PASSED, 8 of 8 (hidden 5 of 5), 1 ms, 3.9 s | PASSED, 10 of 10 (hidden 6 of 6), 1 ms, 3.9 s |

Both runs: comparable ("the same problem and tests, judged the same way, with the same in-app
help"), the requirement's words the page's, the exercise's conditions naming the lesson read, no
sideways scroll at 412 or 360 px on any page, and the canary not in the API's log.

**In CI**: pending, the sandbox job of the run on the commit that adds the journey. The next commit
records that run here.

## Limits

- The nurse's path: one career, a registered nurse. The coach-context step is absent for it (above);
  the "Hint shown" assistance label isn't on it (the software engineer's journey has it); the judge
  isn't used.
- The software engineer's path: Two Sum and, on a phone, Valid Palindrome with one debugging
  exercise (Volume 17, prompt 10); Java only. (Coding submissions are compared
  since Volume 14, prompt 1, and listed under the coding interview's improvement and the requirement
  since prompt 2; a record made before those says "not compared" and "no practice linked".)
- The journey links the follow-up and the accepted improvement only by order. Since Volume 13, prompt 4, a
  follow-up to the improvement's question is listed under its Related practice (docs/ACCEPTED_ACTIONS.md);
  the recorded journey above predates that and doesn't check it.
- The practice packet can't hold accepted improvements, so the final material is the interview-day
  kit.
- Phone size is Chromium emulating a Pixel 7, not a real phone; no screen reader, Safari or Firefox.
- Two devices and a restore: one account, one restore of one file into the same account (a restore
  into another account is `e2e/restore.spec.ts`); the two contexts share one browser process, so it
  proves the account and the server, not two machines' networks.
- The e2e server logs warnings only; traces are checked by the backend test, not in the browser run.
- It proves this integration path on this candidate, not universal correctness or learning effect.
