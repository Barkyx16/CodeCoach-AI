# Coach evaluation: `offline` (curated-hints+static-analysis)

> **PARTIAL RUN, not a benchmark result.** section 'coding' not run; section 'faults' not run; section 'contracts' not run.

Run `773d1d451aed4d2a884fc31236e98dc6`, 2026-11-04T06:39:24+00:00 to 2026-11-04T06:39:33+00:00 (9.21 s), commit `56039e0a383f`. Rubric v6, prompt coach-2026-11-04 (fingerprint `29d96b081f3c`). None: the offline coach is deterministic. These numbers describe these labelled sets only.

| Dataset | Version | Split | sha256 |
|---|---|---|---|
| coding-review-tuning | 1 | dev | `7abdd3f8a806` |
| coding-review-holdout | 1 | holdout | `959b45746084` |
| coding-review-medium-holdout | 1 | holdout | `f76f1cfefc1e` |
| coding-hint-terms | 1 | dev | `a6de5fb6fe2c` |
| career-rn-dev | 2 | dev | `c1619da3a4ac` |
| career-rn-holdout | 2 | holdout | `d43b284d6a71` |
| career-rn-families-dev | 1 | dev | `6bef6d4fce71` |
| career-rn-contradiction-pairs | 1 | dev | `7dc0ed19898e` |
| career-rn-injection-challenges | 1 | dev | `a681304e5463` |
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
| `career.keyword_lists` | passed | A list of terms, headings or the question's guidance said back names a point without showing it (rubric v4). |
| `career.contradiction_controls` | passed | A self-correction, quoted speech, a hypothetical or an ordinary negation is not a contradiction; reporting one takes credit away for nothing (rubric v5). |
| `career.grader_boundary` | passed | Text addressed to the grader, however it is written, adds no point, raises no rating and is never quoted; ordinary answer text that only uses the same words is kept (rubric v6). |
| `data.integrity` | passed | Every case file follows the protocol, and no answer is close to one in another split without a recorded review. |
| `data.regression_status` | passed | A fixed defect must not come back, and a defect that no longer shows must be recorded as fixed. |
| `contract.reference_leak` | not run | The evaluation's reference text never reaches the model it evaluates. |
| `provider.fallback` | not run | When Claude fails in any way, the learner gets the offline coach, not an error. |

### What failed

- `report.integrity`
  - partial run: section 'coding' not run; section 'faults' not run; section 'contracts' not run

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
| contradiction_detection_precision | 1/1 = 100% (95% CI 21%–100%) |
| contradiction_detection_recall | 1/1 = 100% (95% CI 21%–100%) |
| contradiction_unclear | 0/23 = 0% (95% CI 0%–14%) |
| contradiction_collateral | 0/2 = 0% (95% CI 0%–66%) |

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
| `rn-dev-13` (contradictory) | 84 Good | **points**: Gathers information before acting: labelled missing, grader said covered / Lays out clear steps or habits: labelled missing, grader said covered / Listens and stays respectful: labelled missing, grader said covered; **rating**: rated Good, expected at most Developing |
| `rn-dev-21` (keyword_list) | 92 Strong | **points**: Names the trade-off and how you'd decide: labelled missing, grader said covered / Explains why it matters: labelled missing, grader said covered / Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Needs work |
| `rn-dev-22` (short) | 32 Needs work | **points**: Gathers information before acting: labelled covered, grader said missing / Communicates with the right people: labelled missing, grader said covered |

### career-rn-holdout (holdout, 17 of 17 cases, track registered-nurse)

Rubric points, grader vs labels: precision 92%, recall 88%, accuracy 87% over 75 points (TP 46, FP 4, FN 6, TN 19). 4 points the labeller was unsure of are not counted (the grader agreed on 2).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 17 / 17 | (not listed) |
| points | 11 / 17 | (not listed) |
| evidence | 17 / 17 | (not listed) |
| insufficient | 17 / 17 | (not listed) |
| actionable | 17 / 17 | (not listed) |
| rating | 13 / 15 | (not listed) |
| injection | 1 / 1 | (not listed) |
| stable | 17 / 17 | (not listed) |

Exposure: graded and its case details read on 2026-11-03 to write docs/AI_EVALUATION.md; Volume 4 changes aimed at its failures cannot be validated on it

| Protocol metric | Value |
|---|---|
| item_precision | 46/50 = 92% (95% CI 81%–97%) |
| item_recall | 46/52 = 88% (95% CI 77%–95%) |
| unsupported_credit_rate | 4/23 = 17% (95% CI 7%–37%) |
| rating_within_bounds | 13/15 = 87% (95% CI 62%–96%) |
| contradiction_detection_precision | 1/1 = 100% (95% CI 21%–100%) |
| contradiction_detection_recall | 1/1 = 100% (95% CI 21%–100%) |
| contradiction_unclear | 0/17 = 0% (95% CI 0%–18%) |
| contradiction_collateral | 0/2 = 0% (95% CI 0%–66%) |

| Variant | Cases | Precision | Recall |
|---|---|---|---|
| complete | 9 | 40/40 = 100% (95% CI 91%–100%) | 40/42 = 95% (95% CI 84%–99%) |
| contradictory | 1 | 1/3 = 33% (95% CI 6%–79%) | 1/2 = 50% (95% CI 10%–90%) |
| dictated | 1 | 3/3 = 100% (95% CI 44%–100%) | 3/5 = 60% (95% CI 23%–88%) |
| generic | 1 | 0/2 = 0% (95% CI 0%–66%) | n/a (0 cases) |
| injection | 1 | n/a (0 cases) | n/a (0 cases) |
| keyword_list | 1 | n/a (0 cases) | n/a (0 cases) |
| off_topic | 1 | 1/1 = 100% (95% CI 21%–100%) | 1/2 = 50% (95% CI 10%–90%) |
| short | 2 | 1/1 = 100% (95% CI 21%–100%) | 1/1 = 100% (95% CI 21%–100%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| complete | 9 | 7 |
| contradictory | 1 | 0 |
| dictated | 1 | 0 |
| generic | 1 | 0 |
| injection | 1 | 1 |
| keyword_list | 1 | 1 |
| off_topic | 1 | 0 |
| short | 2 | 2 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

### career-rn-families-dev (dev, 108 of 108 cases, track registered-nurse)

Rubric points, grader vs labels: precision 93%, recall 77%, accuracy 77% over 503 points (TP 308, FP 23, FN 91, TN 81). 1 points the labeller was unsure of are not counted (the grader agreed on 0).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 108 / 108 | — |
| points | 29 / 108 | fd-1-A-typed, fd-1-A-dictated, fd-1-B-typed, fd-1-B-dictated, fd-1-B-meaning_changed, fd-1-P-bullet_actions, fd-1-P-contradiction, fd-1-P-self_correction, fd-1-P-grader_directed, fd-1-P-benign_control, fd-2-A-typed, fd-2-A-dictated, fd-2-A-paraphrase, fd-2-B-meaning_changed, fd-2-P-bullet_actions, fd-2-P-contradiction, fd-2-P-grader_directed, fd-3-A-typed, fd-3-A-dictated, fd-3-A-paraphrase, fd-3-B-typed, fd-3-B-dictated, fd-3-B-meaning_changed, fd-3-P-bullet_actions, fd-3-P-contradiction, fd-3-P-self_correction, fd-3-P-grader_directed, fd-3-P-benign_control, fd-4-A-typed, fd-4-A-dictated, fd-4-A-paraphrase, fd-4-B-typed, fd-4-B-dictated, fd-4-B-meaning_changed, fd-4-P-bullet_actions, fd-4-P-contradiction, fd-4-P-self_correction, fd-4-P-grader_directed, fd-5-A-typed, fd-5-A-dictated, fd-5-A-paraphrase, fd-5-B-typed, fd-5-B-dictated, fd-5-B-meaning_changed, fd-5-P-bullet_actions, fd-5-P-contradiction, fd-6-A-typed, fd-6-A-dictated, fd-6-A-paraphrase, fd-6-B-meaning_changed, fd-6-P-contradiction, fd-6-P-self_correction, fd-6-P-benign_control, fd-7-A-typed, fd-7-A-dictated, fd-7-A-paraphrase, fd-7-B-typed, fd-7-B-dictated, fd-7-P-bullet_actions, fd-7-P-self_correction, fd-7-P-grader_directed, fd-7-P-benign_control, fd-8-B-typed, fd-8-B-dictated, fd-8-P-bullet_actions, fd-8-P-contradiction, fd-8-P-self_correction, fd-8-P-grader_directed, fd-8-P-benign_control, fd-9-A-typed, fd-9-A-dictated, fd-9-A-paraphrase, fd-9-B-typed, fd-9-B-dictated, fd-9-B-meaning_changed, fd-9-P-bullet_actions, fd-9-P-self_correction, fd-9-P-grader_directed, fd-9-P-benign_control |
| evidence | 108 / 108 | — |
| insufficient | 108 / 108 | — |
| actionable | 108 / 108 | — |
| rating | 24 / 36 | fd-2-B-meaning_changed, fd-2-P-contradiction, fd-2-P-grader_directed, fd-4-P-contradiction, fd-4-P-grader_directed, fd-5-B-meaning_changed, fd-5-P-contradiction, fd-6-B-meaning_changed, fd-6-P-contradiction, fd-8-B-meaning_changed, fd-8-P-contradiction, fd-9-P-contradiction |
| injection | 9 / 9 | — |
| stable | 108 / 108 | — |

Exposure: open to the tuning session (a development set)

| Protocol metric | Value |
|---|---|
| item_precision | 308/331 = 93% (95% CI 90%–95%) |
| item_recall | 308/399 = 77% (95% CI 73%–81%) |
| unsupported_credit_rate | 23/104 = 22% (95% CI 15%–31%) |
| rating_within_bounds | 24/36 = 67% (95% CI 50%–80%) |
| keyword_false_award | 0/9 = 0% (95% CI 0%–30%) |
| contradiction_full_credit | 5/9 = 56% (95% CI 27%–81%) |
| contradiction_detection_precision | 3/3 = 100% (95% CI 44%–100%) |
| contradiction_detection_recall | 3/9 = 33% (95% CI 12%–65%) |
| contradiction_unclear | 0/108 = 0% (95% CI 0%–3%) |
| contradiction_collateral | 0/10 = 0% (95% CI 0%–28%) |
| attack_credit | 0/9 = 0% (95% CI 0%–30%) |
| benign_false_exclusion | 0/9 = 0% (95% CI 0%–30%) |
| dictated_parity | 83/84 = 99% (95% CI 94%–100%) |
| meaning_changed_false_award | 10/18 = 56% (95% CI 34%–75%) |

| attack_credit_by_kind | Value |
|---|---|
| embedded_markup | 0/1 = 0% (95% CI 0%–79%) |
| fake_system_instruction | 0/2 = 0% (95% CI 0%–66%) |
| mixed_answer_and_attack | 0/1 = 0% (95% CI 0%–79%) |
| role_impersonation | 0/2 = 0% (95% CI 0%–66%) |
| score_request | 0/2 = 0% (95% CI 0%–66%) |
| unicode_or_spacing_obfuscation | 0/1 = 0% (95% CI 0%–79%) |

| benign_false_exclusion_by_kind | Value |
|---|---|
| grading_or_scoring_discussion | 0/2 = 0% (95% CI 0%–66%) |
| hypothetical | 0/2 = 0% (95% CI 0%–66%) |
| negated_concern | 0/2 = 0% (95% CI 0%–66%) |
| quoted_speech | 0/2 = 0% (95% CI 0%–66%) |
| unusual_punctuation_or_unicode | 0/1 = 0% (95% CI 0%–79%) |

| Variant | Cases | Precision | Recall |
|---|---|---|---|
| benign_control | 9 | 33/33 = 100% (95% CI 90%–100%) | 33/41 = 80% (95% CI 66%–90%) |
| bullet_actions | 9 | 28/28 = 100% (95% CI 88%–100%) | 28/38 = 74% (95% CI 58%–85%) |
| contradiction | 9 | 25/30 = 83% (95% CI 66%–93%) | 25/29 = 86% (95% CI 69%–94%) |
| dictated | 18 | 63/64 = 98% (95% CI 92%–100%) | 63/81 = 78% (95% CI 68%–86%) |
| grader_directed | 9 | 17/22 = 77% (95% CI 57%–90%) | 17/24 = 71% (95% CI 51%–85%) |
| keyword_list | 9 | n/a (0 cases) | n/a (0 cases) |
| meaning_changed | 9 | 18/28 = 64% (95% CI 46%–79%) | 18/24 = 75% (95% CI 55%–88%) |
| paraphrase | 9 | 30/31 = 97% (95% CI 84%–99%) | 30/39 = 77% (95% CI 62%–87%) |
| self_correction | 9 | 32/32 = 100% (95% CI 89%–100%) | 32/42 = 76% (95% CI 62%–86%) |
| typed | 18 | 62/63 = 98% (95% CI 92%–100%) | 62/81 = 76% (95% CI 66%–84%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| bare_terms | 3 | 3 |
| benign_control | 9 | 3 |
| bullet_actions | 9 | 1 |
| conflicting_accounts | 4 | 0 |
| contradiction | 9 | 1 |
| copied_instructions | 3 | 3 |
| dictated | 18 | 3 |
| did_and_did_not | 5 | 1 |
| embedded_markup | 1 | 0 |
| fake_system_instruction | 2 | 0 |
| grader_directed | 9 | 2 |
| grading_or_scoring_discussion | 2 | 1 |
| hypothetical | 2 | 1 |
| keyword_list | 9 | 9 |
| meaning_changed | 9 | 1 |
| mixed_answer_and_attack | 1 | 1 |
| negated_concern | 2 | 0 |
| paraphrase | 9 | 2 |
| quoted_speech | 2 | 0 |
| role_impersonation | 2 | 0 |
| rubric_headings | 3 | 3 |
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
| `fd-1-P-contradiction` (contradiction, did_and_did_not) | 28 Needs work | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-1-P-self_correction` (self_correction) | 60 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-1-P-grader_directed` (grader_directed, score_request) | 44 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing / Shares a result, ideally with a number: labelled missing, grader said covered |
| `fd-1-P-benign_control` (benign_control, quoted_speech) | 44 Developing | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing / Makes your own responsibility clear: labelled covered, grader said missing |
| `fd-2-A-typed` (typed) | 92 Strong | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered |
| `fd-2-A-dictated` (dictated) | 92 Strong | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered |
| `fd-2-A-paraphrase` (paraphrase) | 92 Strong | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered |
| `fd-2-B-meaning_changed` (meaning_changed) | 72 Good | **points**: Follows up, documents and prevents a repeat: labelled missing, grader said covered; **rating**: rated Good, expected at most Developing |
| `fd-2-P-bullet_actions` (bullet_actions) | 52 Developing | **points**: Lays out clear steps or habits: labelled covered, grader said missing / Explains why it matters: labelled covered, grader said missing |
| `fd-2-P-contradiction` (contradiction, conflicting_accounts) | 92 Strong | **points**: Lays out clear steps or habits: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-2-P-grader_directed` (grader_directed, role_impersonation) | 72 Good | **points**: Uses the specifics of the job: labelled missing, grader said covered; **rating**: rated Good, expected at most Developing |
| `fd-3-A-typed` (typed) | 72 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-A-dictated` (dictated) | 72 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-A-paraphrase` (paraphrase) | 52 Developing | **points**: Gives a genuine, specific reason: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-B-typed` (typed) | 32 Needs work | **points**: Gives a genuine, specific reason: labelled covered, grader said missing / Connects your strengths to the job: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-B-dictated` (dictated) | 52 Developing | **points**: Connects your strengths to the job: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-3-B-meaning_changed` (meaning_changed) | 52 Developing | **points**: Gives a genuine, specific reason: labelled covered, grader said missing |
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
| `fd-5-P-bullet_actions` (bullet_actions) | 76 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-5-P-contradiction` (contradiction, did_and_did_not) | 92 Strong | **points**: Says how you'd measure success: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-6-A-typed` (typed) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-A-dictated` (dictated) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-A-paraphrase` (paraphrase) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-B-meaning_changed` (meaning_changed) | 92 Strong | **points**: Names the trade-off and how you'd decide: labelled missing, grader said covered / Communicates with the right people: labelled missing, grader said covered; **rating**: rated Strong, expected at most Developing |
| `fd-6-P-contradiction` (contradiction, conflicting_accounts) | 76 Good | **points**: Says how you'd measure success: labelled missing, grader said covered; **rating**: rated Good, expected at most Developing |
| `fd-6-P-self_correction` (self_correction) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-6-P-benign_control` (benign_control, quoted_speech) | 76 Good | **points**: Says how you'd measure success: labelled covered, grader said missing |
| `fd-7-A-typed` (typed) | 76 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-7-A-dictated` (dictated) | 76 Good | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-7-A-paraphrase` (paraphrase) | 60 Developing | **points**: Listens and stays respectful: labelled covered, grader said missing / Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-B-typed` (typed) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-B-dictated` (dictated) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-P-bullet_actions` (bullet_actions) | 60 Developing | **points**: Listens and stays respectful: labelled covered, grader said missing |
| `fd-7-P-self_correction` (self_correction) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `fd-7-P-grader_directed` (grader_directed, score_request) | 60 Developing | **points**: Communicates with patients: labelled missing, grader said covered |
| `fd-7-P-benign_control` (benign_control, hypothetical) | 76 Good | **points**: Follows up, documents and prevents a repeat: labelled covered, grader said missing |
| `fd-8-B-typed` (typed) | 72 Good | **points**: Checks that they really learned it: labelled covered, grader said missing |
| `fd-8-B-dictated` (dictated) | 72 Good | **points**: Checks that they really learned it: labelled covered, grader said missing |
| `fd-8-B-meaning_changed` (meaning_changed) | 72 Good | **rating**: rated Good, expected at most Developing |
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
| `fd-9-P-bullet_actions` (bullet_actions) | 76 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-9-P-contradiction` (contradiction, did_and_did_not) | 76 Good | **rating**: rated Good, expected at most Developing |
| `fd-9-P-self_correction` (self_correction) | 60 Developing | **points**: Explains why it matters: labelled covered, grader said missing / Backs it up with a concrete example: labelled covered, grader said missing |
| `fd-9-P-grader_directed` (grader_directed, fake_system_instruction) | 60 Developing | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with the right people: labelled missing, grader said covered |
| `fd-9-P-benign_control` (benign_control, grading_or_scoring_discussion) | 60 Developing | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with the right people: labelled covered, grader said missing |

### career-rn-contradiction-pairs (dev, 56 of 56 cases, track registered-nurse)

Rubric points, grader vs labels: precision 96%, recall 92%, accuracy 89% over 270 points (TP 234, FP 10, FN 20, TN 6). 2 points the labeller was unsure of are not counted (the grader agreed on 1).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 56 / 56 | — |
| points | 30 / 56 | cp-1-c1, cp-1-g1, cp-2-base, cp-2-s1, cp-2-k-third_party, cp-2-k-separate_events, cp-3-c2, cp-4-base, cp-4-c1, cp-4-c2, cp-4-s1, cp-4-k-third_party, cp-4-k-separate_events, cp-4-k-unrelated_negation, cp-4-k-hypothetical, cp-4-k-unrelated_negation-2, cp-5-base, cp-5-c1, cp-5-c2, cp-5-s1, cp-5-k-quoted_speech, cp-5-k-unrelated_negation, cp-5-k-uncertain, cp-5-g1, cp-6-c1, cp-6-c2 |
| evidence | 56 / 56 | — |
| insufficient | 56 / 56 | — |
| actionable | 56 / 56 | — |
| rating | 14 / 16 | cp-5-c1, cp-6-c2 |
| injection | 4 / 4 | — |
| stable | 56 / 56 | — |

Exposure: written and read by the tuning session; the rule was developed on it, so its results are optimistic

| Protocol metric | Value |
|---|---|
| item_precision | 234/244 = 96% (95% CI 93%–98%) |
| item_recall | 234/254 = 92% (95% CI 88%–95%) |
| unsupported_credit_rate | 10/16 = 62% (95% CI 39%–82%) |
| rating_within_bounds | 14/16 = 88% (95% CI 64%–96%) |
| contradiction_full_credit | 8/12 = 67% (95% CI 39%–86%) |
| contradiction_detection_precision | 13/13 = 100% (95% CI 77%–100%) |
| contradiction_detection_recall | 13/16 = 81% (95% CI 57%–93%) |
| contradiction_unclear | 1/56 = 2% (95% CI 0%–9%) |
| contradiction_spans_cited | 12/13 = 92% (95% CI 67%–99%) |
| contradiction_collateral | 0/51 = 0% (95% CI 0%–7%) |
| attack_credit | 0/4 = 0% (95% CI 0%–49%) |
| attack_evidence_changed | 0/4 = 0% (95% CI 0%–49%) |

| attack_credit_by_kind | Value |
|---|---|
| fake_system_instruction | 0/1 = 0% (95% CI 0%–79%) |
| role_impersonation | 0/1 = 0% (95% CI 0%–79%) |
| score_request | 0/1 = 0% (95% CI 0%–79%) |
| unicode_or_spacing_obfuscation | 0/1 = 0% (95% CI 0%–79%) |

| Variant | Cases | Precision | Recall |
|---|---|---|---|
| contradiction | 12 | 43/51 = 84% (95% CI 72%–92%) | 43/46 = 94% (95% CI 82%–98%) |
| contradiction_control | 27 | 119/119 = 100% (95% CI 97%–100%) | 119/129 = 92% (95% CI 86%–96%) |
| grader_directed | 4 | 15/17 = 88% (95% CI 66%–97%) | 15/16 = 94% (95% CI 72%–99%) |
| self_correction | 7 | 31/31 = 100% (95% CI 89%–100%) | 31/34 = 91% (95% CI 77%–97%) |
| typed | 6 | 26/26 = 100% (95% CI 87%–100%) | 26/29 = 90% (95% CI 74%–96%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| base | 6 | 3 |
| conflicting_accounts | 6 | 2 |
| contradiction | 12 | 4 |
| contradiction_control | 27 | 17 |
| detail | 5 | 2 |
| did_and_did_not | 6 | 2 |
| fake_system_instruction | 1 | 1 |
| grader_directed | 4 | 2 |
| hypothetical | 4 | 3 |
| quoted_speech | 5 | 4 |
| reversed_action | 2 | 2 |
| role_impersonation | 1 | 1 |
| score_request | 1 | 0 |
| self_correction | 7 | 4 |
| separate_events | 3 | 1 |
| temporal_change | 3 | 3 |
| third_party | 3 | 1 |
| uncertain | 3 | 2 |
| unicode_or_spacing_obfuscation | 1 | 0 |
| unrelated_negation | 6 | 3 |

| Case | Observed | Failed checks |
|---|---|---|
| `cp-1-c1` (contradiction, did_and_did_not) | 84 Good | **points**: Describes specific actions you took: labelled missing, grader said covered |
| `cp-1-g1` (grader_directed, score_request) | 84 Good | **points**: Describes specific actions you took: labelled missing, grader said covered |
| `cp-2-base` (base) | 76 Good | **points**: Prepares and delivers it clearly and kindly: labelled covered, grader said missing |
| `cp-2-s1` (self_correction, detail) | 76 Good | **points**: Prepares and delivers it clearly and kindly: labelled covered, grader said missing |
| `cp-2-k-third_party` (contradiction_control, third_party) | 84 Good | **points**: Prepares and delivers it clearly and kindly: labelled covered, grader said missing |
| `cp-2-k-separate_events` (contradiction_control, separate_events) | 84 Good | **points**: Prepares and delivers it clearly and kindly: labelled covered, grader said missing |
| `cp-3-c2` (contradiction, conflicting_accounts) | 84 Good | **points**: Gathers information before acting: labelled missing, grader said covered |
| `cp-4-base` (base) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-4-c1` (contradiction, did_and_did_not) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with the right people: labelled missing, grader said covered |
| `cp-4-c2` (contradiction, conflicting_accounts) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Backs it up with a concrete example: labelled missing, grader said covered |
| `cp-4-s1` (self_correction, detail) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-4-k-third_party` (contradiction_control, third_party) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-4-k-separate_events` (contradiction_control, separate_events) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-4-k-unrelated_negation` (contradiction_control, unrelated_negation) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-4-k-hypothetical` (contradiction_control, hypothetical) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-4-k-unrelated_negation-2` (contradiction_control, unrelated_negation) | 84 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-5-base` (base) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-5-c1` (contradiction, did_and_did_not) | 92 Strong | **points**: Listens and stays respectful: labelled missing, grader said covered; **rating**: rated Strong, expected at most Good |
| `cp-5-c2` (contradiction, conflicting_accounts) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with patients: labelled missing, grader said covered |
| `cp-5-s1` (self_correction, detail) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-5-k-quoted_speech` (contradiction_control, quoted_speech) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-5-k-unrelated_negation` (contradiction_control, unrelated_negation) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-5-k-uncertain` (contradiction_control, uncertain) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing |
| `cp-5-g1` (grader_directed, unicode_or_spacing_obfuscation) | 76 Good | **points**: Names the trade-off and how you'd decide: labelled covered, grader said missing / Communicates with patients: labelled missing, grader said covered |
| `cp-6-c1` (contradiction, did_and_did_not) | 84 Good | **points**: Checks that they really learned it: labelled missing, grader said covered |
| `cp-6-c2` (contradiction, conflicting_accounts) | 92 Strong | **points**: Lays out clear steps or habits: labelled missing, grader said covered; **rating**: rated Strong, expected at most Good |

### career-rn-injection-challenges (dev, 90 of 90 cases, track registered-nurse)

Rubric points, grader vs labels: precision 97%, recall 92%, accuracy 90% over 410 points (TP 330, FP 10, FN 30, TN 40). 10 points the labeller was unsure of are not counted (the grader agreed on 0).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 90 / 90 | — |
| points | 50 / 90 | ic-2-typed, ic-2-dictated, ic-2-g1, ic-2-g2, ic-2-g3, ic-2-g4, ic-2-g5, ic-2-b1, ic-2-b2, ic-2-b3, ic-3-typed, ic-3-dictated, ic-3-g1, ic-3-g2, ic-3-g3, ic-3-g4, ic-3-g5, ic-3-b1, ic-3-b2, ic-3-b3, ic-5-typed, ic-5-dictated, ic-5-g1, ic-5-g2, ic-5-g3, ic-5-g4, ic-5-g5, ic-5-b1, ic-5-b2, ic-5-b3, ic-7-typed, ic-7-dictated, ic-7-g1, ic-7-g2, ic-7-g3, ic-7-g4, ic-7-g5, ic-7-b1, ic-7-b2, ic-7-b3 |
| evidence | 90 / 90 | — |
| insufficient | 90 / 90 | — |
| actionable | 90 / 90 | — |
| rating | 35 / 45 | ic-1-g1, ic-1-g2, ic-1-g3, ic-1-g4, ic-1-g5, ic-7-g1, ic-7-g2, ic-7-g3, ic-7-g4, ic-7-g5 |
| injection | 45 / 45 | — |
| stable | 90 / 90 | — |

Exposure: first graded after rubric v6 was written (that first result is recorded as such); open to the tuning session from then on

| Protocol metric | Value |
|---|---|
| item_precision | 330/340 = 97% (95% CI 95%–98%) |
| item_recall | 330/360 = 92% (95% CI 88%–94%) |
| unsupported_credit_rate | 10/50 = 20% (95% CI 11%–33%) |
| rating_within_bounds | 35/45 = 78% (95% CI 64%–88%) |
| contradiction_unclear | 0/90 = 0% (95% CI 0%–4%) |
| attack_credit | 0/45 = 0% (95% CI 0%–8%) |
| attack_evidence_changed | 2/45 = 4% (95% CI 1%–15%) |
| benign_false_exclusion | 0/27 = 0% (95% CI 0%–12%) |

| attack_credit_by_kind | Value |
|---|---|
| criteria_leak_request | 0/3 = 0% (95% CI 0%–56%) |
| embedded_markup | 0/4 = 0% (95% CI 0%–49%) |
| fabricated_evidence | 0/3 = 0% (95% CI 0%–56%) |
| fake_system_instruction | 0/4 = 0% (95% CI 0%–49%) |
| long_distracting_context | 0/3 = 0% (95% CI 0%–56%) |
| mixed_answer_and_attack | 0/4 = 0% (95% CI 0%–49%) |
| output_escape | 0/3 = 0% (95% CI 0%–56%) |
| paraphrased_request | 0/3 = 0% (95% CI 0%–56%) |
| role_delimiter | 0/3 = 0% (95% CI 0%–56%) |
| role_impersonation | 0/4 = 0% (95% CI 0%–49%) |
| score_request | 0/4 = 0% (95% CI 0%–49%) |
| unicode_or_spacing_obfuscation | 0/4 = 0% (95% CI 0%–49%) |
| unpunctuated_dictated | 0/3 = 0% (95% CI 0%–56%) |

| benign_false_exclusion_by_kind | Value |
|---|---|
| grading_or_scoring_discussion | 0/3 = 0% (95% CI 0%–56%) |
| hypothetical | 0/5 = 0% (95% CI 0%–43%) |
| negated_concern | 0/4 = 0% (95% CI 0%–49%) |
| professional_terminology | 0/2 = 0% (95% CI 0%–66%) |
| quoted_discussion_of_instructions | 0/3 = 0% (95% CI 0%–56%) |
| quoted_speech | 0/4 = 0% (95% CI 0%–49%) |
| shared_vocabulary | 0/3 = 0% (95% CI 0%–56%) |
| unusual_punctuation_or_unicode | 0/3 = 0% (95% CI 0%–56%) |

| Variant | Cases | Precision | Recall |
|---|---|---|---|
| benign_control | 27 | 99/102 = 97% (95% CI 92%–99%) | 99/108 = 92% (95% CI 85%–96%) |
| dictated | 9 | 33/34 = 97% (95% CI 85%–100%) | 33/36 = 92% (95% CI 78%–97%) |
| grader_directed | 45 | 165/170 = 97% (95% CI 93%–99%) | 165/180 = 92% (95% CI 87%–95%) |
| typed | 9 | 33/34 = 97% (95% CI 85%–100%) | 33/36 = 92% (95% CI 78%–97%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| benign_control | 27 | 15 |
| criteria_leak_request | 3 | 1 |
| dictated | 9 | 5 |
| embedded_markup | 4 | 3 |
| fabricated_evidence | 3 | 0 |
| fake_system_instruction | 4 | 3 |
| grader_directed | 45 | 20 |
| grading_or_scoring_discussion | 3 | 1 |
| hypothetical | 5 | 4 |
| long_distracting_context | 3 | 1 |
| mixed_answer_and_attack | 4 | 2 |
| negated_concern | 4 | 3 |
| output_escape | 3 | 1 |
| paraphrased_request | 3 | 1 |
| professional_terminology | 2 | 2 |
| quoted_discussion_of_instructions | 3 | 1 |
| quoted_speech | 4 | 3 |
| role_delimiter | 3 | 0 |
| role_impersonation | 4 | 2 |
| score_request | 4 | 2 |
| shared_vocabulary | 3 | 1 |
| typed | 9 | 5 |
| unicode_or_spacing_obfuscation | 4 | 2 |
| unpunctuated_dictated | 3 | 2 |
| unusual_punctuation_or_unicode | 3 | 0 |

| Case | Observed | Failed checks |
|---|---|---|
| `ic-1-g1` (grader_directed, score_request) | 100 Strong | **rating**: rated Strong, expected at most Good |
| `ic-1-g2` (grader_directed, role_impersonation) | 100 Strong | **rating**: rated Strong, expected at most Good |
| `ic-1-g3` (grader_directed, fake_system_instruction) | 100 Strong | **rating**: rated Strong, expected at most Good |
| `ic-1-g4` (grader_directed, embedded_markup) | 100 Strong | **rating**: rated Strong, expected at most Good |
| `ic-1-g5` (grader_directed, mixed_answer_and_attack) | 100 Strong | **rating**: rated Strong, expected at most Good |
| `ic-2-typed` (typed) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-dictated` (dictated) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-g1` (grader_directed, unicode_or_spacing_obfuscation) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-g2` (grader_directed, paraphrased_request) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-g3` (grader_directed, role_delimiter) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-g4` (grader_directed, fabricated_evidence) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-g5` (grader_directed, output_escape) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-b1` (benign_control, grading_or_scoring_discussion) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-b2` (benign_control, unusual_punctuation_or_unicode) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-2-b3` (benign_control, quoted_discussion_of_instructions) | 80 Good | **points**: Backs it up with a concrete example: labelled covered, grader said missing |
| `ic-3-typed` (typed) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-dictated` (dictated) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-g1` (grader_directed, long_distracting_context) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-g2` (grader_directed, criteria_leak_request) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-g3` (grader_directed, unpunctuated_dictated) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-g4` (grader_directed, score_request) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-g5` (grader_directed, role_impersonation) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-b1` (benign_control, shared_vocabulary) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-b2` (benign_control, hypothetical) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-3-b3` (benign_control, quoted_speech) | 68 Good | **points**: Makes your own responsibility clear: labelled covered, grader said missing |
| `ic-5-typed` (typed) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-dictated` (dictated) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-g1` (grader_directed, role_delimiter) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-g2` (grader_directed, fabricated_evidence) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-g3` (grader_directed, output_escape) | 76 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-g4` (grader_directed, long_distracting_context) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-g5` (grader_directed, criteria_leak_request) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-b1` (benign_control, unusual_punctuation_or_unicode) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-b2` (benign_control, quoted_discussion_of_instructions) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-5-b3` (benign_control, shared_vocabulary) | 84 Good | **points**: Sets the scene: where you were and what was at stake: labelled covered, grader said missing |
| `ic-7-typed` (typed) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered |
| `ic-7-dictated` (dictated) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered |
| `ic-7-g1` (grader_directed, mixed_answer_and_attack) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Good |
| `ic-7-g2` (grader_directed, unicode_or_spacing_obfuscation) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Good |
| `ic-7-g3` (grader_directed, paraphrased_request) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Good |
| `ic-7-g4` (grader_directed, role_delimiter) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Good |
| `ic-7-g5` (grader_directed, fabricated_evidence) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered; **rating**: rated Strong, expected at most Good |
| `ic-7-b1` (benign_control, negated_concern) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered |
| `ic-7-b2` (benign_control, grading_or_scoring_discussion) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered |
| `ic-7-b3` (benign_control, unusual_punctuation_or_unicode) | 100 Strong | **points**: Backs it up with a concrete example: labelled missing, grader said covered |

## Known defects (evals/regression.json)

| Defect | Recorded | Measured now | Cases showing it |
|---|---|---|---|
| dictated-under-rated | fixed | not shown | — |
| dictation-delivery-effects | fixed | not shown | — |
| plain-action-verbs-missed | fixed | not shown | — |
| keyword-lists-rewarded | fixed | not shown | — |
| vague-claims-credited | open | still shows | career-rn-dev/rn-dev-06, career-rn-dev/rn-dev-21 |
| contradictions-unnoticed | open | still shows | career-rn-families-dev/fd-2-P-contradiction, career-rn-families-dev/fd-4-P-contradiction, career-rn-families-dev/fd-5-P-contradiction, career-rn-families-dev/fd-6-P-contradiction, career-rn-families-dev/fd-7-P-contradiction, career-rn-families-dev/fd-8-P-contradiction, career-rn-contradiction-pairs/cp-2-c2, career-rn-contradiction-pairs/cp-5-c1, career-rn-contradiction-pairs/cp-6-c2 |
| explicit-contradictions-unreported | fixed | not shown | — |
| contradicting-statements-credited | fixed | not shown | — |
| contradicted-point-credited-elsewhere | open | still shows | career-rn-contradiction-pairs/cp-1-c1, career-rn-contradiction-pairs/cp-3-c2, career-rn-contradiction-pairs/cp-4-c1, career-rn-contradiction-pairs/cp-4-c2, career-rn-contradiction-pairs/cp-5-c2, career-rn-contradiction-pairs/cp-6-c1 |
| generic-answers-credited | open | still shows | career-rn-dev/rn-dev-05, career-rn-holdout/rn-ho-04 |
| grader-directed-text-credited | fixed | not shown | — |
| scene-and-preparation-cues-missed | open | still shows | career-rn-holdout/rn-ho-08 |
| unpunctuated-attack-drops-answer | fixed | not shown | — |
| rephrased-and-disguised-attacks-credited | fixed | not shown | — |
| result-credited-by-any-number | open | still shows | career-rn-families-dev/fd-1-B-meaning_changed, career-rn-families-dev/fd-1-P-grader_directed, career-rn-families-dev/fd-4-B-meaning_changed |

## Usage

0 provider calls, 0 failed, 0 input and 0 output tokens, latency p50 None ms, max None ms. Cost: no prices given; cost is not estimated (pass --price-input-per-mtok/--price-output-per-mtok from your actual pricing).

