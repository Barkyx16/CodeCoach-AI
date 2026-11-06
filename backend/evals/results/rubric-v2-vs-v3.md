# Comparison: baseline `55f0ad410f0641dab9c16c14b77fbef1` → candidate `1d67b42f283e4d34a0a1042feabf8e15`

## Changed conditions

- commit: `c07d3f8514a1fa2e1992f824fcd43e90776d03e3` → `e973e504ee89c1c96123a88a8b79fc4ee38d8387`
- rubric_version: `v2` → `v3`
- config: `{'career_grader': 'app.careers.grading.grade (rubric v2)', 'sampling': 'none: the offline coach is deterministic'}` → `{'career_grader': 'app.careers.grading.grade (rubric v3)', 'sampling': 'none: the offline coach is deterministic'}`

## Metrics (baseline → candidate)

- **career-rn-dev**: precision 0.806 → 0.811, recall 0.935 → 0.968, schema passed 23 → 23, points passed 13 → 15, evidence passed 23 → 23, insufficient passed 23 → 23, actionable passed 23 → 23, rating passed 17 → 17, notes passed 1 → 1, injection passed 2 → 2, stable passed 23 → 23
- **career-rn-holdout**: precision 0.83 → 0.836, recall 0.846 → 0.885, schema passed 17 → 17, points passed 9 → 10, evidence passed 17 → 17, insufficient passed 17 → 17, actionable passed 17 → 17, rating passed 12 → 12, injection passed 1 → 1, stable passed 17 → 17

## Regressions (0)

- none

## Fixed (3)

- career-rn-dev / rn-dev-09: points
- career-rn-dev / rn-dev-11: points
- career-rn-holdout / rn-ho-07: points

