# One connected preparation journey

One real path through the app, from a target requirement to the material a learner takes into an
interview, checked end to end in a browser against the real API (Volume 12, prompt 10). It proves
the path it exercises on the candidate it ran on: not that everything else works, and not that
practising this way helps anyone learn.

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

Filled in from a run on a committed candidate; see the commit after the one that added this file.

## Limits

- One path, one career: a registered nurse. The coach-context step is absent for it (above); the
  "Hint shown" assistance label isn't on it; the judge isn't used.
- The follow-up isn't linked to the accepted improvement (they're separate features); the journey
  links them only by order.
- The practice packet can't hold accepted improvements, so the final material is the interview-day
  kit.
- Phone size is Chromium emulating a Pixel 7, not a real phone; no screen reader, Safari or Firefox.
- The e2e server logs warnings only; traces are checked by the backend test, not in the browser run.
- It proves this integration path on this candidate, not universal correctness or learning effect.
