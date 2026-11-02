# Coach evaluation: `offline` (curated-hints+static-analysis)

Run 2026-11-02T08:55:18+00:00 over 38 labelled review samples and 300 problems (hint spoiler and relevance rates on the 22 with labeled terms; code-leak checks on all). These numbers describe this labelled set only.

## Tuning set

| Metric | Value |
|---|---|
| Schema validity | 100% |
| Issue detection (micro) precision / recall / F1 | 100% / 60% / 75% |
| False alarms on clean code (medium/high issue on a clean sample) | 0% of 14 |
| Complexity (Big-O) accuracy | 95% |
| Level-1 hint spoiler rate | 0% |
| Level-2 hint relevance | 100% |
| Code in level 1–2 hints | 0% |

## Held-out set (generalisation)

14 samples written after the rules were frozen; never used to tune them.

| Metric | Value |
|---|---|
| Issue detection (micro) precision / recall / F1 | 80% / 50% / 62% |
| False alarms on clean code | 17% of 6 |
| Complexity (Big-O) accuracy | 50% |

| Sample | Expected | Reviewer said | Big-O expected → reported |
|---|---|---|---|
| `ho-max-min-value` | edge-case | — | O(n) → O(n) |
| `ho-reverse-recursive` | complexity | — | O(n^2) → depends on recursion (check for repeated subproblems) |
| `ho-parens-replace` | complexity | — | O(n^2) → O(n) |
| `ho-unique-map-order-bug` | correctness | — | O(n) → O(n) |
| `ho-window-set` | — | complexity | O(n) → O(n^2) |

## Medium held-out set (newer problems)

14 samples written after the rules were frozen; never used to tune them.

| Metric | Value |
|---|---|
| Issue detection (micro) precision / recall / F1 | 100% / 50% / 67% |
| False alarms on clean code | 0% of 4 |
| Complexity (Big-O) accuracy | 86% |

| Sample | Expected | Reviewer said | Big-O expected → reported |
|---|---|---|---|
| `md-product-division` | correctness | — | O(n) → O(n) |
| `md-rotated-strict-loop` | correctness | — | O(log n) → O(log n) |
| `md-coin-greedy` | correctness | — | O(k log k) → O(n log n) |
| `md-decode-no-zero-check` | edge-case | — | O(n) → O(n) |
| `md-kth-sort` | complexity | — | O(n log n) → O(n log n) |

## Issue detection by category (tuning set)

| Category | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| correctness | 100% | 17% | 29% | 2 | 0 | 10 |
| edge-case | 100% | 100% | 100% | 1 | 0 | 0 |
| complexity | 100% | 100% | 100% | 9 | 0 | 0 |
| readability | 100% | 100% | 100% | 1 | 0 | 0 |
| style | 100% | 100% | 100% | 2 | 0 | 0 |

## Disagreements with the labels

| Sample | Expected | Reviewer said | Big-O expected → reported |
|---|---|---|---|
| `two-sum-same-index` | complexity, correctness | complexity | O(n^2) → O(n^2) |
| `max-starts-at-zero` | correctness | — | O(n) → O(n) |
| `reverse-off-by-one` | correctness | — | O(n) → O(n) |
| `palindrome-no-case` | correctness | — | O(n) → O(n) |
| `parens-leftovers` | correctness | — | O(n) → O(n) |
| `parens-counting` | correctness | — | O(n) → O(n) |
| `bsearch-off-by-one` | correctness | — | O(log n) → O(log n) |
| `merge-forgets-tail` | correctness | — | O(n) → O(n) |
| `kadane-zero-init` | correctness | — | O(n) → O(n) |
| `window-no-guard` | correctness | — | O(n) → O(n) |
