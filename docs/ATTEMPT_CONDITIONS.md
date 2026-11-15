# What help was part of an attempt

Each coding attempt and each career written answer says which in-app help was shown before it
(Volume 12, prompt 3). It's worked out when read from records the app already keeps; there's no
separate help log. An answer given in an interview round records it when the answer is saved, with
the round's format (Volume 13, prompt 3; below). Drill attempts, scenario runs and whiteboard
attempts say it too, from 15 Nov 2026 (Volume 14, prompt 4; below).

## Every format, and what it records

| Format | The help it can show | Recorded from | Worked out from |
|---|---|---|---|
| Coding submissions (and runs) | Hints for the problem (levels 1-3: "Hint shown"; level 4: "Solution revealed") | 14 Nov 2026 | the saved hints, by the problem's version |
| Career written answers | Learn lessons that prepare the question | 14 Nov 2026 | lesson reads, by the question's version |
| Interview-round answers | The same lessons, plus the round's format (never help) | 15 Nov 2026 | stored with the answer when it's saved |
| Communication drills | Learn lessons that prepare the drill (the STAR lesson prepares "Answer with a concrete example") | 15 Nov 2026 | lesson reads, by the drill's version (its rubric's) |
| Branching scenarios | Learn lessons that prepare the scenario (the prioritizing and SBAR lessons prepare "Two call lights at once") | 15 Nov 2026 | lesson reads, by the scenario's version; assessed runs and "try another approach" explorations counted apart |
| Whiteboards | None: no lesson prepares a system-design prompt, and the prompt's points are shown to everyone with it | 15 Nov 2026 | (nothing to find: "No in-app help recorded") |

Code-review exercises, sample-answer comparisons, work samples, debugging exercises, offer
comparisons and story help don't record conditions yet (below).

## The labels

Exactly these, as the server gives them:

| Label | Means |
|---|---|
| **Hint shown** | A hint (levels 1-3) for this coding problem, or a Learn lesson that prepares for this written question, was shown since the previous attempt |
| **Solution revealed** | The level 4 hint for this coding problem was shown since the previous attempt: the app warns that it explains the full solution |
| **No in-app help recorded** | Nothing above was recorded for this attempt |
| **Not recorded** | An attempt from before recording began (14 Nov 2026) with nothing to go on, or one whose earlier help can't be matched to a version. Never "none" |

An attempt can have both of the first two. They're never "independent", "unassisted" or
"verified", and they change no score, verdict, count or progress: the judge's verdicts and the
rubric results are exactly as before.

## What's matched, and how

- **Same question and version.** A hint counts for the coding problem it was asked for and the
  problem's version (its tests' version) at the time; the attempt records its version too
  (migration `e5c9a2b7d103` adds `content_version` to hints and submissions). A lesson counts for
  the written questions it prepares for, at the question's version when it was read (from the
  question's published corrections). Help on another question, or for an earlier version of this
  one, doesn't mark it.
- **The next attempt only.** Help belongs to the first attempt after it (in the same mode: a Run
  and a Submit are counted apart). An attempt shows the help since the previous one, so the next
  attempt made without help shows none, and help opened after an attempt never changes it.
- **Shown, not asked.** A hint request that failed (locked, over the daily budget, refused) saved
  nothing and isn't shown. A hint's time is when it actually arrived, even if the learner had left.
- **Once.** A hint sent again after a lost reply is the same saved hint (its request key), so it's
  one piece of help.
- **Older records.** Hints saved before versions were recorded match only when the problem has
  never had another version; otherwise the attempt says "Not recorded".

## Where it shows

- A coding attempt's page (History → a submission): "In-app help", with each hint and its time.
- A written answer: in "Your past answers" and beside its feedback.
- History: each code submission and written answer row, asked for in one bounded request for the
  rows on screen (`POST /api/v1/me/attempt-conditions`, up to 50 ids of each kind; another
  account's ids and unknown ids are simply absent), so the list itself costs no more to load.
- The API: `conditions` on `GET /submissions/{id}`, `GET /me/submissions`, and every answer
  response; the data export adds it to submissions and written answers (and each hint's problem
  version). Private to the owner and deleted with the account, like the attempts.

## Interview rounds

A round's answer is saved with its conditions (`interview_turns.meta.conditions`, no new column):
the help worked out at that moment, by the same rules as a written answer (a Learn lesson that
prepares that question, read since the previous answer to it), and the round's time limit. They're
read back as stored, so nothing that happens later (a lesson read afterwards, an earlier answer
deleted) can change them. With them, each answer carries the round's format, which is never help:

| | Recorded from |
|---|---|
| Timed | The round's time limit ("A 15-minute timed mock interview") |
| The interviewer's follow-up | Asked and answered, or asked and skipped, recorded when it happened. A follow-up isn't help |
| Ended early | The round was ended or ran out of time before every question was reached |

- **Where it shows**: the round's results (the replay) give one line per answer, "In-app help before
  this answer: Hint shown", with the format under it; the question page's past answers show the same
  conditions with "How it was given: …"; the retry comparison names the condition that differed
  (docs/COMPARING_ATTEMPTS.md). The API: `conditions.round` on every answer response.
- **Before recording**: a round answer saved before this (15 Nov 2026) is **Not recorded**, never "No
  in-app help recorded", and nothing is worked out for it later; its format, which the round itself
  kept, is still shown.
- **Never reached**: a question an ended-early round didn't reach says "The round ended before this
  question: nothing was recorded for it."
- Another account's lesson reads never count; conditions change no score, verdict or count.

## Drills, scenarios and whiteboards

The only in-app help these formats have is a Learn lesson that prepares them: a lesson lists what
it prepares (`prepares` in `app/learn/units.py`, checked by a test to name things that exist), and
each read of it records, from 15 Nov 2026, the version of each thing it prepares at that moment
(`learn_events.detail`, no new column). An attempt's help is then worked out when read, by the rule
every format uses:

- **The first attempt after it.** A lesson read counts for the first attempt at what it prepares made
  after it (a scenario's assessed runs and its explorations each count their own), so the next
  attempt shows none. A lesson is recorded as read once per lesson version, as Learn always has.
- **The same version.** A read recorded at another version of the drill or scenario doesn't count. A
  read from before versions were recorded counts only for something that has never had another
  version; otherwise the attempt is **Not recorded**.
- **Before recording.** An attempt made before 15 Nov 2026 with nothing found is **Not recorded**
  (with the date), never "No in-app help recorded".
- **Where it shows**: each attempt's page (a drill's feedback, a scenario run's header, a whiteboard
  attempt's feedback) and its row in that format's list of your attempts ("In-app help: Hint shown");
  `POST /api/v1/me/attempt-conditions` takes `drill_attempt_ids`, `scenario_attempt_ids` and
  `whiteboard_attempt_ids` (50 of each; another account's are left out); the export gives each drill
  attempt, scenario run and whiteboard attempt its `id` and `conditions`.
- **Comparisons read them.** A drill repeat's comparison with the attempt before it adds "The in-app
  help differed: before the earlier one, hint shown; before this one, none recorded." (or that one
  of them wasn't recorded), in the comparison contract's words; nothing else in it changes.
- Feedback, outcomes and debriefs are exactly as before; the conditions change no score or verdict.

## Not observed

- Help outside the app: other sites, books, people, AI tools. It's unknown and never inferred.
- Accessibility settings and how an answer was entered: dictation, captions, screen readers,
  text size, contrast and reduced motion are never inputs here, never help, and never reduce how an
  attempt counts. The answer request doesn't carry them.
- The tips under a question, which everyone sees with it, and earlier feedback.
- A debugging exercise's explanation and reference repair: asking for it isn't recorded.

## Not covered yet

Covered: coding attempts, career written answers, interview rounds, drills, scenarios and
whiteboards. Next, each with what it would use: code-review exercises (`after_reveal` is already
kept), sample-answer comparisons (`revealed_early`), work samples and the coding interviewer.

## Checked by tests (interview rounds)

`backend/tests/test_round_conditions.py`: a lesson read before a round marks only the answer it
prepares; the recorded conditions survive a later read and a deleted earlier answer; an old round is
"Not recorded" with its format; another account's reads never count; a follow-up is part of the format;
an ended-early round says so and records nothing for what it didn't reach; the retry comparison names
the condition that differed and the verdict and score stay. `frontend/src/test/integration/roundConditions.test.tsx`
covers the results page. Negative controls (each caught): worked out again when read; not recorded when
saved; an old round's help guessed; another account's reads counted; the follow-up left out of the
format; an unreached question not said; the differing condition not named; and on the page, no
conditions, no format line, no unreached note, "Not recorded" without its date.

## Checked by tests (drills, scenarios and whiteboards)

`backend/tests/test_practice_conditions.py` (SQLite and PostgreSQL): every lesson link names something
that exists; a lesson read before a scenario run marks that run only, and its list row says the same;
an exploration counts its own; a read recorded at another version doesn't count, and one from before
versions were recorded is "Not recorded" on a revised scenario; attempts from before 15 Nov 2026 are
"Not recorded" for all three formats; a drill's lesson shows once and its comparison names the help
that differed; a whiteboard attempt has none to show even after every lesson; another account's reads
and attempts never count; the export carries each attempt's conditions by id; a read records what the
lesson prepares. `frontend/src/test/integration/practiceConditions.test.tsx` covers the pages and
`frontend/e2e/practice-conditions.spec.ts` a drill and a scenario against the real API. Negative
controls (each caught): help counted for every later attempt (backend and in the browser), across
content versions, a read of unknown version taken as help, modes counted together, the date ignored, a
read recording no version, the drill comparison ignoring the help; on the pages, a drill's, scenario
run's or whiteboard attempt's conditions or a row's left out.
