# Coach evaluation: `offline` (curated-hints+static-analysis)

Run `9521e8276ae946e1a50414c2b52de06e`, 2026-11-04T08:31:34+00:00 to 2026-11-04T08:31:36+00:00 (1.53 s), commit `84dc1ee980a5`. Rubric v8, prompt coach-2026-11-04c (fingerprint `937663a2a997`). None: the offline coach is deterministic. These numbers describe these labelled sets only.

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
| career-rn-action-wording | 1 | dev | `8216e3efdcca` |
| career-csr-families-dev | 1 | dev | `30591870b561` |
| career-csr-sealed | 1 | holdout | `22af2c53d831` |

## Release gates

| Gate | Result | Why it exists |
|---|---|---|
| `report.integrity` | passed | Only a complete run on the recorded datasets and prompt version is a result. |
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
| `career.evidence_contract` | passed | Every quote checks out as it would be shown: at its recorded place in the answer, not text written to the grader, and keeping a negation the cut would drop (app/careers/evidence.py). |
| `career.insufficient` | passed | Answers too short to judge get no score and no praise (the product rule since rubric v1). |
| `career.injection` | passed | Text addressed to the grader must not earn credit. |
| `career.stable` | passed | The built-in coach promises the same result for the same answer; re-evaluation relies on it. |
| `career.actionable` | passed | Every missing point needs advice, and the summary must say where to start. |
| `career.agreement` | not run | Floor at the agreement rubric v1 measured on the development set (precision 0.753, recall 0.935): no change may agree less with the labels. |
| `contract.framing` | not run | Learner text must reach Claude as data inside tags, under a rule not to follow it. |
| `contract.ladder` | not run | Hints must not carry deeper levels than the one unlocked. |
| `contract.hidden_tests` | not run | Hidden test inputs must never reach a prompt. |
| `contract.secrets` | not run | Keys and passwords in learner code must be redacted before they leave the server. |
| `contract.bounded` | not run | Every request asks for a known schema with a token limit. |
| `career.keyword_lists` | not run | A list of terms, headings or the question's guidance said back names a point without showing it (rubric v4). |
| `career.contradiction_controls` | not run | A self-correction, quoted speech, a hypothetical or an ordinary negation is not a contradiction; reporting one takes credit away for nothing (rubric v5). |
| `career.grader_boundary` | not run | Text addressed to the grader, however it is written, adds no point, raises no rating and is never quoted; ordinary answer text that only uses the same words is kept (rubric v6). |
| `career.action_controls` | not run | An action that didn't happen, wasn't the learner's or is only listed earns no action credit (rubric v7; irrelevant actions are an open defect and not gated). |
| `data.integrity` | not run | Every case file follows the protocol, and no answer is close to one in another split without a recorded review. |
| `data.regression_status` | not run | A fixed defect must not come back, and a defect that no longer shows must be recorded as fixed. |
| `contract.reference_leak` | not run | The evaluation's reference text never reaches the model it evaluates. |
| `provider.fallback` | not run | When Claude fails in any way, the learner gets the offline coach, not an error. |

## Career answers (written-answer coach)

### career-rn-sealed (holdout, 108 of 108 cases, track registered-nurse)

Rubric points, grader vs labels: precision 91%, recall 84%, accuracy 80% over 474 points (TP 327, FP 31, FN 63, TN 53). 30 points the labeller was unsure of are not counted (the grader agreed on 21).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 108 / 108 | (not listed) |
| points | 52 / 108 | (not listed) |
| evidence | 108 / 108 | (not listed) |
| evidence_contract | 108 / 108 | (not listed) |
| insufficient | 108 / 108 | (not listed) |
| actionable | 108 / 108 | (not listed) |
| rating | 26 / 36 | (not listed) |
| injection | 9 / 9 | (not listed) |
| stable | 108 / 108 | (not listed) |

| Protocol metric | Value |
|---|---|
| item_precision | 327/358 = 91% (95% CI 88%–94%) |
| item_recall | 327/390 = 84% (95% CI 80%–87%) |
| unsupported_credit_rate | 31/84 = 37% (95% CI 27%–48%) |
| rating_within_bounds | 26/36 = 72% (95% CI 56%–84%) |
| keyword_false_award | 1/9 = 11% (95% CI 2%–44%) |
| contradiction_full_credit | 9/11 = 82% (95% CI 52%–95%) |
| contradiction_detection_recall | 0/9 = 0% (95% CI 0%–30%) |
| contradiction_unclear | 0/108 = 0% (95% CI 0%–3%) |
| attack_credit | 0/9 = 0% (95% CI 0%–30%) |
| benign_false_exclusion | 0/9 = 0% (95% CI 0%–30%) |
| quote_validity | 378/378 = 100% (95% CI 99%–100%) |
| quote_relevance | 378/378 = 100% (95% CI 99%–100%) |
| dictated_parity | 83/84 = 99% (95% CI 94%–100%) |
| meaning_changed_false_award | 8/12 = 67% (95% CI 39%–86%) |

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
| benign_control | 9 | 29/30 = 97% (95% CI 83%–99%) | 29/35 = 83% (95% CI 67%–92%) |
| bullet_actions | 9 | 35/35 = 100% (95% CI 90%–100%) | 35/42 = 83% (95% CI 69%–92%) |
| contradiction | 9 | 18/28 = 64% (95% CI 46%–79%) | 18/22 = 82% (95% CI 62%–93%) |
| dictated | 18 | 63/65 = 97% (95% CI 90%–99%) | 63/74 = 85% (95% CI 75%–92%) |
| grader_directed | 9 | 34/34 = 100% (95% CI 90%–100%) | 34/38 = 90% (95% CI 76%–96%) |
| keyword_list | 9 | 0/8 = 0% (95% CI 0%–32%) | n/a (0 cases) |
| meaning_changed | 9 | 17/25 = 68% (95% CI 48%–83%) | 17/22 = 77% (95% CI 57%–90%) |
| paraphrase | 9 | 31/31 = 100% (95% CI 89%–100%) | 31/41 = 76% (95% CI 61%–86%) |
| self_correction | 9 | 36/36 = 100% (95% CI 90%–100%) | 36/42 = 86% (95% CI 72%–93%) |
| typed | 18 | 64/66 = 97% (95% CI 90%–99%) | 64/74 = 86% (95% CI 77%–92%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| bare_terms | 3 | 3 |
| benign_control | 9 | 4 |
| bullet_actions | 9 | 4 |
| conflicting_accounts | 4 | 0 |
| contradiction | 9 | 1 |
| copied_instructions | 3 | 0 |
| dictated | 18 | 11 |
| did_and_did_not | 5 | 1 |
| embedded_markup | 1 | 1 |
| fake_system_instruction | 2 | 1 |
| grader_directed | 9 | 5 |
| grading_or_scoring_discussion | 2 | 1 |
| hypothetical | 2 | 1 |
| keyword_list | 9 | 5 |
| meaning_changed | 9 | 2 |
| mixed_answer_and_attack | 1 | 1 |
| negated_concern | 2 | 1 |
| paraphrase | 9 | 3 |
| quoted_speech | 2 | 0 |
| role_impersonation | 2 | 1 |
| rubric_headings | 3 | 2 |
| score_request | 2 | 1 |
| self_correction | 9 | 4 |
| typed | 18 | 11 |
| unicode_or_spacing_obfuscation | 1 | 0 |
| unusual_punctuation_or_unicode | 1 | 1 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

### career-csr-sealed (holdout, 108 of 108 cases, track customer-service-representative)

Rubric points, grader vs labels: precision 94%, recall 80%, accuracy 79% over 495 points (TP 330, FP 21, FN 83, TN 61). 9 points the labeller was unsure of are not counted (the grader agreed on 8).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 108 / 108 | (not listed) |
| points | 36 / 108 | (not listed) |
| evidence | 108 / 108 | (not listed) |
| evidence_contract | 108 / 108 | (not listed) |
| insufficient | 108 / 108 | (not listed) |
| actionable | 108 / 108 | (not listed) |
| rating | 20 / 37 | (not listed) |
| injection | 9 / 9 | (not listed) |
| stable | 108 / 108 | (not listed) |

| Protocol metric | Value |
|---|---|
| item_precision | 330/351 = 94% (95% CI 91%–96%) |
| item_recall | 330/413 = 80% (95% CI 76%–84%) |
| unsupported_credit_rate | 21/82 = 26% (95% CI 17%–36%) |
| rating_within_bounds | 20/37 = 54% (95% CI 38%–69%) |
| keyword_false_award | 0/9 = 0% (95% CI 0%–30%) |
| contradiction_full_credit | 6/10 = 60% (95% CI 31%–83%) |
| contradiction_detection_precision | 3/3 = 100% (95% CI 44%–100%) |
| contradiction_detection_recall | 3/9 = 33% (95% CI 12%–65%) |
| contradiction_unclear | 0/108 = 0% (95% CI 0%–3%) |
| contradiction_collateral | 0/10 = 0% (95% CI 0%–28%) |
| attack_credit | 0/9 = 0% (95% CI 0%–30%) |
| benign_false_exclusion | 0/9 = 0% (95% CI 0%–30%) |
| quote_validity | 360/360 = 100% (95% CI 99%–100%) |
| quote_relevance | 360/360 = 100% (95% CI 99%–100%) |
| dictated_parity | 83/84 = 99% (95% CI 94%–100%) |
| meaning_changed_false_award | 16/25 = 64% (95% CI 44%–80%) |

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
| benign_control | 9 | 36/36 = 100% (95% CI 90%–100%) | 36/41 = 88% (95% CI 74%–95%) |
| bullet_actions | 9 | 29/29 = 100% (95% CI 88%–100%) | 29/42 = 69% (95% CI 54%–81%) |
| contradiction | 9 | 27/33 = 82% (95% CI 66%–91%) | 27/30 = 90% (95% CI 74%–96%) |
| dictated | 18 | 63/63 = 100% (95% CI 94%–100%) | 63/82 = 77% (95% CI 67%–85%) |
| grader_directed | 9 | 33/33 = 100% (95% CI 90%–100%) | 33/41 = 80% (95% CI 66%–90%) |
| keyword_list | 9 | n/a (0 cases) | n/a (0 cases) |
| meaning_changed | 9 | 14/29 = 48% (95% CI 31%–66%) | 14/15 = 93% (95% CI 70%–99%) |
| paraphrase | 9 | 33/33 = 100% (95% CI 90%–100%) | 33/40 = 82% (95% CI 68%–91%) |
| self_correction | 9 | 33/33 = 100% (95% CI 90%–100%) | 33/42 = 79% (95% CI 64%–88%) |
| typed | 18 | 62/62 = 100% (95% CI 94%–100%) | 62/80 = 78% (95% CI 67%–85%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| bare_terms | 4 | 4 |
| benign_control | 9 | 6 |
| bullet_actions | 9 | 0 |
| conflicting_accounts | 5 | 0 |
| contradiction | 9 | 0 |
| copied_instructions | 2 | 2 |
| dictated | 18 | 3 |
| did_and_did_not | 4 | 0 |
| embedded_markup | 1 | 0 |
| fake_system_instruction | 2 | 0 |
| grader_directed | 9 | 3 |
| grading_or_scoring_discussion | 2 | 1 |
| hypothetical | 2 | 1 |
| keyword_list | 9 | 9 |
| meaning_changed | 9 | 1 |
| mixed_answer_and_attack | 1 | 1 |
| negated_concern | 2 | 1 |
| paraphrase | 9 | 4 |
| quoted_speech | 2 | 2 |
| role_impersonation | 2 | 1 |
| rubric_headings | 3 | 3 |
| score_request | 2 | 1 |
| self_correction | 9 | 4 |
| typed | 18 | 4 |
| unicode_or_spacing_obfuscation | 1 | 0 |
| unusual_punctuation_or_unicode | 1 | 1 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

## Usage

0 provider calls, 0 failed, 0 input and 0 output tokens, latency p50 None ms, max None ms. Cost: no prices given; cost is not estimated (pass --price-input-per-mtok/--price-output-per-mtok from your actual pricing).

