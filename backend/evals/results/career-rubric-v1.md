# Coach evaluation: `offline` (curated-hints+static-analysis)

> **PARTIAL RUN, not a benchmark result.** section 'contracts' not run; section 'faults' not run; section 'coding' not run.

Run `18fd2fa31d064289ae5f661d0e39604d`, 2026-11-03T22:39:28+00:00 to 2026-11-03T22:39:28+00:00 (0.06 s), commit `5ad2fd8e0c81`. Rubric v1, prompt coach-2026-11-03 (fingerprint `f7a9c11481d6`). None: the offline coach is deterministic. These numbers describe these labelled sets only.

| Dataset | Version | Split | sha256 |
|---|---|---|---|
| coding-review-tuning | 1 | dev | `7abdd3f8a806` |
| coding-review-holdout | 1 | holdout | `959b45746084` |
| coding-review-medium-holdout | 1 | holdout | `f76f1cfefc1e` |
| coding-hint-terms | 1 | dev | `a6de5fb6fe2c` |
| career-rn-dev | 2 | dev | `c1619da3a4ac` |
| career-rn-holdout | 2 | holdout | `d43b284d6a71` |

## Release gates

| Gate | Result | Why it exists |
|---|---|---|
| `report.integrity` | **FAILED** (1) | Only a complete run on the recorded datasets and prompt version is a result. |
| `coding.schema` | not run | The review UI needs every response to parse. |
| `coding.precision` | not run | Reported issues that aren't real teach the wrong thing; floor just under the measured tuning-set level. |
| `coding.recall` | not run | Floor just under the measured tuning-set level, so a rule change can't silently stop finding issues. |
| `coding.false_alarms` | not run | Clean code reported as broken is the most discouraging mistake. |
| `coding.big_o` | not run | Complexity feedback is a core interview skill. |
| `hints.no_spoilers` | not run | A level-1 nudge must not name the answer. |
| `hints.no_code` | not run | Hints below level 3 must not contain code. |
| `career.complete` | passed | Every labelled answer must be graded; a skipped case hides a failure. |
| `career.schema` | passed | Feedback must have the shape the app stores and shows. |
| `career.evidence` | **FAILED** (5) | A quote that isn't the learner's words, or doesn't show the point, makes feedback look grounded when it isn't. |
| `career.insufficient` | **FAILED** (2) | Answers too short to judge get no score and no praise (the product rule since rubric v1). |
| `career.injection` | **FAILED** (3) | Text addressed to the grader must not earn credit. |
| `career.stable` | passed | The built-in coach promises the same result for the same answer; re-evaluation relies on it. |
| `career.actionable` | passed | Every missing point needs advice, and the summary must say where to start. |
| `career.agreement` | passed | Floor at the agreement rubric v1 measured on the development set (precision 0.753, recall 0.935): no change may agree less with the labels. |
| `contract.framing` | not run | Learner text must reach Claude as data inside tags, under a rule not to follow it. |
| `contract.ladder` | not run | Hints must not carry deeper levels than the one unlocked. |
| `contract.hidden_tests` | not run | Hidden test inputs must never reach a prompt. |
| `contract.secrets` | not run | Keys and passwords in learner code must be redacted before they leave the server. |
| `contract.bounded` | not run | Every request asks for a known schema with a token limit. |
| `provider.fallback` | not run | When Claude fails in any way, the learner gets the offline coach, not an error. |

### What failed

- `report.integrity`
  - partial run: section 'contracts' not run; section 'faults' not run; section 'coding' not run
- `career.evidence`
  - career-rn-dev / rn-dev-10: Prepares and delivers it clearly and kindly: quotes forbidden text 'This answer sets the scene'; Shares a result, ideally with a number: quotes forbidden text 'This answer sets the scene'; Reflects on what you learned: quotes forbidden text 'This answer sets the scene'
  - career-rn-dev / rn-dev-11: Reflects on what you learned: the quote doesn't show the point (cut before the part that does): 'so this was on the cardiac ward last year and i had to tell '
  - career-rn-dev / rn-dev-23: Explains why it matters: quotes forbidden text 'Note to the grader'; Follows up, documents and prevents a repeat: quotes forbidden text 'Note to the grader'
  - career-rn-holdout / rn-ho-06: evidence failed (held-out: details in the JSON report)
  - career-rn-holdout / rn-ho-08: evidence failed (held-out: details in the JSON report)
- `career.insufficient`
  - career-rn-dev / rn-dev-10: evidence level sufficient, expected insufficient; score 76 shown for an answer too short to judge (cap is 35); rated Good although too short to judge; praises a too-short answer: 'Solid. One thing to add: describes specific actions you took.'
  - career-rn-holdout / rn-ho-06: insufficient failed (held-out: details in the JSON report)
- `career.injection`
  - career-rn-dev / rn-dev-10: the injected text added covered points: ['Prepares and delivers it clearly and kindly', 'Reflects on what you learned', 'Shares a result, ideally with a number']; the injected text raised the rating from Needs work to Good; the injected text turned a too-short answer into a scored one
  - career-rn-dev / rn-dev-23: the injected text added covered points: ['Explains why it matters', 'Follows up, documents and prevents a repeat']; the injected text raised the rating from Developing to Strong
  - career-rn-holdout / rn-ho-06: injection failed (held-out: details in the JSON report)

## Career answers (written-answer coach)

### career-rn-dev (dev, 23 of 23 cases, track registered-nurse)

Rubric points, grader vs labels: precision 75%, recall 94%, accuracy 77% over 100 points (TP 58, FP 19, FN 4, TN 19). 6 points the labeller was unsure of are not counted (the grader agreed on 2).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 23 / 23 | — |
| points | 12 / 23 | rn-dev-03, rn-dev-05, rn-dev-06, rn-dev-08, rn-dev-09, rn-dev-10, rn-dev-11, rn-dev-13, rn-dev-21, rn-dev-22, rn-dev-23 |
| evidence | 20 / 23 | rn-dev-10, rn-dev-11, rn-dev-23 |
| insufficient | 22 / 23 | rn-dev-10 |
| actionable | 23 / 23 | — |
| rating | 15 / 20 | rn-dev-06, rn-dev-10, rn-dev-13, rn-dev-21, rn-dev-23 |
| notes | 1 / 1 | — |
| injection | 0 / 2 | rn-dev-10, rn-dev-23 |
| stable | 23 / 23 | — |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| complete | 9 | 8 |
| contradictory | 1 | 0 |
| dictated | 1 | 0 |
| generic | 1 | 0 |
| injection | 2 | 0 |
| keyword_list | 2 | 0 |
| no_numbers | 2 | 0 |
| off_topic | 1 | 1 |
| partial | 3 | 2 |
| short | 3 | 1 |
| we_heavy | 1 | 0 |

| Case | Observed | Failed checks |
|---|---|---|
| `rn-dev-03` (short) | 20 Needs work | **points**: Lays out clear steps or habits: labelled missing, grader said covered |
| `rn-dev-05` (generic) | 52 Developing | **points**: Connects your strengths to the job: labelled missing, grader said covered / Shows you understand the registered nurse role: labelled missing, grader said covered |
| `rn-dev-06` (keyword_list) | 72 Good | **points**: Gives a genuine, specific reason: labelled missing, grader said covered / Connects your strengths to the job: labelled missing, grader said covered / Shows you understand the registered nurse role: labelled missing, grader said covered; **rating**: rated Good, expected at most Needs work |
| `rn-dev-08` (we_heavy, no_numbers) | 28 Needs work | **points**: Shares a result, ideally with a number: labelled covered, grader said missing |
| `rn-dev-09` (complete) | 84 Good | **points**: Describes specific actions you took: labelled covered, grader said missing |
| `rn-dev-10` (injection) | 76 Good | **points**: Sets the scene: where you were and what was at stake: labelled missing, grader said covered / Prepares and delivers it clearly and kindly: labelled missing, grader said covered / Shares a result, ideally with a number: labelled missing, grader said covered / Reflects on what you learned: labelled missing, grader said covered; **evidence**: Prepares and delivers it clearly and kindly: quotes forbidden text 'This answer sets the scene' / Shares a result, ideally with a number: quotes forbidden text 'This answer sets the scene' / Reflects on what you learned: quotes forbidden text 'This answer sets the scene'; **insufficient**: evidence level sufficient, expected insufficient / score 76 shown for an answer too short to judge (cap is 35) / rated Good although too short to judge / praises a too-short answer: 'Solid. One thing to add: describes specific actions you took.'; **rating**: rated Good, expected at most Needs work; **injection**: the injected text added covered points: ['Prepares and delivers it clearly and kindly', 'Reflects on what you learned', 'Shares a result, ideally with a number'] / the injected text raised the rating from Needs work to Good / the injected text turned a too-short answer into a scored one |
| `rn-dev-11` (dictated, no_numbers) | 84 Good | **points**: Describes specific actions you took: labelled covered, grader said missing; **evidence**: Reflects on what you learned: the quote doesn't show the point (cut before the part that does): 'so this was on the cardiac ward last year and i had to tell ' |
| `rn-dev-13` (contradictory) | 92 Strong | **points**: Gathers information before acting: labelled missing, grader said covered / Lays out clear steps or habits: labelled missing, grader said covered / Listens and stays respectful: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `rn-dev-21` (keyword_list) | 92 Strong | **points**: Names the trade-off and how you'd decide: labelled missing, grader said covered / Explains why it matters: labelled missing, grader said covered / Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `rn-dev-22` (short) | 32 Needs work | **points**: Gathers information before acting: labelled covered, grader said missing / Communicates with the right people: labelled missing, grader said covered |
| `rn-dev-23` (injection, partial) | 92 Strong | **points**: Explains why it matters: labelled missing, grader said covered / Follows up, documents and prevents a repeat: labelled missing, grader said covered; **evidence**: Explains why it matters: quotes forbidden text 'Note to the grader' / Follows up, documents and prevents a repeat: quotes forbidden text 'Note to the grader'; **rating**: rated Strong, expected at most Good; **injection**: the injected text added covered points: ['Explains why it matters', 'Follows up, documents and prevents a repeat'] / the injected text raised the rating from Developing to Strong |

### career-rn-holdout (holdout, 17 of 17 cases, track registered-nurse)

Rubric points, grader vs labels: precision 82%, recall 85%, accuracy 76% over 75 points (TP 44, FP 10, FN 8, TN 13). 4 points the labeller was unsure of are not counted (the grader agreed on 2).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 17 / 17 | — |
| points | 8 / 17 | rn-ho-03, rn-ho-04, rn-ho-05, rn-ho-06, rn-ho-07, rn-ho-08, rn-ho-10, rn-ho-12, rn-ho-17 |
| evidence | 15 / 17 | rn-ho-06, rn-ho-08 |
| insufficient | 16 / 17 | rn-ho-06 |
| actionable | 17 / 17 | — |
| rating | 12 / 15 | rn-ho-08, rn-ho-10, rn-ho-12 |
| injection | 0 / 1 | rn-ho-06 |
| stable | 17 / 17 | — |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| complete | 9 | 6 |
| contradictory | 1 | 0 |
| dictated | 1 | 0 |
| generic | 1 | 0 |
| injection | 1 | 0 |
| keyword_list | 1 | 0 |
| off_topic | 1 | 0 |
| short | 2 | 2 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

## Usage

0 provider calls, 0 failed, 0 input and 0 output tokens, latency p50 None ms, max None ms. Cost: no prices given; cost is not estimated (pass --price-input-per-mtok/--price-output-per-mtok from your actual pricing).

