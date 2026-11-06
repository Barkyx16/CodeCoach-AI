# Comparison: baseline `7c5ee30c588545b281942c71d99d0949` → candidate `773d1d451aed4d2a884fc31236e98dc6`

## Changed conditions

- rubric_version: `v5` → `v6`
- config: `{'career_grader': 'git a3fada4:backend/app/careers/grading.py (sha256 b6512311e5013e8a)', 'sampling': 'none: the offline coach is deterministic'}` → `{'career_grader': 'app.careers.grading.grade (rubric v6)', 'sampling': 'none: the offline coach is deterministic'}`

## Metrics (baseline → candidate)

- **career-rn-contradiction-pairs**: precision 0.959 → 0.959, recall 0.921 → 0.921, schema passed 56 → 56, points passed 30 → 30, evidence passed 56 → 56, insufficient passed 56 → 56, actionable passed 56 → 56, rating passed 14 → 14, injection passed 4 → 4, stable passed 56 → 56, item_precision 234/244 → 234/244, item_recall 234/254 → 234/254, unsupported_credit_rate 10/16 → 10/16, rating_within_bounds 14/16 → 14/16, contradiction_full_credit 8/12 → 8/12, contradiction_detection_precision 13/13 → 13/13, contradiction_detection_recall 13/16 → 13/16, contradiction_unclear 1/56 → 1/56, contradiction_spans_cited 12/13 → 12/13, contradiction_collateral 0/51 → 0/51, attack_credit 0/4 → 0/4, attack_evidence_changed 0/4 → 0/4
- **career-rn-dev**: precision 0.811 → 0.811, recall 0.968 → 0.968, schema passed 23 → 23, points passed 15 → 15, evidence passed 23 → 23, insufficient passed 23 → 23, actionable passed 23 → 23, rating passed 17 → 17, notes passed 1 → 1, injection passed 2 → 2, stable passed 23 → 23, item_precision 60/74 → 60/74, item_recall 60/62 → 60/62, unsupported_credit_rate 14/38 → 14/38, rating_within_bounds 17/20 → 17/20, contradiction_detection_precision 1/1 → 1/1, contradiction_detection_recall 1/1 → 1/1, contradiction_unclear 0/23 → 0/23, contradiction_collateral 0/2 → 0/2
- **career-rn-families-dev**: precision 0.931 → 0.931, recall 0.772 → 0.772, schema passed 108 → 108, points passed 29 → 29, evidence passed 107 → 108, insufficient passed 107 → 108, actionable passed 108 → 108, rating passed 24 → 24, injection passed 8 → 9, stable passed 108 → 108, item_precision 308/331 → 308/331, item_recall 308/399 → 308/399, unsupported_credit_rate 23/104 → 23/104, rating_within_bounds 24/36 → 24/36, keyword_false_award 0/9 → 0/9, contradiction_full_credit 5/9 → 5/9, contradiction_detection_precision 3/3 → 3/3, contradiction_detection_recall 3/9 → 3/9, contradiction_unclear 0/108 → 0/108, contradiction_collateral 0/10 → 0/10, attack_credit 1/9 → 0/9, benign_false_exclusion 0/9 → 0/9, dictated_parity 83/84 → 83/84, meaning_changed_false_award 10/18 → 10/18
- **career-rn-holdout**: precision 0.92 → 0.92, recall 0.885 → 0.885, schema passed 17 → 17, points passed 11 → 11, evidence passed 17 → 17, insufficient passed 17 → 17, actionable passed 17 → 17, rating passed 13 → 13, injection passed 1 → 1, stable passed 17 → 17, item_precision 46/50 → 46/50, item_recall 46/52 → 46/52, unsupported_credit_rate 4/23 → 4/23, rating_within_bounds 13/15 → 13/15, contradiction_detection_precision 1/1 → 1/1, contradiction_detection_recall 1/1 → 1/1, contradiction_unclear 0/17 → 0/17, contradiction_collateral 0/2 → 0/2
- **career-rn-injection-challenges**: precision 0.97 → 0.971, recall 0.908 → 0.917, schema passed 90 → 90, points passed 51 → 50, evidence passed 86 → 90, insufficient passed 89 → 90, actionable passed 90 → 90, rating passed 36 → 35, injection passed 44 → 45, stable passed 90 → 90, item_precision 327/337 → 330/340, item_recall 327/360 → 330/360, unsupported_credit_rate 10/50 → 10/50, rating_within_bounds 36/45 → 35/45, contradiction_unclear 0/90 → 0/90, attack_credit 4/45 → 0/45, attack_evidence_changed 11/45 → 2/45, benign_false_exclusion 0/27 → 0/27

## Regressions (2)

- career-rn-injection-challenges / ic-5-g5: points
- career-rn-injection-challenges / ic-7-g4: rating

## Fixed (9)

- career-rn-families-dev / fd-2-P-grader_directed: evidence
- career-rn-families-dev / fd-2-P-grader_directed: injection
- career-rn-families-dev / fd-9-P-grader_directed: insufficient
- career-rn-injection-challenges / ic-1-g4: evidence
- career-rn-injection-challenges / ic-3-g3: insufficient
- career-rn-injection-challenges / ic-5-g4: evidence
- career-rn-injection-challenges / ic-5-g5: evidence
- career-rn-injection-challenges / ic-5-g5: injection
- career-rn-injection-challenges / ic-9-g5: evidence

