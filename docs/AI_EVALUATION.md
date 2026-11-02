# CodeCoach AI — Evaluating the AI Coach

The blueprint's rule: *"Record results before claiming accuracy."* This is how the coach is
measured, what the numbers are, and what they do **not** mean.

## What's measured

`backend/evals/run.py` scores any coach provider (offline today; Claude when an API key is
configured) against hand-labelled data:

| Area | Metric | How |
|---|---|---|
| Code review | Issue-detection precision / recall / F1 | Per category (`correctness`, `edge-case`, `complexity`, `readability`, `style`) and micro-averaged, against labels |
| Code review | False alarms on clean code | Share of samples labelled *clean* where the reviewer reported a medium/high issue (a "hallucinated defect" proxy) |
| Code review | Big-O accuracy | Reviewer's time complexity vs. the labelled complexity |
| Code review | Schema validity | Every response parses as a `CodeReview` |
| Hints | Level-1 spoiler rate | Nudges containing a give-away term from `evals/hint_terms.json` (whole-word match) |
| Hints | Level-2 relevance | Concept hints that mention the key idea |
| Hints | Code leak rate | Level 1–2 hints containing Java code |

## The data

- **`evals/review_set.json`**: 38 samples across the original 12 problems: optimal solutions, correct
  but slow ones, logic bugs, edge-case bugs, and style problems. Each has an issue-category
  label, a Big-O label and an expected verdict.
- **`evals/holdout_set.json`**: 14 samples written **after** the analyzer rules were tuned on
  the first set and never used to change them. This is the generalization number.
- **`evals/medium_set.json`**: 14 samples on the 10 medium problems added in session 5, written
  **after** the session-5 rules below and never used to change them (a second held-out set).
- **The labels are verified, not assumed.** Every sample in all three sets is submitted to the
  *real* judge (API → worker → runner → gVisor), and its `PASSED`/`FAILED` verdict label must
  match (`backend/tests/test_judge_sandbox.py::test_eval_set_verdict_labels_match_the_real_judge`, run in CI).

## Results: offline coach (curated hints + static analysis)

Measured 2026-11-01. Full reports: `backend/evals/results/offline*.md`.

| Metric | Tuning set, first run | Tuning set, after fixes | **Held-out set** |
|---|---|---|---|
| Precision | 80% | 100% | **80%** |
| Recall | 48% | 60% | **50%** |
| F1 | 60% | 75% | **62%** |
| False alarms on clean code | 14% (2 of 14) | 0% (0 of 14) | **17% (1 of 6)** |
| Big-O accuracy | 79% | 95% | **50%** |
| Schema validity | 100% | 100% | 100% |
| Level-1 spoilers / level-2 relevance / code leaks | 8%¹ / 100% / 0% | 0% / 100% / 0% | (hints are per problem, not per sample) |

¹ The 8% was a **scorer bug**, not a coach problem: the term `mid` matched inside the word
"middle". The scorer now uses whole-word matching. It's listed so the change is visible.

### What changed between the first and second run (eval-driven fixes)
The first run's disagreements pointed at general weaknesses, each fixed with a general rule
and its own unit test:
1. Two-pointer loops (an inner `while` sharing the outer loop's bounds) were counted as
   nested, which reported O(n²) for linear code.
2. `nums[0]` was flagged even when the problem guarantees `1 <= nums.length`.
3. Halving loops (`mid = … / 2`) are now O(log n), and a linear scan is flagged when O(log n) is required.
4. "O(n + m)" now counts as a linear target, so sorting is flagged.
5. Exponential recursion (two or more unmemoized self-calls) is detected.
6. The eval also caught a **regression the new rules introduced**: `sb.reverse()` inside a
   method named `reverse` was mistaken for recursion. Fixed, with a test.

### Session 5: new problems exposed false alarms on optimal code
Adding 10 medium problems meant running the offline reviewer over their **optimal reference
solutions**, which should get no complexity complaints. Three did:

| Reference solution | Reviewer said (before) | Why it was wrong |
|---|---|---|
| Daily Temperatures (monotonic stack) | O(n²), "nested loops" | The inner `while` pops a stack; each index is popped once in total, so it's amortized O(n) |
| Longest Repeating Replacement (sliding window) | O(n²), "nested loops" | The inner `while` only moves `left` forward, and `left` is never reset |
| Coin Change (DP over amount × coins) | O(n²) vs target O(amount * k) | Two nested loops over two *different* inputs is the target, not a defect |

LIS and Kth Largest were also under-estimated as O(n) because a binary search or heap
operation inside a loop wasn't counted as a log factor. Three general rules fixed them, each
tested both ways (a pointer declared inside the outer loop, or reset in it, and a queue that's
refilled inside the inner loop, still count as nested):
1. **Amortized inner loops**: an inner `while` that drains a stack/queue (and doesn't refill it
   in the body), or advances a pointer declared outside the outer loop and never reset.
2. **Product targets**: when the target is a product of two inputs, depth-2 nesting is on target.
3. **Log factors**: `binarySearch`, `PriorityQueue`, `TreeMap`/`TreeSet` inside a loop → O(n log n).

The original two sets were **unchanged** by these rules (identical numbers before and after).

| Metric | Medium held-out, old rules | **Medium held-out, new rules** |
|---|---|---|
| Precision | 83% | **100%** |
| Recall | 50% | **50%** |
| False alarms on clean code | 25% (1 of 4) | **0% (0 of 4)** |
| Big-O accuracy | 79% | **86%** |

Caveat: the samples are new code written after the rules, but the rules were motivated by the
reference solutions of the **same problems**, so this is "held-out code", not "unseen
problems". The remaining misses are logic bugs (wrong for zeros, greedy coin change, a strict
loop bound, a missing '0' check: the judge catches all four) and sorting for Kth Largest, which
isn't flagged because its target, O(n log k), isn't linear.

### How to read this honestly
- The tuning-set numbers are **optimistic**: the rules were improved while looking at those
  samples. The **held-out** numbers are the fair estimate, and they're clearly lower. Keyword
  and loop-depth heuristics don't generalize well. That's the main finding.
- **Correctness recall is low by design.** Static checks can't see logic bugs (off-by-one, wrong
  initial value, a forgotten tail). Those are caught by the **judge**, which is the source of
  truth, and are what an LLM reviewer is for.
- The sets are small (66 samples), so a single sample moves a percentage a lot. These numbers
  describe these sets only. They aren't general accuracy claims and shouldn't be quoted as such.

## Measuring Claude
```bash
cd backend
AI_PROVIDER=anthropic ANTHROPIC_API_KEY=… python -m evals.run --provider anthropic
```
This writes `evals/results/anthropic.md` with the same metrics, so the two providers can be
compared like for like. **Not run yet** (no API key in the build environment). Until it is,
no claims are made about Claude's review quality.

## Guarding against regressions
`backend/tests/test_evals.py` runs the offline evaluation in CI and fails if tuning-set
quality drops below the current numbers (precision ≥ 95%, recall ≥ 55%, false alarms ≤ 10%,
Big-O ≥ 90%, zero spoilers and code leaks). The held-out set is reported, never used as a target.
