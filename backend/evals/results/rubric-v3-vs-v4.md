# Comparison: baseline `1d67b42f283e4d34a0a1042feabf8e15` → candidate `9bd05c2045964b8a997d16cc3662c77e`

## Changed conditions

- commit: `e973e504ee89c1c96123a88a8b79fc4ee38d8387` → `2e70d0b8ed95d82ffcaa6e4e7f6cbd908d7a30ec`
- rubric_version: `v3` → `v4`
- config: `{'career_grader': 'app.careers.grading.grade (rubric v3)', 'sampling': 'none: the offline coach is deterministic'}` → `{'career_grader': 'app.careers.grading.grade (rubric v4)', 'sampling': 'none: the offline coach is deterministic'}`

## Metrics (baseline → candidate)

- **career-rn-dev**: precision 0.811 → 0.811, recall 0.968 → 0.968, schema passed 23 → 23, points passed 15 → 15, evidence passed 23 → 23, insufficient passed 23 → 23, actionable passed 23 → 23, rating passed 17 → 17, notes passed 1 → 1, injection passed 2 → 2, stable passed 23 → 23
- **career-rn-holdout**: precision 0.836 → 0.92, recall 0.885 → 0.885, schema passed 17 → 17, points passed 10 → 11, evidence passed 17 → 17, insufficient passed 17 → 17, actionable passed 17 → 17, rating passed 12 → 13, injection passed 1 → 1, stable passed 17 → 17

## Regressions (0)

- none

## Fixed (2)

- career-rn-holdout / rn-ho-12: points
- career-rn-holdout / rn-ho-12: rating

