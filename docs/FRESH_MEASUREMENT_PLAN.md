# Fresh measurement plan: rubric v10 (planned, not run)

Declared 2026-11-05 (Durable Saves brief 15), before any of its cases exist. The machine-readable
version is `next_measurement` in `backend/evals/protocol.json` (protocol v8). This plan does not
contain a measurement.

## Where each kind of evidence stands

| Evidence | Status | Where |
|---|---|---|
| Development results, rubric v10 | measured, on sets the tuning session read (plus new pairs it wrote) | docs/AI_EVALUATION.md, "Results: rubric v10" |
| Exposed historical comparison | `career-rn-holdout` and the two used sealed sets (graded once with v8) | "The sealed measurement" |
| Human label review | packet prepared, **no person has reviewed anything** | EVAL_PROTOCOL.md, "The review sample" |
| Independent measurement of rubric v10 | **pending**: no fresh set exists | this plan |
| Live Claude evaluation | **not run**, no paid calls authorized | "Live Claude evaluation" below |

Each row stands alone. A green CI run, a development gain or an offline provider test doesn't
change another row's status.

## The frozen candidate

`backend/evals/results/freeze-2026-11-05-candidate-rubric-v10.json`, written with
`python -m evals.freeze write --label candidate-rubric-v10` on a clean tree (protocol v9). The
earlier v9 freeze (`…-candidate-rubric-v9.json`) is kept and superseded: its `check` fails once
scoring changes, which is the rule working. It records:

- rubric v10 and coach prompt `coach-2026-11-04c` with its request fingerprint;
- protocol v9;
- a sha256 of each file that decides a career score or a request to Claude (`grading.py`,
  `questions.py`, `contradictions.py`, `evidence.py`, `profiles.py`, `anthropic_provider.py`,
  `protocol.json`), every dataset and the dependency files;
- the declared metrics and the release rule.

`python -m evals.freeze check <record>` must pass immediately before grading. If anything has
moved, the candidate is frozen again and this plan is declared again. A frozen candidate is not
re-measured on old data and then called fresh.

**Baseline:** rubric v8, the previous frozen candidate (`84dc1ee`). It runs from a worktree of that
commit (its own `app/careers`), using the candidate's evaluation harness and the fresh sets, the
same way the v2 baseline was run for the sealed measurement.

## Metrics, declared before measuring (each with what its denominator counts)

| Metric | Denominator |
|---|---|
| item_precision / item_recall | points credited / points labelled covered (labels not marked uncertain) |
| unsupported_credit_rate | points labelled missing |
| contradiction_detection_precision / recall | contradictions reported / answers labelled contradictory |
| contradiction_full_credit | contradicted points in contradiction answers |
| contradiction_collateral | covered points a reported contradiction isn't about |
| meaning_changed_false_award | points labelled covered on a typed answer and missing on its meaning-changed version |
| keyword_false_award | keyword_list answers, including the question's guidance copied or reported back |
| benign_false_exclusion | benign control answers (false rejections of ordinary text as addressed to the grader) |
| attack_credit | grader-directed answers |
| quote_validity / quote_relevance | quotes shown as evidence |
| dictated_parity | point decisions on dictated answers, against their typed pairs |
| rating_within_bounds | answers with a rating bound |

**Release rule (unchanged items, applied to each fresh set against the baseline):**

- every case graded;
- no failing schema, evidence, insufficient or stable case;
- attack_credit = 0 for the kinds the candidate claims to handle;
- benign_false_exclusion not higher than the baseline's;
- non-inferiority margins of 0.02 on item precision, item recall and unsupported credit.

The other metrics are reported, not gated, with their counts and 95% intervals. Small counts are
called small.

## The fresh sets and how they are kept apart

**Sets.**

- `career-rn-fresh` uses the 5th question by id of each (difficulty, kind) cell for registered
  nurse, and `career-csr-fresh` does the same for customer service. Every cell has at least 5
  questions.
- A question any existing set already uses is skipped for the next unused index, and each skip is
  recorded.
- Each set uses the families plan: 12 answers per question (two base families with dictated,
  paraphrased and meaning-changed versions, and a probe family).

**Roles.**

| Role | Who | Sees |
|---|---|---|
| Author and labeller | a session or person that has not seen this repository's code, results, other sets or regression register | the protocol, the questions' prompts and their rubric points' label and advice text |
| Operator | a person | receives the files, registers hashes, keeps them out of the tuning session's reach, keeps the access log |
| Reviewer (optional) | a person not tuning the coach (`evals.review_packet --reviewer-not-tuning`) | the packet; without one, labels stay model-written and are reported as such |
| Grader runner | may be the tuning session | `python -m evals.run --sealed` only: aggregates, with case-level results written unopened |

**Separation, step by step.**

1. The operator starts the author with only the inputs above. A new agent session started from
   *this* repository doesn't qualify, because it can read the code and results.
2. The author writes answers and labels. The operator runs `python -m evals.overlap` against every
   existing set. Flagged answers go back to the author to rewrite and are not shown to the tuning
   session.
3. The operator registers each file under `backend/evals/sealed/` with its version and sha256 in
   `evals/datasets.json`, and writes the "written" and "registered" rows in
   `evals/sealed/ACCESS.md`.
4. `python -m evals.freeze check` passes. The candidate and baseline are graded once each.
   `python -m evals.release` applies the rule, and only aggregates are reported.
5. If case text or case-level results reach the tuning session at any point, the sets are
   consumed. Results from them are then reported as development data.

**What this independence is and isn't.**

- A separate session is not independence by itself. What makes the measurement independent of
  the tuning is that the tuning session never sees the fresh sets.
- If the author is a model, its labels are model-written and share that model's blind spots.
  That is independence from the tuning, not expert validation.
- Nothing here measures clinical or customer-service correctness. The coach judges answer
  structure only.

**If the roles can't be filled,** development results are reported and the fresh measurement stays
pending. It does not block other engineering work.

## Live Claude evaluation: dry-run plan (no calls made)

Claude is used for coding reviews and hints. Career answers are graded offline, so a live run
doesn't touch them. The plan below is `python -m evals.run --provider anthropic --plan --max-calls 300
--max-output-tokens 400000`, saved as `backend/evals/results/live-eval-plan-2026-11-05.json`. It
builds no client and sends nothing. No key was set or printed: `api_key_set: false`, provider
`offline`, so it isn't ready.

| | |
|---|---|
| answers requested | 666 (38 tuning reviews, 600 hints at levels 1–2, 14 + 14 holdout reviews) |
| worst case | 1,998 requests, 4,392,000 output tokens (every answer retried 3 times at its token limit) |
| proposed budgets | `--max-calls 300 --max-output-tokens 400000`; either stops the run (marked partial) before the worst case |
| input tokens | not estimated before the run; counted from the provider's reports |
| cost | **not estimated: no prices were supplied.** A cost is computed only from `--price-input-per-mtok`, `--price-output-per-mtok` and `--price-source` given at run time, never from remembered prices |

**What exists today is contract testing, not quality measurement.** The provider tests
(`tests/test_ai_coach.py`, `tests/test_live_eval.py`, `tests/test_explain_failure.py`, and the
`faults` and `contracts` sections of `evals.run`) run against a fake client. They show how
requests are framed, bounded and redacted, and how failures fall back to the offline coach. They
say nothing about how well Claude coaches.

A live run needs an explicit authorization naming a budget and the pricing source, then
`--allow-paid-calls`. This queue authorizes neither.
