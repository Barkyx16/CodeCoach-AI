# What help was part of an attempt

Each coding attempt and each career written answer says which in-app help was shown before it
(Volume 12, prompt 3). It's worked out when read from records the app already keeps; there's no
separate help log. An answer given in an interview round records it when the answer is saved, with
the round's format (Volume 13, prompt 3; below). Drill attempts, scenario runs and whiteboard
attempts say it too, from 15 Nov 2026 (Volume 14, prompt 4; below), and so do code-review
exercises, sample-answer comparisons and work samples (Volume 15, prompt 3; below), debugging
exercises and coding interviews (Volume 16, prompt 2; below). Every format that's a practice attempt
now says what in-app help came before it.

## Every format, and what it records

| Format | The help it can show | Recorded from | Worked out from |
|---|---|---|---|
| Coding submissions (and runs) | Hints for the problem (levels 1-3: "Hint shown"; level 4: "Solution revealed") | 14 Nov 2026 | the saved hints, by the problem's version |
| Career written answers | Learn lessons that prepare the question | 14 Nov 2026 | lesson reads, by the question's version |
| Interview-round answers | The same lessons, plus the round's format (never help) | 15 Nov 2026 | stored with the answer when it's saved |
| Communication drills | Learn lessons that prepare the drill (the STAR lesson prepares "Answer with a concrete example") | 15 Nov 2026 | lesson reads, by the drill's version (its rubric's) |
| Branching scenarios | Learn lessons that prepare the scenario (the prioritizing and SBAR lessons prepare "Two call lights at once") | 15 Nov 2026 | lesson reads, by the scenario's version; assessed runs and "try another approach" explorations counted apart |
| Whiteboards | None: no lesson prepares a system-design prompt, and the prompt's points are shown to everyone with it | 15 Nov 2026 | (nothing to find: "No in-app help recorded") |
| Code-review exercises | The exercise's authored review, shown before the review was written ("Solution revealed"); Learn lessons that prepare the exercise (none yet) | 15 Nov 2026 (the authored review shown first: always kept) | the attempt's own `after_reveal`; lesson reads, by the exercise's version |
| Sample-answer comparisons | The comparison's explanation, opened before the reading was sent ("Solution revealed"); Learn lessons that prepare it (the STAR lesson prepares "Specific evidence or general claims?") | 15 Nov 2026 (the explanation opened first: always kept) | the attempt's own `revealed_early`, as the page reported it when sending; lesson reads, by the comparison's version |
| Work samples | None: no lesson prepares a brief yet, and each section's hint is shown to everyone with the brief | 15 Nov 2026 | (nothing to find: "No in-app help recorded") |
| Debugging exercises | Hints for the exercise (as for any coding problem); its explanation and repair, opened before the attempt ("Solution revealed"); Learn lessons that prepare it (“Fixing code from a failing test” prepares all three, since Volume 17, prompt 5) | hints 14 Nov 2026; the explanation opened, 16 Nov 2026 | the saved hints; `lab_reveals`, by the exercise's version; lesson reads (`debug:<slug>`) |
| Coding interviews | Hints for the interview's problem, before or during it; plus its format (never help): the time limit, how it ended, each message and the feedback checked before it left CodeCoach | hints 14 Nov 2026; checked messages 16 Nov 2026 | the saved hints, by the problem's version when it started; what the interview stores |

Offer comparisons and story help aren't practice attempts, so they have no conditions (below).

## The labels

Exactly these, as the server gives them:

| Label | Means |
|---|---|
| **Hint shown** | A hint (levels 1-3) for this coding problem, or a Learn lesson that prepares for this written question, was shown since the previous attempt |
| **Solution revealed** | The level 4 hint for this coding problem was shown since the previous attempt (the app warns that it explains the full solution); or, for a code-review exercise or a sample-answer comparison, its own answer (the authored review, the explanation) was shown before the attempt; or a debugging exercise's explanation and repair were opened since the previous attempt |
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

- A coding attempt's page (History → a submission): "In-app help", with each hint and its time; a
  debugging exercise's attempt the same, with the explanation opened.
- A coding interview's review: "In-app help before this interview", with each hint, its time and
  whether it came before or during the interview, then how it was given and what was checked.
- A written answer: in "Your past answers" and beside its feedback.
- History: each code submission, written answer and coding interview row, asked for in one bounded
  request for the rows on screen (`POST /api/v1/me/attempt-conditions`, up to 50 ids of each kind;
  another account's ids, unknown ids, a career interview and one still running are simply absent),
  so the list itself costs no more to load.
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

## Code reviews, sample-answer comparisons and work samples

Volume 15, prompt 3. Two kinds of help, by the rule every format uses:

- **The format's own answer, shown first.** A code-review exercise sends its authored review only
  when asked (or after a review is sent); a review written after that says **Solution revealed**
  ("The authored review was shown before this was written"). A comparison's explanation can be
  opened before the reading is sent, after a confirmation; a reading sent after that says
  **Solution revealed** ("The explanation was opened before this was sent"). Both attempts have
  always stored this (`after_reveal`, `revealed_early`), so it's shown for every attempt, older ones
  too. Its time is the attempt's: the reveal's own time isn't kept. Unlike a hint, the authored
  review stays seen: every later review of the same exercise says so, as it always has.
- **A Learn lesson that prepares it**, read before the attempt and since the previous one, at the
  attempt's version: **Hint shown**, for the first attempt after the read only. The STAR lesson
  prepares "Specific evidence or general claims?" (reviewed: both teach showing what you did rather
  than claiming a quality); no lesson prepares a code-review exercise or a work-sample brief yet. A
  work sample's section hints are shown to everyone with the brief, like a question's tips, so
  they're not help.

Attempts from before 15 Nov 2026 with nothing found are **Not recorded** (with the date), never "No
in-app help recorded". Shown under each attempt's result and in its row in the format's list of
your attempts ("In-app help: Solution revealed"); `POST /api/v1/me/attempt-conditions` takes
`code_review_attempt_ids`, `comparison_attempt_ids` and `work_sample_attempt_ids` (50 of each;
another account's are left out); the export gives each attempt its `id` and `conditions`. Feedback,
counts and the authored review are exactly as before.

Checked by `backend/tests/test_review_formats_conditions.py` (8): the lesson link is real; the
authored review and the explanation shown first, on the attempt and its list row; a lesson read
counts for the first comparison after it only, and not for a different comparison; a work sample has
none to show after every lesson; older attempts are "Not recorded" unless their own flag says more;
another account's reads never count and its attempts are left out; the export. The code-review,
comparison and work-sample unit tests check the pages. Negative controls (each caught): each reveal
ignored, every comparison marked revealed, the lesson link removed, another account's attempts
returned, the export without conditions; on the pages, a review's, a reading's or a work-sample row's
conditions left out.

## Not observed

- Help outside the app: other sites, books, people, AI tools. It's unknown and never inferred.
- Accessibility settings and how an answer was entered: dictation, captions, screen readers,
  text size, contrast and reduced motion are never inputs here, never help, and never reduce how an
  attempt counts. The answer request doesn't carry them.
- The tips under a question, which everyone sees with it, and earlier feedback.
- A debugging exercise's explanation opened before 16 Nov 2026: it wasn't recorded then, and an
  attempt from before says so. Read without signing in, it's recorded nowhere (there's no account
  to record it against). One left open on the page across attempts counts for the attempt after it
  was opened only.
- Which coding-interview messages were checked before 16 Nov 2026.

## Debugging exercises and coding interviews

Volume 16, prompt 2. Both read by the one function each (`Conditions.for_submissions`,
`Conditions.for_interviews`), used by the submission page, the interview's review, History and the
export, so they can't disagree.

**A debugging exercise** is a submission, so its hints are found as for any coding problem. Opening
its explanation and repair ("Stuck? Show the explanation", or "Why it happened" after a passing fix)
is recorded when signed in: the page asks with `POST /problems/{slug}/lab/explanation`, which keeps
the exercise, its version then and the time (`lab_reveals`, migration `b2e6d4a8c157`, owner-only
under row-level security, in the export and the data summary, deleted with the account). The next
attempt at that version says "Solution revealed: The exercise's explanation and a correct repair
(version 1)", with the time; an attempt after that, unless it's opened again, doesn't. Opening it
again before the next attempt is the same opening (no second row). An opening at another version of
the exercise doesn't count. A Learn lesson that prepares an exercise (`prepares: "debug:<slug>"`)
counts by the lesson rule: since Volume 17, prompt 5, **Fixing code from a failing test**
(`se-failing-test`, version 1, author-reviewed) prepares all three exercises, is offered under
"Learn first" on each, and its read is help for the first attempt after it (reading it after an
attempt is the next one's). The content gate refuses a `prepares` link to something that doesn't
exist, and a test checks the lesson gives none of the exercises' answers away. An attempt from before 16 Nov 2026 says "Opening the
exercise's explanation and repair wasn't recorded before 16 Nov 2026, so whether it was opened before
this attempt isn't known", beside any hints it did record, and with nothing else found it's "Not
recorded".

**A coding interview** lists the hints for its problem shown after the previous coding interview of
that problem ended and before this one ended, at the problem's version when it started (recorded at
the start from 16 Nov 2026; before, known only if the problem never had another version). Each is
in the hint panel's words, with the problem and when: "Level 2 hint, “Concept”, on “Two Sum”, during
the interview". Since Volume 17, prompt 4, the interview room has its own **Hints** panel (under
the editor): the problem's ladder, one level at a time, each checked first (what the coach reads: the
code last sent) and asked for through `POST /interviews/{id}/hint`, the same coach, ladder and budget
as the workspace. The interview records each (`hints`: level, its name, when it was shown, after how
many messages); asking for a level it already has gives that hint again with no second request; the
panel is closed once the interview is over or its time is up, and a career interview has none. Hints
asked for in the workspace still count, said "before the interview" or "during the interview" by
when. A submission of the problem counts the same hints for itself (a submission and an
interview are counted apart, like a Run and a Submit). Its format is read from what it stores, never
help: "A 15-minute coding interview, finished; 1 of 2 messages checked before sending; the
feedback's material checked before it was scored." with each check and its time. A message counts as
checked when it was sent with its preview's fingerprint (`interview_turns.meta.checked`, from 16 Nov
2026; before, "whether messages were checked before they were sent wasn't recorded then"); the
feedback, from `plan.feedback_read` (docs/COACH_CONTEXT.md). Nothing is said while it runs. A career
interview isn't described as a whole: each answer has its own (interview rounds, above).

## What isn't a practice attempt

- **Offer comparisons** (docs/OFFER_COMPARISON.md) organise the terms of real or fictional job offers
  the learner enters. There's nothing to attempt and no result to qualify, so there's no record of
  help before one, and none is made up.
- **Story help** (docs/STORIES.md, "Writing help") is the story bank's rule-based check of a story
  being written. A story is the learner's own material, not an attempt at an exercise; it isn't
  scored, so nothing qualifies it. A story used in a written answer or a round is part of that
  answer, whose conditions are its own.

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

## Checked by tests (debugging exercises and coding interviews)

`backend/tests/test_debug_interview_conditions.py` (SQLite and PostgreSQL): a debugging exercise after
a hint says so and the next says none; opening the explanation is "Solution revealed" for the next
attempt only, asking again is the same opening, and one opened after an attempt is the next one's;
the plain read records nothing and needs no account, the recording one does; an opening at another
version doesn't count; an attempt from before says the opening wasn't recorded, beside its hints;
another account's openings and hints never count; a coding interview with two hints lists both in
order, before and during, and the next interview of the problem starts afresh while the next
submission counts its own; which messages and the feedback were checked; an interview ended early,
unchecked; an interview from before says its checks weren't recorded; nothing while one runs; the
export and History carry both records by id and match the pages; a career interview isn't described
as a coding one; and on PostgreSQL, row-level security keeps both records to this account's rows even
with the hint and opening queries' owner filters removed. `frontend/src/test/integration/debugInterviewConditions.test.tsx`
covers the review, History's row and an older attempt's note; `debuggingLab.test.tsx` that opening it
signed in is recorded and signed out isn't. Negative controls (each caught): openings ignored, counted
for every later attempt, across versions, recorded twice, from before not said, another account's
counted; an interview's hints not bounded by the previous interview, before and during swapped, a
checked message not recorded, the feedback's check not listed, an old interview's checks claimed, the
export or the bulk route without interviews, a career interview or a running one described; on the
pages, the format line, the checks, the older attempt's note, the review's section, History's request
and row left out, the lab read without recording, and a record promised when signed out.
