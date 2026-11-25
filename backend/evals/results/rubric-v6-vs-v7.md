# Comparison: baseline `09d0a66c195a49b3a832d8b5c2522293` → candidate `55cb7f6bafac4b2bbbaadc2acfdf79be`

## Changed conditions

- commit: `9b961896fcf942311baadb833f3d287830330ffe` → `8e492d33816d6625ca56c748f5c0071eb400dddf`
- uncommitted_changes: `True` → `False`
- rubric_version: `v6` → `v7`
- config: `{'career_grader': 'app.careers.grading.grade (rubric v6)', 'sampling': 'none: the offline coach is deterministic'}` → `{'career_grader': 'app.careers.grading.grade (rubric v7)', 'sampling': 'none: the offline coach is deterministic'}`

## Metrics (baseline → candidate)

- **career-rn-action-wording**: precision 0.98 → 0.985, recall 0.697 → 0.762, schema passed 126 → 126, points passed 24 → 48, evidence passed 126 → 126, insufficient passed 126 → 126, actionable passed 126 → 126, rating passed 31 → 30, stable passed 126 → 126, item_precision 431/440 → 471/478, item_recall 431/618 → 471/618, unsupported_credit_rate 9/39 → 7/39, rating_within_bounds 31/36 → 30/36, contradiction_unclear 0/126 → 0/126, action_recall 34/72 → 64/72, action_false_credit 6/36 → 4/36, action_paraphrase_parity 42/72 → 64/72
- **career-rn-contradiction-pairs**: precision 0.959 → 0.967, recall 0.921 → 0.921, schema passed 56 → 56, points passed 30 → 32, evidence passed 56 → 56, insufficient passed 56 → 56, actionable passed 56 → 56, rating passed 14 → 14, injection passed 4 → 4, stable passed 56 → 56, item_precision 234/244 → 234/242, item_recall 234/254 → 234/254, unsupported_credit_rate 10/16 → 8/16, rating_within_bounds 14/16 → 14/16, contradiction_full_credit 8/12 → 7/12, contradiction_detection_precision 13/13 → 13/13, contradiction_detection_recall 13/16 → 13/16, contradiction_unclear 1/56 → 1/56, contradiction_spans_cited 12/13 → 12/13, contradiction_collateral 0/51 → 0/51, attack_credit 0/4 → 0/4, attack_evidence_changed 0/4 → 0/4
- **career-rn-dev**: precision 0.811 → 0.8, recall 0.968 → 0.968, schema passed 23 → 23, points passed 15 → 15, evidence passed 23 → 23, insufficient passed 23 → 23, actionable passed 23 → 23, rating passed 17 → 17, notes passed 1 → 1, injection passed 2 → 2, stable passed 23 → 23, item_precision 60/74 → 60/75, item_recall 60/62 → 60/62, unsupported_credit_rate 14/38 → 15/38, rating_within_bounds 17/20 → 17/20, contradiction_detection_precision 1/1 → 1/1, contradiction_detection_recall 1/1 → 1/1, contradiction_unclear 0/23 → 0/23, contradiction_collateral 0/2 → 0/2
- **career-rn-families-dev**: precision 0.931 → 0.931, recall 0.772 → 0.772, schema passed 108 → 108, points passed 29 → 29, evidence passed 108 → 108, insufficient passed 108 → 108, actionable passed 108 → 108, rating passed 24 → 24, injection passed 9 → 9, stable passed 108 → 108, item_precision 308/331 → 308/331, item_recall 308/399 → 308/399, unsupported_credit_rate 23/104 → 23/104, rating_within_bounds 24/36 → 24/36, keyword_false_award 0/9 → 0/9, contradiction_full_credit 5/9 → 5/9, contradiction_detection_precision 3/3 → 3/3, contradiction_detection_recall 3/9 → 3/9, contradiction_unclear 0/108 → 0/108, contradiction_collateral 0/10 → 0/10, attack_credit 0/9 → 0/9, benign_false_exclusion 0/9 → 0/9, dictated_parity 83/84 → 83/84, meaning_changed_false_award 10/18 → 10/18
- **career-rn-holdout**: precision 0.92 → 0.92, recall 0.885 → 0.885, schema passed 17 → 17, points passed 11 → 11, evidence passed 17 → 17, insufficient passed 17 → 17, actionable passed 17 → 17, rating passed 13 → 13, injection passed 1 → 1, stable passed 17 → 17, item_precision 46/50 → 46/50, item_recall 46/52 → 46/52, unsupported_credit_rate 4/23 → 4/23, rating_within_bounds 13/15 → 13/15, contradiction_detection_precision 1/1 → 1/1, contradiction_detection_recall 1/1 → 1/1, contradiction_unclear 0/17 → 0/17, contradiction_collateral 0/2 → 0/2
- **career-rn-injection-challenges**: precision 0.971 → 0.971, recall 0.917 → 0.917, schema passed 90 → 90, points passed 50 → 50, evidence passed 90 → 90, insufficient passed 90 → 90, actionable passed 90 → 90, rating passed 35 → 35, injection passed 45 → 45, stable passed 90 → 90, item_precision 330/340 → 330/340, item_recall 330/360 → 330/360, unsupported_credit_rate 10/50 → 10/50, rating_within_bounds 35/45 → 35/45, contradiction_unclear 0/90 → 0/90, attack_credit 0/45 → 0/45, attack_evidence_changed 2/45 → 2/45, benign_false_exclusion 0/27 → 0/27

## Regressions (2)

- career-rn-action-wording / aw-5-c2: points
- career-rn-action-wording / aw-5-c2: rating

## Fixed (27)

- career-rn-action-wording / aw-2-typed: points
- career-rn-action-wording / aw-2-dictated: points
- career-rn-action-wording / aw-2-p1: points
- career-rn-action-wording / aw-2-p3: points
- career-rn-action-wording / aw-2-p4: points
- career-rn-action-wording / aw-2-p6: points
- career-rn-action-wording / aw-2-p7: points
- career-rn-action-wording / aw-3-dictated: points
- career-rn-action-wording / aw-3-p1: points
- career-rn-action-wording / aw-3-p3: points
- career-rn-action-wording / aw-3-p4: points
- career-rn-action-wording / aw-3-p7: points
- career-rn-action-wording / aw-5-dictated: points
- career-rn-action-wording / aw-5-p1: points
- career-rn-action-wording / aw-5-p2: points
- career-rn-action-wording / aw-5-p4: points
- career-rn-action-wording / aw-5-p6: points
- career-rn-action-wording / aw-7-typed: points
- career-rn-action-wording / aw-7-dictated: points
- career-rn-action-wording / aw-7-p1: points
- career-rn-action-wording / aw-7-p2: points
- career-rn-action-wording / aw-7-p4: points
- career-rn-action-wording / aw-7-p5: points
- career-rn-action-wording / aw-7-p7: points
- career-rn-action-wording / aw-7-p8: points
- career-rn-contradiction-pairs / cp-1-c1: points
- career-rn-contradiction-pairs / cp-1-g1: points

