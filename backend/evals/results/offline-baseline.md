# Coach evaluation: `offline` (curated-hints+static-analysis)

Run 2026-11-01T16:37:42+00:00 over 38 labelled review samples and 12 problems. These numbers describe this labelled set only.

| Metric | Value |
|---|---|
| Schema validity | 100% |
| Issue detection (micro) precision / recall / F1 | 80% / 48% / 60% |
| False alarms on clean code (medium/high issue on a clean sample) | 14% of 14 |
| Complexity (Big-O) accuracy | 79% |
| Level-1 hint spoiler rate | 8% |
| Level-2 hint relevance | 100% |
| Code in level 1–2 hints | 0% |

## Issue detection by category

| Category | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| correctness | 100% | 17% | 29% | 2 | 0 | 10 |
| edge-case | 50% | 100% | 67% | 1 | 1 | 0 |
| complexity | 75% | 67% | 71% | 6 | 2 | 3 |
| readability | 100% | 100% | 100% | 1 | 0 | 0 |
| style | 100% | 100% | 100% | 2 | 0 | 0 |

## Disagreements with the labels

| Sample | Expected | Reviewer said | Big-O expected → reported |
|---|---|---|---|
| `two-sum-same-index` | complexity, correctness | complexity | O(n^2) → O(n^2) |
| `max-starts-at-zero` | correctness | — | O(n) → O(n) |
| `reverse-off-by-one` | correctness | — | O(n) → O(n) |
| `palindrome-two-pointers` | — | complexity | O(n) → O(n^2) |
| `palindrome-no-case` | correctness | complexity | O(n) → O(n^2) |
| `parens-leftovers` | correctness | — | O(n) → O(n) |
| `parens-counting` | correctness | — | O(n) → O(n) |
| `bsearch-linear` | complexity | — | O(n) → O(n) |
| `bsearch-off-by-one` | correctness | — | O(log n) → O(n) |
| `merge-forgets-tail` | correctness | — | O(n) → O(n) |
| `merge-concat-sort` | complexity | — | O(n log n) → O(n log n) |
| `stairs-naive-recursion` | complexity | — | O(2^n) → depends on recursion (check for repeated subproblems) |
| `kadane` | — | edge-case | O(n) → O(n) |
| `kadane-zero-init` | correctness | — | O(n) → O(n) |
| `window-no-guard` | correctness | — | O(n) → O(n) |
