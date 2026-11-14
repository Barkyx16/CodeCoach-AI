# What help was part of an attempt

Each coding attempt and each career written answer says which in-app help was shown before it
(Volume 12, prompt 3). It's worked out when read from records the app already keeps; there's no
separate help log.

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

## Not observed

- Help outside the app: other sites, books, people, AI tools. It's unknown and never inferred.
- Accessibility settings and how an answer was entered: dictation, captions, screen readers,
  text size, contrast and reduced motion are never inputs here, never help, and never reduce how an
  attempt counts. The answer request doesn't carry them.
- The tips under a question, which everyone sees with it, and earlier feedback.
- A debugging exercise's explanation and reference repair: asking for it isn't recorded.

## Not covered yet

Coding attempts and career written answers only. Next, each with what it would use: whiteboard
attempts, code-review exercises (`after_reveal` is already kept), sample-answer comparisons
(`revealed_early`), work samples, drills, scenarios, interview rounds and the coding interviewer.
