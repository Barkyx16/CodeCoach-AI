# Coach evaluation: `offline` (curated-hints+static-analysis)

Run `566ac17875e24d21b010d9e8f5723bdb`, 2026-11-03T22:39:22+00:00 to 2026-11-03T22:39:25+00:00 (3.01 s), commit `5ad2fd8e0c81`. Rubric v2, prompt coach-2026-11-03 (fingerprint `f7a9c11481d6`). None: the offline coach is deterministic. These numbers describe these labelled sets only.

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
| `report.integrity` | passed | Only a complete run on the recorded datasets and prompt version is a result. |
| `coding.schema` | passed | The review UI needs every response to parse. |
| `coding.precision` | passed | Reported issues that aren't real teach the wrong thing; floor just under the measured tuning-set level. |
| `coding.recall` | passed | Floor just under the measured tuning-set level, so a rule change can't silently stop finding issues. |
| `coding.false_alarms` | passed | Clean code reported as broken is the most discouraging mistake. |
| `coding.big_o` | passed | Complexity feedback is a core interview skill. |
| `hints.no_spoilers` | passed | A level-1 nudge must not name the answer. |
| `hints.no_code` | passed | Hints below level 3 must not contain code. |
| `career.complete` | passed | Every labelled answer must be graded; a skipped case hides a failure. |
| `career.schema` | passed | Feedback must have the shape the app stores and shows. |
| `career.evidence` | passed | A quote that isn't the learner's words, or doesn't show the point, makes feedback look grounded when it isn't. |
| `career.insufficient` | passed | Answers too short to judge get no score and no praise (the product rule since rubric v1). |
| `career.injection` | passed | Text addressed to the grader must not earn credit. |
| `career.stable` | passed | The built-in coach promises the same result for the same answer; re-evaluation relies on it. |
| `career.actionable` | passed | Every missing point needs advice, and the summary must say where to start. |
| `career.agreement` | passed | Floor at the agreement rubric v1 measured on the development set (precision 0.753, recall 0.935): no change may agree less with the labels. |
| `contract.framing` | passed | Learner text must reach Claude as data inside tags, under a rule not to follow it. |
| `contract.ladder` | passed | Hints must not carry deeper levels than the one unlocked. |
| `contract.hidden_tests` | passed | Hidden test inputs must never reach a prompt. |
| `contract.secrets` | passed | Keys and passwords in learner code must be redacted before they leave the server. |
| `contract.bounded` | passed | Every request asks for a known schema with a token limit. |
| `provider.fallback` | passed | When Claude fails in any way, the learner gets the offline coach, not an error. |

## Career answers (written-answer coach)

### career-rn-dev (dev, 23 of 23 cases, track registered-nurse)

Rubric points, grader vs labels: precision 81%, recall 94%, accuracy 82% over 100 points (TP 58, FP 14, FN 4, TN 24). 6 points the labeller was unsure of are not counted (the grader agreed on 2).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 23 / 23 | — |
| points | 13 / 23 | rn-dev-03, rn-dev-05, rn-dev-06, rn-dev-08, rn-dev-09, rn-dev-10, rn-dev-11, rn-dev-13, rn-dev-21, rn-dev-22 |
| evidence | 23 / 23 | — |
| insufficient | 23 / 23 | — |
| actionable | 23 / 23 | — |
| rating | 17 / 20 | rn-dev-06, rn-dev-13, rn-dev-21 |
| notes | 1 / 1 | — |
| injection | 2 / 2 | — |
| stable | 23 / 23 | — |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| complete | 9 | 8 |
| contradictory | 1 | 0 |
| dictated | 1 | 0 |
| generic | 1 | 0 |
| injection | 2 | 1 |
| keyword_list | 2 | 0 |
| no_numbers | 2 | 0 |
| off_topic | 1 | 1 |
| partial | 3 | 3 |
| short | 3 | 1 |
| we_heavy | 1 | 0 |

| Case | Observed | Failed checks |
|---|---|---|
| `rn-dev-03` (short) | 20 Needs work | **points**: Lays out clear steps or habits: labelled missing, grader said covered |
| `rn-dev-05` (generic) | 52 Developing | **points**: Connects your strengths to the job: labelled missing, grader said covered / Shows you understand the registered nurse role: labelled missing, grader said covered |
| `rn-dev-06` (keyword_list) | 72 Good | **points**: Gives a genuine, specific reason: labelled missing, grader said covered / Connects your strengths to the job: labelled missing, grader said covered / Shows you understand the registered nurse role: labelled missing, grader said covered; **rating**: rated Good, expected at most Needs work |
| `rn-dev-08` (we_heavy, no_numbers) | 28 Needs work | **points**: Shares a result, ideally with a number: labelled covered, grader said missing |
| `rn-dev-09` (complete) | 84 Good | **points**: Describes specific actions you took: labelled covered, grader said missing |
| `rn-dev-10` (injection) | 16 Needs work | **points**: Sets the scene: where you were and what was at stake: labelled missing, grader said covered |
| `rn-dev-11` (dictated, no_numbers) | 84 Good | **points**: Describes specific actions you took: labelled covered, grader said missing |
| `rn-dev-13` (contradictory) | 92 Strong | **points**: Gathers information before acting: labelled missing, grader said covered / Lays out clear steps or habits: labelled missing, grader said covered / Listens and stays respectful: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `rn-dev-21` (keyword_list) | 92 Strong | **points**: Names the trade-off and how you'd decide: labelled missing, grader said covered / Explains why it matters: labelled missing, grader said covered / Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `rn-dev-22` (short) | 32 Needs work | **points**: Gathers information before acting: labelled covered, grader said missing / Communicates with the right people: labelled missing, grader said covered |

### career-rn-holdout (holdout, 17 of 17 cases, track registered-nurse)

Rubric points, grader vs labels: precision 83%, recall 85%, accuracy 77% over 75 points (TP 44, FP 9, FN 8, TN 14). 4 points the labeller was unsure of are not counted (the grader agreed on 2).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 17 / 17 | — |
| points | 9 / 17 | rn-ho-03, rn-ho-04, rn-ho-05, rn-ho-07, rn-ho-08, rn-ho-10, rn-ho-12, rn-ho-17 |
| evidence | 17 / 17 | — |
| insufficient | 17 / 17 | — |
| actionable | 17 / 17 | — |
| rating | 12 / 15 | rn-ho-08, rn-ho-10, rn-ho-12 |
| injection | 1 / 1 | — |
| stable | 17 / 17 | — |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| complete | 9 | 6 |
| contradictory | 1 | 0 |
| dictated | 1 | 0 |
| generic | 1 | 0 |
| injection | 1 | 1 |
| keyword_list | 1 | 0 |
| off_topic | 1 | 0 |
| short | 2 | 2 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

## Code review and hints: tuning set

38 labelled review samples; hints on 300 problems (spoiler and relevance rates on the 22 with labelled terms; code-leak checks on all).

| Metric | Value |
|---|---|
| Schema validity | 100% |
| Issue detection (micro) precision / recall / F1 | 100% / 60% / 75% |
| False alarms on clean code (medium/high issue on a clean sample) | 0% of 14 |
| Complexity (Big-O) accuracy | 95% |
| Level-1 hint spoiler rate | 0% |
| Level-2 hint relevance | 100% |
| Code in level 1–2 hints | 0% |

## Held-out set (generalisation)

14 samples written after the rules were frozen; never used to tune them.

| Metric | Value |
|---|---|
| Issue detection (micro) precision / recall / F1 | 80% / 50% / 62% |
| False alarms on clean code | 17% of 6 |
| Complexity (Big-O) accuracy | 50% |

| Sample | Expected | Reviewer said | Big-O expected → reported |
|---|---|---|---|
| `ho-max-min-value` | edge-case | — | O(n) → O(n) |
| `ho-reverse-recursive` | complexity | — | O(n^2) → depends on recursion (check for repeated subproblems) |
| `ho-parens-replace` | complexity | — | O(n^2) → O(n) |
| `ho-unique-map-order-bug` | correctness | — | O(n) → O(n) |
| `ho-window-set` | — | complexity | O(n) → O(n^2) |

## Medium held-out set (newer problems)

14 samples written after the rules were frozen; never used to tune them.

| Metric | Value |
|---|---|
| Issue detection (micro) precision / recall / F1 | 100% / 50% / 67% |
| False alarms on clean code | 0% of 4 |
| Complexity (Big-O) accuracy | 86% |

| Sample | Expected | Reviewer said | Big-O expected → reported |
|---|---|---|---|
| `md-product-division` | correctness | — | O(n) → O(n) |
| `md-rotated-strict-loop` | correctness | — | O(log n) → O(log n) |
| `md-coin-greedy` | correctness | — | O(k log k) → O(n log n) |
| `md-decode-no-zero-check` | edge-case | — | O(n) → O(n) |
| `md-kth-sort` | complexity | — | O(n log n) → O(n log n) |

## Issue detection by category (tuning set)

| Category | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| correctness | 100% | 17% | 29% | 2 | 0 | 10 |
| edge-case | 100% | 100% | 100% | 1 | 0 | 0 |
| complexity | 100% | 100% | 100% | 9 | 0 | 0 |
| readability | 100% | 100% | 100% | 1 | 0 | 0 |
| style | 100% | 100% | 100% | 2 | 0 | 0 |

## Disagreements with the labels (tuning set)

| Sample | Expected | Reviewer said | Big-O expected → reported |
|---|---|---|---|
| `two-sum-same-index` | complexity, correctness | complexity | O(n^2) → O(n^2) |
| `max-starts-at-zero` | correctness | — | O(n) → O(n) |
| `reverse-off-by-one` | correctness | — | O(n) → O(n) |
| `palindrome-no-case` | correctness | — | O(n) → O(n) |
| `parens-leftovers` | correctness | — | O(n) → O(n) |
| `parens-counting` | correctness | — | O(n) → O(n) |
| `bsearch-off-by-one` | correctness | — | O(log n) → O(log n) |
| `merge-forgets-tail` | correctness | — | O(n) → O(n) |
| `kadane-zero-init` | correctness | — | O(n) → O(n) |
| `window-no-guard` | correctness | — | O(n) → O(n) |

## Requests to Claude (checked without calling it)

2079 requests built by the real prompt builders and service; hidden-test checks on 293 problems (7 have no hidden value distinct from their public data, so a leak there couldn't be detected).

| Check | Result |
|---|---|
| framing | passed |
| ladder | passed |
| bounded | passed |
| hidden_tests | passed |
| secrets | passed |

## Provider failures

30 of 30 scenario × action checks fell back to the offline coach (10 failure kinds × hint, review, explain-failure). Real client limits: 60 s timeout, 2 retries.


## Usage

666 provider calls, 0 failed, 0 input and 0 output tokens, latency p50 0.0 ms, max 0.05 ms. Cost: no prices given; cost is not estimated (pass --price-input-per-mtok/--price-output-per-mtok from your actual pricing).

