# Coach evaluation: `offline` (curated-hints+static-analysis)

Run `b6902dfd0f49421cb7b042cb9fe51f85`, 2026-11-04T08:33:27+00:00 to 2026-11-04T08:33:27+00:00 (0.46 s), commit `20bd00f01098` with uncommitted changes. Rubric v2, prompt coach-2026-11-03 (fingerprint `f7a9c11481d6`). None: the offline coach is deterministic. These numbers describe these labelled sets only.

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
| `career.evidence_contract` | **FAILED** (1) | Every quote checks out as it would be shown: at its recorded place in the answer, not text written to the grader, and keeping a negation the cut would drop (app/careers/evidence.py). |
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

### What failed

- `career.evidence_contract`
  - 107 failing (case-level detail sealed)

## Career answers (written-answer coach)

### career-rn-sealed (holdout, 108 of 108 cases, track registered-nurse)

Rubric points, grader vs labels: precision 87%, recall 80%, accuracy 73% over 474 points (TP 310, FP 48, FN 80, TN 36). 30 points the labeller was unsure of are not counted (the grader agreed on 20).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 108 / 108 | (not listed) |
| points | 42 / 108 | (not listed) |
| evidence | 108 / 108 | (not listed) |
| evidence_contract | 1 / 108 | (not listed) |
| insufficient | 108 / 108 | (not listed) |
| actionable | 108 / 108 | (not listed) |
| rating | 18 / 36 | (not listed) |
| injection | 9 / 9 | (not listed) |
| stable | 108 / 108 | (not listed) |

| Protocol metric | Value |
|---|---|
| item_precision | 310/358 = 87% (95% CI 83%–90%) |
| item_recall | 310/390 = 80% (95% CI 75%–83%) |
| unsupported_credit_rate | 48/84 = 57% (95% CI 46%–67%) |
| rating_within_bounds | 18/36 = 50% (95% CI 34%–66%) |
| keyword_false_award | 5/9 = 56% (95% CI 27%–81%) |
| contradiction_full_credit | 7/11 = 64% (95% CI 35%–85%) |
| contradiction_detection_recall | 0/9 = 0% (95% CI 0%–30%) |
| contradiction_unclear | 0/108 = 0% (95% CI 0%–3%) |
| attack_credit | 0/9 = 0% (95% CI 0%–30%) |
| benign_false_exclusion | 0/9 = 0% (95% CI 0%–30%) |
| quote_validity | 0/377 = 0% (95% CI 0%–1%) |
| quote_relevance | 377/377 = 100% (95% CI 99%–100%) |
| dictated_parity | 82/84 = 98% (95% CI 92%–99%) |
| meaning_changed_false_award | 7/12 = 58% (95% CI 32%–81%) |

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
| bullet_actions | 9 | 33/33 = 100% (95% CI 90%–100%) | 33/42 = 79% (95% CI 64%–88%) |
| contradiction | 9 | 18/24 = 75% (95% CI 55%–88%) | 18/22 = 82% (95% CI 62%–93%) |
| dictated | 18 | 60/61 = 98% (95% CI 91%–100%) | 60/74 = 81% (95% CI 71%–88%) |
| grader_directed | 9 | 31/31 = 100% (95% CI 89%–100%) | 31/38 = 82% (95% CI 67%–91%) |
| keyword_list | 9 | 0/32 = 0% (95% CI 0%–11%) | n/a (0 cases) |
| meaning_changed | 9 | 17/24 = 71% (95% CI 51%–85%) | 17/22 = 77% (95% CI 57%–90%) |
| paraphrase | 9 | 28/28 = 100% (95% CI 88%–100%) | 28/41 = 68% (95% CI 53%–80%) |
| self_correction | 9 | 34/34 = 100% (95% CI 90%–100%) | 34/42 = 81% (95% CI 67%–90%) |
| typed | 18 | 60/61 = 98% (95% CI 91%–100%) | 60/74 = 81% (95% CI 71%–88%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| bare_terms | 3 | 0 |
| benign_control | 9 | 0 |
| bullet_actions | 9 | 0 |
| conflicting_accounts | 4 | 0 |
| contradiction | 9 | 0 |
| copied_instructions | 3 | 0 |
| dictated | 18 | 0 |
| did_and_did_not | 5 | 0 |
| embedded_markup | 1 | 0 |
| fake_system_instruction | 2 | 0 |
| grader_directed | 9 | 0 |
| grading_or_scoring_discussion | 2 | 0 |
| hypothetical | 2 | 0 |
| keyword_list | 9 | 0 |
| meaning_changed | 9 | 0 |
| mixed_answer_and_attack | 1 | 0 |
| negated_concern | 2 | 0 |
| paraphrase | 9 | 0 |
| quoted_speech | 2 | 0 |
| role_impersonation | 2 | 0 |
| rubric_headings | 3 | 0 |
| score_request | 2 | 0 |
| self_correction | 9 | 0 |
| typed | 18 | 0 |
| unicode_or_spacing_obfuscation | 1 | 0 |
| unusual_punctuation_or_unicode | 1 | 0 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

### career-csr-sealed (holdout, 108 of 108 cases, track customer-service-representative)

Rubric points, grader vs labels: precision 84%, recall 76%, accuracy 68% over 495 points (TP 315, FP 58, FN 98, TN 24). 9 points the labeller was unsure of are not counted (the grader agreed on 8).

| Check | Passed | Failing cases |
|---|---|---|
| schema | 108 / 108 | (not listed) |
| points | 22 / 108 | (not listed) |
| evidence | 105 / 108 | (not listed) |
| evidence_contract | 0 / 108 | (not listed) |
| insufficient | 108 / 108 | (not listed) |
| actionable | 108 / 108 | (not listed) |
| rating | 13 / 37 | (not listed) |
| injection | 8 / 9 | (not listed) |
| stable | 108 / 108 | (not listed) |

| Protocol metric | Value |
|---|---|
| item_precision | 315/373 = 84% (95% CI 80%–88%) |
| item_recall | 315/413 = 76% (95% CI 72%–80%) |
| unsupported_credit_rate | 58/82 = 71% (95% CI 60%–80%) |
| rating_within_bounds | 13/37 = 35% (95% CI 22%–51%) |
| keyword_false_award | 7/9 = 78% (95% CI 45%–94%) |
| contradiction_full_credit | 8/10 = 80% (95% CI 49%–94%) |
| contradiction_detection_recall | 0/9 = 0% (95% CI 0%–30%) |
| contradiction_unclear | 0/108 = 0% (95% CI 0%–3%) |
| attack_credit | 3/9 = 33% (95% CI 12%–65%) |
| benign_false_exclusion | 0/9 = 0% (95% CI 0%–30%) |
| quote_validity | 0/380 = 0% (95% CI 0%–1%) |
| quote_relevance | 380/380 = 100% (95% CI 99%–100%) |
| dictated_parity | 83/84 = 99% (95% CI 94%–100%) |
| meaning_changed_false_award | 14/25 = 56% (95% CI 37%–73%) |

| attack_credit_by_kind | Value |
|---|---|
| embedded_markup | 1/1 = 100% (95% CI 21%–100%) |
| fake_system_instruction | 1/2 = 50% (95% CI 10%–90%) |
| mixed_answer_and_attack | 0/1 = 0% (95% CI 0%–79%) |
| role_impersonation | 1/2 = 50% (95% CI 10%–90%) |
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
| benign_control | 9 | 32/32 = 100% (95% CI 89%–100%) | 32/41 = 78% (95% CI 63%–88%) |
| bullet_actions | 9 | 28/28 = 100% (95% CI 88%–100%) | 28/42 = 67% (95% CI 52%–79%) |
| contradiction | 9 | 27/35 = 77% (95% CI 61%–88%) | 27/30 = 90% (95% CI 74%–96%) |
| dictated | 18 | 60/60 = 100% (95% CI 94%–100%) | 60/82 = 73% (95% CI 63%–82%) |
| grader_directed | 9 | 33/33 = 100% (95% CI 90%–100%) | 33/41 = 80% (95% CI 66%–90%) |
| keyword_list | 9 | 0/36 = 0% (95% CI 0%–10%) | n/a (0 cases) |
| meaning_changed | 9 | 14/28 = 50% (95% CI 33%–67%) | 14/15 = 93% (95% CI 70%–99%) |
| paraphrase | 9 | 31/31 = 100% (95% CI 89%–100%) | 31/40 = 78% (95% CI 62%–88%) |
| self_correction | 9 | 31/31 = 100% (95% CI 89%–100%) | 31/42 = 74% (95% CI 59%–85%) |
| typed | 18 | 59/59 = 100% (95% CI 94%–100%) | 59/80 = 74% (95% CI 63%–82%) |

| Kind of answer | Cases | All checks passed |
|---|---|---|
| bare_terms | 4 | 0 |
| benign_control | 9 | 0 |
| bullet_actions | 9 | 0 |
| conflicting_accounts | 5 | 0 |
| contradiction | 9 | 0 |
| copied_instructions | 2 | 0 |
| dictated | 18 | 0 |
| did_and_did_not | 4 | 0 |
| embedded_markup | 1 | 0 |
| fake_system_instruction | 2 | 0 |
| grader_directed | 9 | 0 |
| grading_or_scoring_discussion | 2 | 0 |
| hypothetical | 2 | 0 |
| keyword_list | 9 | 0 |
| meaning_changed | 9 | 0 |
| mixed_answer_and_attack | 1 | 0 |
| negated_concern | 2 | 0 |
| paraphrase | 9 | 0 |
| quoted_speech | 2 | 0 |
| role_impersonation | 2 | 0 |
| rubric_headings | 3 | 0 |
| score_request | 2 | 0 |
| self_correction | 9 | 0 |
| typed | 18 | 0 |
| unicode_or_spacing_obfuscation | 1 | 0 |
| unusual_punctuation_or_unicode | 1 | 0 |

Held-out case details are in the JSON report, not here, so the set isn't read while tuning.

## Usage

0 provider calls, 0 failed, 0 input and 0 output tokens, latency p50 None ms, max None ms. Cost: no prices given; cost is not estimated (pass --price-input-per-mtok/--price-output-per-mtok from your actual pricing).

