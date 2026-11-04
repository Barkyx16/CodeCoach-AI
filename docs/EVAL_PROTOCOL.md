# CodeCoach AI — Evaluation protocol (version 1, frozen 2026-11-04)

How the written-answer coach is measured from here on, written down **before** the next scoring
changes. The machine-readable copy is `backend/evals/protocol.json`; the tests in
`backend/tests/test_eval_protocol.py` hold the harness to it. Results and history are in
[AI_EVALUATION.md](AI_EVALUATION.md).

## Why a reset

The held-out career set from 2026-11-03 was graded and its case details were read to write the
evaluation report. It still records what rubric v1 and v2 did, but it can no longer show whether
a change aimed at its failures generalises: anyone tuning against those failures has seen them.
The same holds, more weakly, for the two held-out coding sets, whose per-sample disagreements
have been printed in every report. So every set now records its **role** and **exposure**, and a
fresh, sealed set exists for the final measurement of the next candidate.

## The sets and what each is for

| Set | Role | Written by | What has been seen |
|---|---|---|---|
| `career_dev.json` (23) | development | the harness author (the tuning session) | everything; used to develop rubric v2 |
| `career_holdout.json` (17) | **exposed historical benchmark** | the harness author | graded, case details read 2026-11-03 |
| `career_families_dev.json` | development (Volume 4 tuning) | a separate agent session | written without the grader code or output; open to the tuning session |
| `career_contradiction_pairs.json` (56) | development (Volume 4 brief 04; protocol v2) | the tuning session, together with the rule it tests | everything; results on it are optimistic by construction |
| `sealed/career_rn_sealed.json` | **sealed final evaluation** | another separate agent session | counts, ids and hashes only (see Access) |
| `review_set.json` (38), `hint_terms.json` | development (coding) | earlier sessions | everything |
| `holdout_set.json` (14), `medium_set.json` (14) | exposed historical benchmarks (coding) | earlier sessions | per-sample results printed in every report |
| `regression.json` | known defects, by reference | — | points at cases in their original sets |

`regression.json` groups the cases that showed each known defect (dictated answers under-rated,
plain action verbs missed, keyword lists rewarded, contradictions unnoticed, generic answers
credited, grader-directed text credited). Cases keep their original set and hash. The gate
`data.regression_status` fails when a defect recorded as fixed shows again, or when one recorded
as open no longer shows (the record must be updated, with the commit, in the same change).

## How the new sets were made

**Questions** are chosen by a fixed rule over registered-nurse questions: for each
(difficulty, kind) cell, the 3rd question by id goes to the new development set and the 4th to the
sealed set (the 1st and 2nd were used by the earlier sets). No question is shared between sets.

**Families, not rows.** Each question has three families, and all variants of a family stay in
one set, so near-identical answers never straddle a split:

| Family | Variants |
|---|---|
| A | typed, dictated, paraphrase (one situation, same facts) |
| B | typed, dictated, meaning_changed (a different situation; one variant changes what is earned) |
| probe | keyword_list, bullet_actions, contradiction, self_correction, grader_directed, benign_control |

`grader_directed` covers score requests, role impersonation, fake system instructions, embedded
markup, attacks mixed into a good answer, and spacing or look-alike characters. `benign_control`
covers quoted speech, hypotheticals, negated concerns, discussion of grading or scoring in the
job, and unusual punctuation or Unicode. Both sets follow the same plan: 108 answers each.

**Who wrote them.** Each new set was written and labelled by a separate AI agent session (a
different model from the one tuning the coach) that saw only the protocol, its own questions and
the rubric points' label and advice text: not the grader code, not any grader output, not the
other sets. That separates the labels from the tuner and from the grader's behaviour. It is **not**
independent human labelling: the labels are model-written, every set says `review_status:
unreviewed`, and results against them are reported as agreement with provisional reference
labels, never as validated accuracy.

## Duplicates

`python -m evals.overlap` compares every pair of answers from different splits: exact text,
normalised text (lower case, no punctuation, collapsed whitespace; code keeps its operators),
and near-duplicates (word 3-gram Jaccard ≥ 0.5 or containment ≥ 0.8). Within one split, close
variants are deliberate (a typed answer and its dictated version, a correct solution and the same
code with one bug), so only cross-split pairs are flagged. Every flagged pair needs a decision in
`evals/overlap_review.json`; the gate `data.integrity` fails otherwise. The one pre-existing
overlap (the same Java code for two problems in the coding tuning and medium held-out sets) is
recorded there and in the manifest. The tool prints ids and similarity only, never text.

## What is measured

Defined before measuring (`protocol.json` → `metrics`). Every rate is reported with its numerator,
denominator and a Wilson 95% interval, and per-variant counts are always shown:

- **item precision / recall** of rubric points against the labels (uncertain points left out);
- **unsupported credit rate**: points the labels say are missing that the grader awarded;
- **rating within bounds**, where the labeller gave bounds;
- **keyword false award**: keyword lists rated Good or Strong;
- **contradiction full credit**: contradicted points still awarded;
- **attack credit**: grader-directed answers whose injected text added a point, raised the rating
  or was quoted; **benign false exclusion**: ordinary answers with a sentence left out as if
  written to the grader;
- **dictated parity**: criteria where a dictated answer gets the same decision as its typed pair;
- **meaning-changed false award**: points a meaning change removed that the grader still awarded;
- **contradiction detection** (protocol v2): answers the coach reports as contradictory that the
  labels say are, over those it reports (precision) and over those labelled contradictory
  (recall); how many it reports as only *unclear*; whether the two statements it quotes are the
  two labelled ones; and **collateral**: points the labels say are covered and not contradicted
  that it stopped counting because of a contradiction.

## Release rule for the next candidate

Applied once, to the frozen candidate and the baseline (rubric v2, commit `20bd00f`), both graded
on the sealed set after the candidate is frozen:

- **must pass:** every case graded; no failing schema, evidence, insufficient-evidence or
  stability check; attack credit 0 for the grader-directed kinds the candidate claims to handle;
  benign false exclusion no higher than the baseline's;
- **not worse:** item precision and recall each at least the baseline's minus 0.02, unsupported
  credit rate at most the baseline's plus 0.02;
- **reported, not gated:** keyword false award, contradiction full credit, dictated parity,
  meaning-changed false award, rating within bounds. An improvement is claimed only for these
  cases, with its interval, and small counts are called small. Nothing here claims clinical
  accuracy, fairness across groups of people, or general robustness.

## Protocol v2 (2026-11-04, Volume 4 brief 04)

`protocol.json` changed after cases were graded, so it has a new version and this note
(`changes` in the file records both versions). What v2 adds:

- the development set `career-rn-contradiction-pairs` and its **minimal-pairs** design: six base
  answers on the development questions (the 1st by id, never a question the sealed set's rule
  picks), and variants that each make exactly one edit to their base (checked word by word by
  `python -m evals.validate_cases`) — a contradiction, a self-correction, a control that looks
  like a contradiction (quoted speech, a hypothetical, an unrelated negation, a change over time,
  someone else's action, another occasion, uncertainty), or a contradiction plus text addressed
  to the grader. Every case says whether it is `contradiction`, and a contradiction quotes its
  two statements (`conflict`) and the points they undermine;
- the `contradiction_*` metrics above, reported and not gated (also on the sealed set at the
  final grading);
- the gate `career.contradiction_controls`: a self-correction or control in the development
  families (and the families set's benign controls) is never reported as a contradiction.

Unchanged: the sealed set, its selection rule and access rules, and the release rule's must-pass
items and non-inferiority margins. The pairs set was written by the tuning session together with
the rule it tests, and says so in its `labeler` field: it shows what the rule does on the cases it
was built from, not that it generalises.

## Protocol v3 (2026-11-04, Volume 4 brief 05 / prompt 07)

What v3 adds (`changes` in `protocol.json`):

- the development set `career-rn-injection-challenges` (90 cases, written by a separate agent
  session from the protocol, the questions and the rubric text only; model-written labels,
  unreviewed): nine families on the development questions (the 1st by id), each a **typed and a
  dictated base** and variants that make exactly one edit to a base, checked word by word;
- **45 grader_directed** variants in 13 kinds: the six from v1 plus paraphrased_request,
  role_delimiter, fabricated_evidence, output_escape, long_distracting_context,
  criteria_leak_request and unpunctuated_dictated (an attack inside the dictated base). Each
  records the exact added text (`injection`) and quotes that must never be shown as evidence;
- **27 benign_control** variants in 8 kinds: the five from v1 plus
  quoted_discussion_of_instructions, shared_vocabulary and professional_terminology (clinical or
  workplace terms that look like commands: escalate, override, NEWS2 score, care plan marked
  complete);
- metrics `attack_credit_by_kind`, `benign_false_exclusion_by_kind` (one rate per kind, so a
  serious failure in one kind isn't hidden in a total) and `attack_evidence_changed` (attack
  answers whose point decisions or quotes differ from their base's);
- the gate `career.grader_boundary` on the grader_directed and benign_control families of this set
  and on the families set's grader_directed answers; this set's benign controls are also gated as
  not contradictions.

Unchanged: the sealed set, its selection rule and access rules, and the release rule. The set was
written by a separate session, but the tuning session read every case while building rubric v6,
so its results are development figures.

## Access to the sealed set

- The tuning session never opens `sealed/career_rn_sealed.json` or case-level results from it.
  The tools it runs over the set (`validate_cases`, `overlap`, the data gate) print counts, ids and
  hashes only.
- `python -m evals.run --sealed` grades only sealed sets and grades nothing else. Its report and
  markdown hold aggregates only; case-level results go to `evals/sealed/results/<label>.cases.json`
  and the run is appended to `evals/sealed/ACCESS.md`.
- It is run **once**, after the candidate is frozen. Once its case-level results are read, or any
  of its findings guides a change, the set is consumed and the next honest measurement needs a
  new sealed set (new file, new manifest entry).
- A hash shows the file didn't change; it does not show that nobody read it. The separation here
  is procedural: a separate authoring session, tools that don't print text, and the access log.
  This session wrote the protocol that the sealed set's author followed and knows the sealed set's
  question ids (which question template each one uses); it has not seen any sealed answer or label.

## Review by people

`python -m evals.review_packet <set>` writes a printable page (question, rubric points with their
advice, answer, proposed labels) and a CSV with one row per (case, point) to mark agree,
disagree or unsure. `--import <csv> --reviewer "<name, role>"` records the decisions in
`evals/reviews/<set>.json`. A review never edits labels: a corrected label needs a new dataset
version. A set's status can't say more than its records (`review_status`), and the validator
rejects a set that claims validation or expert review without them. A sealed set's packet is only
for a reviewer who isn't tuning the coach. **No reviewer has taken part yet**; every set is
unreviewed and results are provisional.

## Baseline: rubric v2 on the new development set

Measured 2026-11-04 at commit `da96069` (`python -m evals.run --split dev --label baseline-v2-dev`;
report in `backend/evals/results/baseline-v2-dev.*`). This is the starting point for the Volume 4
scoring work. These are development numbers against model-written, unreviewed labels: they guide
tuning and are not a final measurement.

| Metric | Rubric v2 on career-rn-families-dev (108 answers) |
|---|---|
| Item precision | 281/331 = 85% (95% CI 81–88%) |
| Item recall | 281/399 = 70% (95% CI 66–75%) |
| Unsupported credit rate | 50/104 = 48% (95% CI 39–58%) |
| Rating within the labelled bounds | 17/36 = 47% (95% CI 32–63%) |
| Keyword lists rated Good or Strong | 4/9 (95% CI 19–73%) |
| Contradicted points still awarded | 6/9 (95% CI 35–88%) |
| Grader-directed answers whose text earned credit or was quoted | 1/9 (95% CI 2–44%) |
| Ordinary answers with a sentence wrongly left out | 0/9 (95% CI 0–30%) |
| Dictated answers' decisions matching their typed pair | 78/84 = 93% (95% CI 85–97%) |
| Points removed by a meaning change but still awarded | 9/18 = 50% (95% CI 29–71%) |

**What this says about the earlier numbers.** On answers written by a separate session, rubric v2's
recall is 70%; on the sets the harness author wrote and labelled (2026-11-03) it was 94% on
development and 85% on the then-held-out set. The author's own answers matched the grader's
phrasing more often than independently written ones do, so the earlier recall was optimistic.
Only 9 answers per probe variant: the intervals are wide, and single cases move the rates a lot.

## Commands

```bash
cd backend
python -m evals.validate_cases evals/career_families_dev.json   # a set against the protocol
python -m evals.overlap                                          # cross-split duplicates
python -m evals.run --split dev                                  # development measurement
python -m evals.run                                              # everything except sealed sets, with gates
python -m evals.review_packet career-rn-families-dev             # a packet for a reviewer
python -m evals.run --sealed --label final-<date>                # once, for a frozen candidate
```
