# Comparison: baseline `55f602d53bca41d68ee125db2095bae2` → candidate `6750c68ff9b246ce81494fca5936cd55`

## Changed conditions

- rubric_version: `v4` → `v5`
- config: `{'career_grader': 'git 8db564c:backend/app/careers/grading.py (sha256 e5a590d20ea7980a)', 'sampling': 'none: the offline coach is deterministic'}` → `{'career_grader': 'app.careers.grading.grade (rubric v5)', 'sampling': 'none: the offline coach is deterministic'}`

## Metrics (baseline → candidate)

- **career-rn-contradiction-pairs**: precision 0.947 → 0.959, recall 0.921 → 0.921, schema passed 56 → 56, points passed 27 → 30, evidence passed 56 → 56, insufficient passed 56 → 56, actionable passed 56 → 56, rating passed 7 → 14, injection passed 4 → 4, stable passed 56 → 56, item_precision 234/247 → 234/244, item_recall 234/254 → 234/254, unsupported_credit_rate 13/16 → 10/16, rating_within_bounds 7/16 → 14/16, contradiction_full_credit 10/12 → 8/12, contradiction_detection_precision 0/0 → 13/13, contradiction_detection_recall 0/16 → 13/16, contradiction_unclear 0/56 → 1/56, contradiction_spans_cited 0/0 → 12/13, contradiction_collateral 0/0 → 0/51, attack_credit 0/4 → 0/4
- **career-rn-dev**: precision 0.811 → 0.811, recall 0.968 → 0.968, schema passed 23 → 23, points passed 15 → 15, evidence passed 23 → 23, insufficient passed 23 → 23, actionable passed 23 → 23, rating passed 17 → 17, notes passed 1 → 1, injection passed 2 → 2, stable passed 23 → 23, item_precision 60/74 → 60/74, item_recall 60/62 → 60/62, unsupported_credit_rate 14/38 → 14/38, rating_within_bounds 17/20 → 17/20, contradiction_detection_precision 0/0 → 1/1, contradiction_detection_recall 0/1 → 1/1, contradiction_unclear 0/23 → 0/23, contradiction_collateral 0/0 → 0/2
- **career-rn-families-dev**: precision 0.925 → 0.931, recall 0.772 → 0.772, schema passed 108 → 108, points passed 28 → 29, evidence passed 107 → 107, insufficient passed 107 → 107, actionable passed 108 → 108, rating passed 24 → 24, injection passed 8 → 8, stable passed 108 → 108, item_precision 308/333 → 308/331, item_recall 308/399 → 308/399, unsupported_credit_rate 25/104 → 23/104, rating_within_bounds 24/36 → 24/36, keyword_false_award 0/9 → 0/9, contradiction_full_credit 7/9 → 5/9, contradiction_detection_precision 0/0 → 3/3, contradiction_detection_recall 0/9 → 3/9, contradiction_unclear 0/108 → 0/108, contradiction_collateral 0/0 → 0/10, attack_credit 1/9 → 1/9, benign_false_exclusion 0/9 → 0/9, dictated_parity 83/84 → 83/84, meaning_changed_false_award 10/18 → 10/18
- **career-rn-holdout**: precision 0.92 → 0.92, recall 0.885 → 0.885, schema passed 17 → 17, points passed 11 → 11, evidence passed 17 → 17, insufficient passed 17 → 17, actionable passed 17 → 17, rating passed 13 → 13, injection passed 1 → 1, stable passed 17 → 17, item_precision 46/50 → 46/50, item_recall 46/52 → 46/52, unsupported_credit_rate 4/23 → 4/23, rating_within_bounds 13/15 → 13/15, contradiction_detection_precision 0/0 → 1/1, contradiction_detection_recall 0/1 → 1/1, contradiction_unclear 0/17 → 0/17, contradiction_collateral 0/0 → 0/2

## Regressions (0)

- none

## Fixed (11)

- career-rn-contradiction-pairs / cp-1-c1: rating
- career-rn-contradiction-pairs / cp-1-c2: points
- career-rn-contradiction-pairs / cp-1-c2: rating
- career-rn-contradiction-pairs / cp-1-g1: rating
- career-rn-contradiction-pairs / cp-3-c1: points
- career-rn-contradiction-pairs / cp-3-c1: rating
- career-rn-contradiction-pairs / cp-3-c2: rating
- career-rn-contradiction-pairs / cp-3-g1: points
- career-rn-contradiction-pairs / cp-3-g1: rating
- career-rn-contradiction-pairs / cp-6-c1: rating
- career-rn-families-dev / fd-9-P-contradiction: points

