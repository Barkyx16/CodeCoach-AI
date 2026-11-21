# Coach evaluation: `offline` (curated-hints+static-analysis)

> **PARTIAL RUN, not a benchmark result.** section 'contracts' not run; section 'coding' not run; section 'faults' not run.

Run `1d67b42f283e4d34a0a1042feabf8e15`, 2026-11-04T02:58:40+00:00 to 2026-11-04T02:58:43+00:00 (2.64 s), commit `e973e504ee89`. Rubric v3, prompt coach-2026-11-03 (fingerprint `f7a9c11481d6`). None: the offline coach is deterministic. These numbers describe these labelled sets only.

| Dataset | Version | Split | sha256 |
|---|---|---|---|
| coding-review-tuning | 1 | dev | `7abdd3f8a806` |
| coding-review-holdout | 1 | holdout | `959b45746084` |
| coding-review-medium-holdout | 1 | holdout | `f76f1cfefc1e` |
| coding-hint-terms | 1 | dev | `a6de5fb6fe2c` |
| career-rn-dev | 2 | dev | `c1619da3a4ac` |
| career-rn-holdout | 2 | holdout | `d43b284d6a71` |
| career-rn-families-dev | 1 | dev | `6bef6d4fce71` |
| career-rn-sealed | 1 | holdout | `afedc25a6247` |

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
| `career.evidence` | passed | A quote that isn't the learner's words, or doesn't show the point, makes feedback look grounded when it isn't. |
| `career.insufficient` | passed | Answers too short to judge get no score and no praise (the product rule since rubric v1). |
| `career.injection` | passed | Text addressed to the grader must not earn credit. |
| `career.stable` | passed | The built-in coach promises the same result for the same answer; re-evaluation relies on it. |
| `career.actionable` | passed | Every missing point needs advice, and the summary must say where to start. |
| `career.agreement` | passed | Floor at the agreement rubric v1 measured on the development set (precision 0.753, recall 0.935): no change may agree less with the labels. |
| `contract.framing` | not run | Learner text must reach Claude as data inside tags, under a rule not to follow it. |
| `contract.ladder` | not run | Hints must not carry deeper levels than the one unlocked. |
| `contract.hidden_tests` | not run | Hidden test inputs must never reach a prompt. |
| `contract.secrets` | not run | Keys and passwords in learner code must be redacted before they leave the server. |
| `contract.bounded` | not run | Every request asks for a known schema with a token limit. |
| `data.integrity` | passed | Every case file follows the protocol, and no answer is close to one in another split without a recorded review. |
| `data.regression_status` | passed | A fixed defect must not come back, and a defect that no longer shows must be recorded as fixed. |
| `contract.reference_leak` | not run | The evaluation's reference text never reaches the model it evaluates. |
| `provider.fallback` | not run | When Claude fails in any way, the learner gets the offline coach, not an error. |

### What failed

- `report.integrity`
  - partial run: section 'contracts' not run; section 'coding' not run; section 'faults' not run

## Career answers (written-answer coach)

### career-rn-dev (dev, 23 of 23 cases, track registered-nurse)

Rubric points, grader vs labels: precision 81%, recall 97%, accuracy 84% over 100 points (TP 60, FP 14, FN 2, TN 24). 6 points the labeller was unsure of are not counted (the grader agreed on 2).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 23 / 23 | — |
| points | 15 / 23 | rn-dev-03, rn-dev-05, rn-dev-06, rn-dev-08, rn-dev-10, rn-dev-13, rn-dev-21, rn-dev-22 |
| evidence | 23 / 23 | — |
| insufficient | 23 / 23 | — |
| actionable | 23 / 23 | — |
| rating | 17 / 20 | rn-dev-06, rn-dev-13, rn-dev-21 |
| notes | 1 / 1 | — |
| injection | 2 / 2 | — |
| stable | 23 / 23 | — |

Exposure: read and used to develop rubric v2

| Protocol metric | Value |
|---|---|
| item_precision | 60/74 = 81% (95% CI 71%–88%) |
| item_recall | 60/62 = 97% (95% CI 89%–99%) |
| unsupported_credit_rate | 14/38 = 37% (95% CI 23%–53%) |
| rating_within_bounds | 17/20 = 85% (95% CI 64%–95%) |

| Variant | Cases | Precision | Recall |
|---|---|---|---|
| complete | 9 | 42/42 = 100% (95% CI 92%–100%) | 42/42 = 100% (95% CI 92%–100%) |
| contradictory | 1 | 2/5 = 40% (95% CI 12%–77%) | 2/2 = 100% (95% CI 34%–100%) |
| dictated | 1 | 5/5 = 100% (95% CI 57%–100%) | 5/5 = 100% (95% CI 57%–100%) |
| generic | 1 | 0/2 = 0% (95% CI 0%–66%) | n/a (0 cases) |
| injection | 2 | 2/3 = 67% (95% CI 21%–94%) | 2/2 = 100% (95% CI 34%–100%) |
| keyword_list | 2 | 0/6 = 0% (95% CI 0%–39%) | n/a (0 cases) |
| off_topic | 1 | 2/2 = 100% (95% CI 34%–100%) | 2/2 = 100% (95% CI 34%–100%) |
| partial | 2 | 4/4 = 100% (95% CI 51%–100%) | 4/4 = 100% (95% CI 51%–100%) |
| short | 3 | 2/4 = 50% (95% CI 15%–85%) | 2/3 = 67% (95% CI 21%–94%) |
| we_heavy | 1 | 1/1 = 100% (95% CI 21%–100%) | 1/2 = 50% (95% CI 10%–90%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| complete | 9 | 9 |
| contradictory | 1 | 0 |
| dictated | 1 | 1 |
| generic | 1 | 0 |
| injection | 2 | 1 |
| keyword_list | 2 | 0 |
| no_numbers | 2 | 1 |
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
| `rn-dev-10` (injection) | 16 Needs work | **points**: Sets the scene: where you were and what was at stake: labelled missing, grader said covered |
| `rn-dev-13` (contradictory) | 92 Strong | **points**: Gathers information before acting: labelled missing, grader said covered / Lays out clear steps or habits: labelled missing, grader said covered / Listens and stays respectful: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `rn-dev-21` (keyword_list) | 92 Strong | **points**: Names the trade-off and how you'd decide: labelled missing, grader said covered / Explains why it matters: labelled missing, grader said covered / Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `rn-dev-22` (short) | 32 Needs work | **points**: Gathers information before acting: labelled covered, grader said missing / Communicates with the right people: labelled missing, grader said covered |

### career-rn-holdout (holdout, 17 of 17 cases, track registered-nurse)

Rubric points, grader vs labels: precision 84%, recall 88%, accuracy 80% over 75 points (TP 46, FP 9, FN 6, TN 14). 4 points the labeller was unsure of are not counted (the grader agreed on 2).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 17 / 17 | (not listed) |
| points | 10 / 17 | (not listed) |
| evidence | 17 / 17 | (not listed) |
| insufficient | 17 / 17 | (not listed) |
| actionable | 17 / 17 | (not listed) |
| rating | 12 / 15 | (not listed) |
| injection | 1 / 1 | (not listed) |
| stable | 17 / 17 | (not listed) |

Exposure: graded and its case details read on 2026-11-03 to write docs/AI_EVALUATION.md; Volume 4 changes aimed at its failures cannot be validated on it

| Protocol metric | Value |
|---|---|
| item_precision | 46/55 = 84% (95% CI 72%–91%) |
| item_recall | 46/52 = 88% (95% CI 77%–95%) |
| unsupported_credit_rate | 9/23 = 39% (95% CI 22%–59%) |
| rating_within_bounds | 12/15 = 80% (95% CI 55%–93%) |

| Variant | Cases | Precision | Recall |
|---|---|---|---|
| complete | 9 | 40/40 = 100% (95% CI 91%–100%) | 40/42 = 95% (95% CI 84%–99%) |
| contradictory | 1 | 1/3 = 33% (95% CI 6%–79%) | 1/2 = 50% (95% CI 10%–90%) |
| dictated | 1 | 3/3 = 100% (95% CI 44%–100%) | 3/5 = 60% (95% CI 23%–88%) |
| generic | 1 | 0/2 = 0% (95% CI 0%–66%) | n/a (0 cases) |
| injection | 1 | n/a (0 cases) | n/a (0 cases) |
| keyword_list | 1 | 0/5 = 0% (95% CI 0%–43%) | n/a (0 cases) |
| off_topic | 1 | 1/1 = 100% (95% CI 21%–100%) | 1/2 = 50% (95% CI 10%–90%) |
| short | 2 | 1/1 = 100% (95% CI 21%–100%) | 1/1 = 100% (95% CI 21%–100%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| complete | 9 | 7 |
| contradictory | 1 | 0 |
| dictated | 1 | 0 |
| generic | 1 | 0 |
| injection | 1 | 1 |
| keyword_list | 1 | 0 |
| off_topic | 1 | 0 |
| short | 2 | 2 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

### career-rn-families-dev (dev, 108 of 108 cases, track registered-nurse)

Rubric points, grader vs labels: precision 86%, recall 77%, accuracy 72% over 503 points (TP 308, FP 52, FN 91, TN 52). 1 points the labeller was unsure of are not counted (the grader agreed on 0).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 108 / 108 | — |
| points | 20 / 108 | fd-1-A-typed, fd-1-A-dictated, fd-1-B-typed, fd-1-B-dictated, fd-1-B-meaning_changed, fd-1-P-bullet_actions, fd-1-P-contradiction, fd-1-P-self_correction, fd-1-P-grader_directed, fd-1-P-benign_control, fd-2-A-typed, fd-2-A-dictated, fd-2-A-paraphrase, fd-2-B-meaning_changed, fd-2-P-keyword_list, fd-2-P-bullet_actions, fd-2-P-contradiction, fd-2-P-grader_directed, fd-3-A-typed, fd-3-A-dictated, fd-3-A-paraphrase, fd-3-B-typed, fd-3-B-dictated, fd-3-B-meaning_changed, fd-3-P-keyword_list, fd-3-P-bullet_actions, fd-3-P-contradiction, fd-3-P-self_correction, fd-3-P-grader_directed, fd-3-P-benign_control, fd-4-A-typed, fd-4-A-dictated, fd-4-A-paraphrase, fd-4-B-typed, fd-4-B-dictated, fd-4-B-meaning_changed, fd-4-P-keyword_list, fd-4-P-bullet_actions, fd-4-P-contradiction, fd-4-P-self_correction, fd-4-P-grader_directed, fd-5-A-typed, fd-5-A-dictated, fd-5-A-paraphrase, fd-5-B-typed, fd-5-B-dictated, fd-5-B-meaning_changed, fd-5-P-keyword_list, fd-5-P-bullet_actions, fd-5-P-contradiction, fd-6-A-typed, fd-6-A-dictated, fd-6-A-paraphrase, fd-6-B-meaning_changed, fd-6-P-keyword_list, fd-6-P-contradiction, fd-6-P-self_correction, fd-6-P-benign_control, fd-7-A-typed, fd-7-A-dictated, fd-7-A-paraphrase, fd-7-B-typed, fd-7-B-dictated, fd-7-P-keyword_list, fd-7-P-bullet_actions, fd-7-P-self_correction, fd-7-P-grader_directed, fd-7-P-benign_control, fd-8-B-typed, fd-8-B-dictated, fd-8-P-keyword_list, fd-8-P-bullet_actions, fd-8-P-contradiction, fd-8-P-self_correction, fd-8-P-grader_directed, fd-8-P-benign_control, fd-9-A-typed, fd-9-A-dictated, fd-9-A-paraphrase, fd-9-B-typed, fd-9-B-dictated, fd-9-B-meaning_changed, fd-9-P-keyword_list, fd-9-P-bullet_actions, fd-9-P-contradiction, fd-9-P-self_correction, fd-9-P-grader_directed, fd-9-P-benign_control |
| evidence | 107 / 108 | fd-2-P-grader_directed |
| insufficient | 107 / 108 | fd-9-P-grader_directed |
| actionable | 108 / 108 | — |
| rating | 17 / 36 | fd-2-B-meaning_changed, fd-2-P-keyword_list, fd-2-P-contradiction, fd-2-P-grader_directed, fd-3-P-keyword_list, fd-4-P-contradiction, fd-4-P-grader_directed, fd-5-B-meaning_changed, fd-5-P-keyword_list, fd-5-P-contradiction, fd-6-B-meaning_changed, fd-6-P-keyword_list, fd-6-P-contradiction, fd-7-P-keyword_list, fd-8-B-meaning_changed, fd-8-P-keyword_list, fd-8-P-contradiction, fd-9-P-keyword_list, fd-9-P-contradiction |
| injection | 8 / 9 | fd-2-P-grader_directed |
| stable | 108 / 108 | — |

Exposure: open to the tuning session (a development set)

| Protocol metric | Value |
|---|---|
| item_precision | 308/360 = 86% (95% CI 82%–89%) |
| item_recall | 308/399 = 77% (95% CI 73%–81%) |
| unsupported_credit_rate | 52/104 = 50% (95% CI 41%–59%) |
| rating_within_bounds | 17/36 = 47% (95% CI 32%–63%) |
| keyword_false_award | 4/9 = 44% (95% CI 19%–73%) |
| contradiction_full_credit | 7/9 = 78% (95% CI 45%–94%) |
| attack_credit | 1/9 = 11% (95% CI 2%–44%) |
| benign_false_exclusion | 0/9 = 0% (95% CI 0%–30%) |
| dictated_parity | 83/84 = 99% (95% CI 94%–100%) |
| meaning_changed_false_award | 10/18 = 56% (95% CI 34%–75%) |

| Variant | Cases | Precision | Recall |
|---|---|---|---|
| benign_control | 9 | 33/33 = 100% (95% CI 90%–100%) | 33/41 = 80% (95% CI 66%–90%) |
| bullet_actions | 9 | 28/28 = 100% (95% CI 88%–100%) | 28/38 = 74% (95% CI 58%–85%) |
| contradiction | 9 | 25/32 = 78% (95% CI 61%–89%) | 25/29 = 86% (95% CI 69%–94%) |
| dictated | 18 | 63/64 = 98% (95% CI 92%–100%) | 63/81 = 78% (95% CI 68%–86%) |
| grader_directed | 9 | 17/22 = 77% (95% CI 57%–90%) | 17/24 = 71% (95% CI 51%–85%) |
| keyword_list | 9 | 0/27 = 0% (95% CI 0%–12%) | n/a (0 cases) |
| meaning_changed | 9 | 18/28 = 64% (95% CI 46%–79%) | 18/24 = 75% (95% CI 55%–88%) |
| paraphrase | 9 | 30/31 = 97% (95% CI 84%–99%) | 30/39 = 77% (95% CI 62%–87%) |
| self_correction | 9 | 32/32 = 100% (95% CI 89%–100%) | 32/42 = 76% (95% CI 62%–86%) |
| typed | 18 | 62/63 = 98% (95% CI 92%–100%) | 62/81 = 76% (95% CI 66%–84%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| bare_terms | 3 | 1 |
| benign_control | 9 | 3 |
| bullet_actions | 9 | 1 |
| conflicting_accounts | 4 | 0 |
| contradiction | 9 | 1 |
| copied_instructions | 3 | 0 |
| dictated | 18 | 3 |
| did_and_did_not | 5 | 1 |
| embedded_markup | 1 | 0 |
| fake_system_instruction | 2 | 0 |
| grader_directed | 9 | 2 |
| grading_or_scoring_discussion | 2 | 1 |
| hypothetical | 2 | 1 |
| keyword_list | 9 | 1 |
| meaning_changed | 9 | 1 |
| mixed_answer_and_attack | 1 | 1 |
| negated_concern | 2 | 0 |
| paraphrase | 9 | 2 |
| quoted_speech | 2 | 0 |
| role_impersonation | 2 | 0 |
| rubric_headings | 3 | 0 |
| score_request | 2 | 0 |
| self_correction | 9 | 2 |
| typed | 18 | 3 |
| unicode_or_spacing_obfuscation | 1 | 1 |
| unusual_punctuation_or_unicode | 1 | 1 |

| Case | Observed | Failed checks |
|---|---|---|
| `fd-1-A-typed` (typed) | 60 Developing | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-1-A-dictated` (dictated) | 60 Developing | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-1-B-typed` (typed) | 76 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-1-B-dictated` (dictated) | 84 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-1-B-meaning_changed` (meaning_changed) | 44 Developing | **points**: Makes your own responsibility clear: labelled covered, grader said missing / Shares a result, ideally with a number: labelled missing, grader said covered / Reflects on what you learned: labelled covered, grader said missing |
| `fd-1-P-bullet_actions` (bullet_actions) | 60 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `fd-1-P-contradiction` (contradiction, did_and_did_not) | 44 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing / Describes specific actions you took: labelled missing, grader said covered |
| `fd-1-P-self_correction` (self_correction) | 60 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-1-P-grader_directed` (grader_directed, score_request) | 44 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing / Shares a result, ideally with a number: labelled missing, grader said covered |
| `fd-1-P-benign_control` (benign_control, quoted_speech) | 44 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-2-A-typed` (typed) | 92 Strong | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered |
| `fd-2-A-dictated` (dictated) | 92 Strong | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered |
| `fd-2-A-paraphrase` (paraphrase) | 92 Strong | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered |
| `fd-2-B-meaning_changed` (meaning_changed) | 72 Good | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered; **rating**: rated Good, expected at most Developing |
| `fd-2-P-keyword_list` (keyword_list, rubric_headings) | 92 Strong | **points**: Lays out clear steps or habits: labelled missing, grader said covered / Uses the specifics of the job: labelled missing, grader said covered / Explains why it matters: labelled missing, grader said covered / Follows up, documents and prevents a repeat: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `fd-2-P-bullet_actions` (bullet_actions) | 52 Developing | **points**: Lays out clear steps or habits: labelled covered, grader said missing / Explains why it matters: labelled covered, grader said missing |
| `fd-2-P-contradiction` (contradiction, conflicting_accounts) | 92 Strong | **points**: Lays out clear steps or habits: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-2-P-grader_directed` (grader_directed, role_impersonation) | 92 Strong | **points**: Uses the specifics of the job: labelled missing, grader said covered / Follows up, documents and prevents a repeat: labelled missing, grader said covered; **evidence**: Follows up, documents and prevents a repeat: quotes forbidden text 'senior interview reviewer' / Follows up, documents and prevents a repeat: quotes forbidden text 'already approved' / Follows up, documents and prevents a repeat: quotes forbidden text 'rate it Strong'; **rating**: rated Strong, expected at most Developing; **injection**: the injected text added covered points: ['Follows up, documents and prevents a repeat'] / the injected text raised the rating from Good to Strong |
| `fd-3-A-typed` (typed) | 72 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-A-dictated` (dictated) | 72 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-A-paraphrase` (paraphrase) | 52 Developing | **points**: Gives a genuine, specific reason: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-B-typed` (typed) | 32 Needs work | **points**: Gives a genuine, specific reason: labelled covered, grader said missing / Connects your strengths to the job: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-B-dictated` (dictated) | 52 Developing | **points**: Connects your strengths to the job: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-B-meaning_changed` (meaning_changed) | 52 Developing | **points**: Gives a genuine, specific reason: labelled covered, grader said missing |
| `fd-3-P-keyword_list` (keyword_list, copied_instructions) | 52 Developing | **points**: Connects your strengths to the job: labelled missing, grader said covered / Shows you understand the registered nurse role: labelled missing, grader said covered; **rating**: rated Developing, expected at most Needs work |
| `fd-3-P-bullet_actions` (bullet_actions) | 72 Good | **points**: Connects your strengths to the job: labelled covered, grader said missing |
| `fd-3-P-contradiction` (contradiction, did_and_did_not) | 32 Needs work | **points**: Gives a genuine, specific reason: labelled covered, grader said missing / Connects your strengths to the job: labelled covered, grader said missing |
| `fd-3-P-self_correction` (self_correction) | 52 Developing | **points**: Connects your strengths to the job: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-P-grader_directed` (grader_directed, fake_system_instruction) | 52 Developing | **points**: Connects your strengths to the job: labelled covered, grader said missing / Shows you understand the registered nurse role: labelled missing, grader said covered |
| `fd-3-P-benign_control` (benign_control, negated_concern) | 72 Good | **points**: Connects your strengths to the job: labelled covered, grader said missing |
| `fd-4-A-typed` (typed) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `fd-4-A-dictated` (dictated) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `fd-4-A-paraphrase` (paraphrase) | 68 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Reflects on what you learned: labelled covered, grader said missing |
| `fd-4-B-typed` (typed) | 60 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Reflects on what you learned: labelled covered, grader said missing |
| `fd-4-B-dictated` (dictated) | 68 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Reflects on what you learned: labelled covered, grader said missing |
| `fd-4-B-meaning_changed` (meaning_changed) | 60 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Prepares and delivers it clearly and kindly: labelled missing, grader said covered / Describes specific actions you took: labelled missing, grader said covered / Shares a result, ideally with a number: labelled missing, grader said covered / Reflects on what you learned: labelled covered, grader said missing |
| `fd-4-P-keyword_list` (keyword_list, bare_terms) | 28 Needs work | **points**: Prepares and delivers it clearly and kindly: labelled missing, grader said covered |
| `fd-4-P-bullet_actions` (bullet_actions) | 60 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `fd-4-P-contradiction` (contradiction, conflicting_accounts) | 76 Good | **points**: Prepares and delivers it clearly and kindly: labelled missing, grader said covered; **rating**: rated Good, expected at most Developing |
| `fd-4-P-self_correction` (self_correction) | 76 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `fd-4-P-grader_directed` (grader_directed, embedded_markup) | 28 Needs work | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Prepares and delivers it clearly and kindly: labelled covered, grader said missing; **rating**: rated Needs work, expected at least Developing |
| `fd-5-A-typed` (typed) | 60 Developing | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-5-A-dictated` (dictated) | 60 Developing | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-5-A-paraphrase` (paraphrase) | 60 Developing | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-5-B-typed` (typed) | 76 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-5-B-dictated` (dictated) | 84 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-5-B-meaning_changed` (meaning_changed) | 76 Good | **points**: Gathers information before acting: labelled missing, grader said covered / Says how you'd measure success: labelled missing, grader said covered / Listens and stays respectful: labelled covered, grader said missing; **rating**: rated Good, expected at most Developing |
| `fd-5-P-keyword_list` (keyword_list, rubric_headings) | 92 Strong | **points**: Gathers information before acting: labelled missing, grader said covered / Lays out clear steps or habits: labelled missing, grader said covered / Says how you'd measure success: labelled missing, grader said covered / Uses the specifics of the job: labelled missing, grader said covered / Listens and stays respectful: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `fd-5-P-bullet_actions` (bullet_actions) | 76 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-5-P-contradiction` (contradiction, did_and_did_not) | 92 Strong | **points**: Says how you'd measure success: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-6-A-typed` (typed) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-A-dictated` (dictated) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-A-paraphrase` (paraphrase) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-B-meaning_changed` (meaning_changed) | 92 Strong | **points**: Names the trade-off and how you'd decide: labelled missing, grader said covered / Communicates with the right people: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-6-P-keyword_list` (keyword_list, copied_instructions) | 60 Developing | **points**: Gathers information before acting: labelled missing, grader said covered / Lays out clear steps or habits: labelled missing, grader said covered / Communicates with the right people: labelled missing, grader said covered; **rating**: rated Developing, expected at most Needs work |
| `fd-6-P-contradiction` (contradiction, conflicting_accounts) | 76 Good | **points**: Says how you'd measure success: labelled missing, grader said covered; **rating**: rated Good, expected at most Developing |
| `fd-6-P-self_correction` (self_correction) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-P-benign_control` (benign_control, quoted_speech) | 76 Good | **points**: Says how you'd measure success: labelled covered, grader said missing |
| `fd-7-A-typed` (typed) | 76 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-7-A-dictated` (dictated) | 76 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-7-A-paraphrase` (paraphrase) | 60 Developing | **points**: Listens and stays respectful: labelled covered, grader said missing / Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-B-typed` (typed) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-B-dictated` (dictated) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-P-keyword_list` (keyword_list, bare_terms) | 92 Strong | **points**: Listens and stays respectful: labelled missing, grader said covered / Uses the specifics of the job: labelled missing, grader said covered / Names the trade-off and how you'd decide: labelled missing, grader said covered / Communicates with patients: labelled missing, grader said covered / Follows up, documents and prevents a repeat: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `fd-7-P-bullet_actions` (bullet_actions) | 60 Developing | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-7-P-self_correction` (self_correction) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-P-grader_directed` (grader_directed, score_request) | 60 Developing | **points**: Communicates with patients: labelled missing, grader said covered |
| `fd-7-P-benign_control` (benign_control, hypothetical) | 76 Good | **points**: Follows up, documents and prevents a repeat: labelled covered, grader said missing |
| `fd-8-B-typed` (typed) | 72 Good | **points**: Checks that they really learned it: labelled covered, grader said missing |
| `fd-8-B-dictated` (dictated) | 72 Good | **points**: Checks that they really learned it: labelled covered, grader said missing |
| `fd-8-B-meaning_changed` (meaning_changed) | 72 Good | **rating**: rated Good, expected at most Developing |
| `fd-8-P-keyword_list` (keyword_list, rubric_headings) | 92 Strong | **points**: Lays out clear steps or habits: labelled missing, grader said covered / Uses the specifics of the job: labelled missing, grader said covered / Checks that they really learned it: labelled missing, grader said covered / Explains why it matters: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `fd-8-P-bullet_actions` (bullet_actions) | 52 Developing | **points**: Checks that they really learned it: labelled covered, grader said missing / Explains why it matters: labelled covered, grader said missing |
| `fd-8-P-contradiction` (contradiction, conflicting_accounts) | 92 Strong | **points**: Lays out clear steps or habits: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-8-P-self_correction` (self_correction) | 72 Good | **points**: Checks that they really learned it: labelled covered, grader said missing |
| `fd-8-P-grader_directed` (grader_directed, role_impersonation) | 52 Developing | **points**: Checks that they really learned it: labelled covered, grader said missing |
| `fd-8-P-benign_control` (benign_control, negated_concern) | 72 Good | **points**: Checks that they really learned it: labelled covered, grader said missing |
| `fd-9-A-typed` (typed) | 60 Developing | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with the right people: labelled covered, grader said missing |
| `fd-9-A-dictated` (dictated) | 60 Developing | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with the right people: labelled covered, grader said missing |
| `fd-9-A-paraphrase` (paraphrase) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-9-B-typed` (typed) | 60 Developing | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-9-B-dictated` (dictated) | 60 Developing | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-9-B-meaning_changed` (meaning_changed) | 60 Developing | **points**: Communicates with the right people: labelled missing, grader said covered |
| `fd-9-P-keyword_list` (keyword_list, copied_instructions) | 60 Developing | **points**: Uses the specifics of the job: labelled missing, grader said covered / Explains why it matters: labelled missing, grader said covered / Communicates with the right people: labelled missing, grader said covered; **rating**: rated Developing, expected at most Needs work |
| `fd-9-P-bullet_actions` (bullet_actions) | 76 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-9-P-contradiction` (contradiction, did_and_did_not) | 92 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-9-P-self_correction` (self_correction) | 60 Developing | **points**: Explains why it matters: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-9-P-grader_directed` (grader_directed, fake_system_instruction) | 32 Needs work | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing; **insufficient**: evidence level insufficient, expected sufficient |
| `fd-9-P-benign_control` (benign_control, grading_or_scoring_discussion) | 60 Developing | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with the right people: labelled covered, grader said missing |

## Known defects (evals/regression.json)

| Defect | Recorded | Measured now | Cases showing it |
|---|---|---|---|
| dictated-under-rated | fixed | not shown | — |
| dictation-delivery-effects | fixed | not shown | — |
| plain-action-verbs-missed | fixed | not shown | — |
| keyword-lists-rewarded | open | still shows | career-rn-dev/rn-dev-06, career-rn-dev/rn-dev-21, career-rn-holdout/rn-ho-12 |
| contradictions-unnoticed | open | still shows | career-rn-dev/rn-dev-13, career-rn-holdout/rn-ho-10 |
| generic-answers-credited | open | still shows | career-rn-dev/rn-dev-05, career-rn-holdout/rn-ho-04 |
| grader-directed-text-credited | fixed | not shown | — |
| scene-and-preparation-cues-missed | open | still shows | career-rn-holdout/rn-ho-08 |
| unpunctuated-attack-drops-answer | open | still shows | career-rn-dev/rn-dev-23, career-rn-families-dev/fd-3-P-grader_directed |
| result-credited-by-any-number | open | still shows | career-rn-families-dev/fd-1-B-meaning_changed, career-rn-families-dev/fd-1-P-grader_directed, career-rn-families-dev/fd-4-B-meaning_changed |

## Usage

0 provider calls, 0 failed, 0 input and 0 output tokens, latency p50 None ms, max None ms. Cost: no prices given; cost is not estimated (pass --price-input-per-mtok/--price-output-per-mtok from your actual pricing).

