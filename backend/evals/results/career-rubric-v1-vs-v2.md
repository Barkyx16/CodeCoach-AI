# Comparison: baseline `18fd2fa31d064289ae5f661d0e39604d` → candidate `92d5e8da758245b1a68ecb472c72d854`

## Changed conditions

- rubric_version: `v1` → `v2`
- config: `{'career_grader': 'git 58d52ec:backend/app/careers/grading.py (sha256 e60a6abc877b6e9d)', 'sampling': 'none: the offline coach is deterministic'}` → `{'career_grader': 'app.careers.grading.grade (rubric v2)', 'sampling': 'none: the offline coach is deterministic'}`

## Metrics (baseline → candidate)

- **career-rn-dev**: precision 0.753 → 0.806, recall 0.935 → 0.935, schema passed 23 → 23, points passed 12 → 13, evidence passed 20 → 23, insufficient passed 22 → 23, actionable passed 23 → 23, rating passed 15 → 17, notes passed 1 → 1, injection passed 0 → 2, stable passed 23 → 23
- **career-rn-holdout**: precision 0.815 → 0.83, recall 0.846 → 0.846, schema passed 17 → 17, points passed 8 → 9, evidence passed 15 → 17, insufficient passed 16 → 17, actionable passed 17 → 17, rating passed 12 → 12, injection passed 0 → 1, stable passed 17 → 17

## Regressions (0)

- none

## Fixed (14)

- career-rn-dev / rn-dev-10: evidence
- career-rn-dev / rn-dev-10: injection
- career-rn-dev / rn-dev-10: insufficient
- career-rn-dev / rn-dev-10: rating
- career-rn-dev / rn-dev-11: evidence
- career-rn-dev / rn-dev-23: evidence
- career-rn-dev / rn-dev-23: injection
- career-rn-dev / rn-dev-23: points
- career-rn-dev / rn-dev-23: rating
- career-rn-holdout / rn-ho-06: evidence
- career-rn-holdout / rn-ho-06: injection
- career-rn-holdout / rn-ho-06: insufficient
- career-rn-holdout / rn-ho-06: points
- career-rn-holdout / rn-ho-08: evidence

