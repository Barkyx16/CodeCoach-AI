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

## Protocol v4 (2026-11-04, Volume 4 prompt 05)

What v4 adds (`changes` in `protocol.json`):

- `labeling.action_criterion`: what "Describes specific actions you took" means, written before
  the set: at least two concrete things the learner did or took part in, told as done. Team
  actions count; someone else's, a passive that doesn't say who, intended, hypothetical, negated,
  only-thought-about and general habits don't; cautious wording about memory still tells an
  action; the wording doesn't matter. Labellers mark the point uncertain when they can't tell;
- the development set `career-rn-action-wording` (126 cases, written by a separate agent session
  from the protocol, the questions and the rubric text only; model-written labels, unreviewed):
  nine behavioural questions (the first three by id with the action point in each behavioural
  cell, never the 2nd–4th by id of the cell, which the holdout, families and sealed rules pick),
  each with a typed and a dictated base, 8 `action_paraphrase` variants (11 kinds: team action,
  a story in the present, past perfect, professional phrasing, irregular verbs, words between,
  cautious memory, cleft or nominal, a passive with the learner as agent, concise, a paraphrase in
  the dictated answer) and 4 `action_control` variants (8 kinds: negated, intended, hypothetical,
  someone else did it, a passive without the learner, an irrelevant action, a keyword list, a
  thought rather than an act);
- metrics `action_recall` and `action_false_credit` (with by-kind tables) and
  `action_paraphrase_parity`;
- the gate `career.action_controls` on that set's controls, except irrelevant actions (an open
  defect).

Unchanged: the sealed set, its selection rule and access rules, and the release rule. The set's
first grading (rubric v6) is recorded as its baseline; after that the tuning session read it, so
its later numbers are development figures.

## Protocol v5 (2026-11-04, Volume 4 prompt 06)

Adds the per-case check `evidence_contract` (every quote checks out as it would be shown:
`app/careers/evidence.py`), gated on the gated career sets as `career.evidence_contract`, and two
metrics reported apart: `quote_validity` (quotes at their recorded place) and `quote_relevance`
(quotes that show their point). No set, label, selection rule or release rule changes.

## Protocol v6 (2026-11-04, Volume 4 prompt 10)

A second career, `customer-service-representative`, chosen from the catalog because it is
non-clinical, has its own people, skills and metrics, and needs no domain expertise to label
answer structure. Two sets, each written by its own separate agent session to the same family plan
as `career-rn-families-dev` (12 answers per question: two base families with dictated,
paraphrased and meaning-changed versions, and a probe family with a keyword list, bullet actions,
a contradiction, a self-correction, an attack on the grader and a benign control):

- `career-csr-families-dev`: development, the 1st question by id of each (difficulty, kind) cell;
- `career-csr-sealed`: sealed (`evals/sealed/career_csr_sealed.json`), the 4th by id; not opened by
  the tuning session (its access log is `evals/sealed/ACCESS.md`); graded once with the frozen
  candidate and reported. It has no baseline, so the release rule (written for `career-rn-sealed`)
  doesn't apply to it.

Labels judge structure only, never whether the customer-service practice described is right; a
point worded "Explains <metric> correctly" is labelled by whether the answer addresses it.
Nothing about the nursing sets changes.

## Protocol v7 (2026-11-04, Durable Saves brief 13)

`career-csr-families-dev`'s `keyword_list` family is gated (`gated_families`), like the nursing
set's: its one failing case, the question's advice reported as someone else's
(`cd-3-P-keyword_list`, `paraphrased-guidance-credited`), is fixed by rubric v9, and no other case in the
family fails under v9. No set, label, selection rule, release rule item or margin changes, and
nothing about the sealed sets changes: they stay used, and rubric v9 has no independent
measurement (docs/AI_EVALUATION.md, "Results: rubric v9").

## Protocol v8 (2026-11-05, Durable Saves brief 15)

Declares the next measurement before any of its cases exist (`next_measurement`):

- the frozen rubric v9 candidate (`evals/results/freeze-2026-11-05-candidate-rubric-v9.json`,
  checked with `python -m evals.freeze check`) against the rubric v8 baseline (`84dc1ee`);
- two fresh sets, the 5th question by id of each cell for each career, written by an author who
  hasn't seen this repository's code, results or other sets, and registered by a person;
- the release rule applied to each set.

Roles, separation steps and the declared metrics with their denominators are in
[FRESH_MEASUREMENT_PLAN.md](FRESH_MEASUREMENT_PLAN.md). **Nothing has been written or measured
under it.** Rubric v9's independent measurement is pending. No existing set, label, gate or
release item changes, and the used sealed sets stay used.

## Protocol v9 (2026-11-05, Verification briefs 12–14)

The next measurement's candidate is now rubric v10
(`evals/results/freeze-2026-11-05-candidate-rubric-v10.json`), because the v9 candidate's freeze
check fails once scoring changes, as the plan requires. The v9 freeze record is kept and marked
superseded. Nothing else in `next_measurement` changes, and neither do the existing sets,
labels, gates or release items.

## The sealed sets have been graded (2026-11-04)

`career-rn-sealed` and `career-csr-sealed` were graded once each for the frozen candidate
(`84dc1ee`, rubric v8; freeze record `backend/evals/results/freeze-2026-11-04.json`) and the
baseline (rubric v2, `20bd00f`), as the release rule says. The release rule passes on
`career-rn-sealed`; the results, including what didn't improve, are in docs/AI_EVALUATION.md, "The
sealed measurement". Case-level results were not opened and are kept out of the repository. From
now on the two sets are used: any fix guided by their case-level results consumes them, and the
next honest measurement needs new sealed sets written the same way (a separate session; the
selection rule's next unused index, the 5th question by id of each cell).

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

### The review sample (Durable Saves brief 14): prepared, human review pending

A whole set is a lot to review, so `python -m evals.review_sample` draws a bounded sample and
runs it in two passes. The committed sample is `backend/evals/reviews/samples/sample-2026-11-05.json`
(24 cases, 119 point judgements, drawn at rubric v9 with seed `2026-11-05`). **Status: prepared;
no person has reviewed any item.** No ratings file exists, and none may be written by a model.

- *What is sampled:* development sets and the exposed historical set only. Sealed sets are never
  opened by this tool. They are used, and any fresh independent set must stay out of the tuning
  session's packets too.
- *Selection rule (seeded, recorded on every item):*
  - stratum `disagreement` (10 cases) holds cases where the current rubric differs from a proposed
    label, or the labeller marked a point unsure. They are taken round-robin across sets, most
    differences first. **This stratum is chosen on purpose and is not representative.** Its figures
    describe where labels are most likely to be wrong, not the sets.
  - stratum `random` (2 cases per set, 14) holds the first cases in the order of
    sha256(seed:set:case).
  - Each set's version and sha256 are recorded. A changed set makes the sample refuse to build a
    packet, so a new one has to be drawn.
- *First pass, blind* (`packet <id>`): question, rubric version, each point's label and advice,
  the labelling definitions (covered, the action criterion, contradiction) and the answer.
  Proposed labels, the coach's decisions and case ids (which name the variant, a hint at the
  label) are all hidden. The form `1-form.csv` asks for each point:
  - `your_label`: covered, missing or cant_tell;
  - `uncertainty`: low, medium or high;
  - `needs_expertise`;
  - a `rationale`.
- *Import* (`import <id> form.csv --reviewer "Name, role" --human`): `--human` states that a person
  made the labels, and another model's labels are not a review. A reviewer's later pass replaces
  their earlier one. Since the Verification batch it also refuses:
  - a point rated twice in one form;
  - a form missing its columns;
  - a reviewer named as a model or tool. This is a backstop listing only names no person carries;
    "Claude" is a person's name too.

  Status lists unresolved and not-yet-adjudicated differences. These ingestion tests use
  synthetic ratings, so they prove the checks, not a review.
- *Second pass, reveal* (`reveal <id>`): the proposed label, the rubric's decision and every
  reviewer's label side by side. Each difference becomes a row in `2-adjudication.csv`, with
  outcome `keep`, `change` (with the label) or `unresolved` and a rationale, recorded by
  `adjudicate <id> … --adjudicator "Name, role" --human`.
- *Agreement* (`status <id>`): reported only when at least two people labelled the same points
  (percent agreement and Cohen's kappa per pair, `cant_tell` left out). With one reviewer it says
  it can't be computed, and no agreement figure is ever quoted from model labels.
- *Structure, not practice:* reviewers judge whether the answer does what the point describes.
  - Whether the nursing or customer-service practice is right is a separate judgement. It needs
    the right expertise: a registered nurse or nurse educator for the nursing sets, an
    experienced practitioner for customer service.
  - A point marked `needs_expertise` stays as labelled until such a reviewer records a decision,
    and is reported as needing expertise.
  - Points worded "Explains … correctly" are flagged `domain` in the form. The rubric only checks
    that the answer discusses the subject.

### When a review changes a label

1. The tool never edits a dataset. An adjudicated `change` is recorded, with who decided, when
   and why, in `evals/reviews/samples/<id>.ratings.json`.
2. Applying it makes a **new version of the set** (`version` + 1). The new version has:
   - the label changed;
   - a `label_changes` entry with `case`, `point`, `from`, `to`, `version`, `review` (the record's
     path), `adjudicator`, `date` and `rationale`;
   - `review_status` saying no more than the records support.

   `evals/datasets.json` gets the new version and sha256. The validator rejects a `label_changes`
   entry that is missing a field, has no later version, or doesn't match the set's current label.
3. **Old reports are kept as they are.** Each records the dataset version and hash it was graded
   on, so it stays true of that version. Results on the new version are new reports, and a
   comparison across versions says so.
4. Entries in `evals/regression.json` whose signal depends on a changed label are re-checked, with
   a note.
5. A protocol change (new `protocol_version`, a note here) is needed only if a gate, a family's
   gating or a metric's definition changes.
6. Sealed labels are not changed by the tuning session.

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
python -m evals.review_sample packet sample-2026-11-05           # the bounded review sample, blind first pass
python -m evals.run --sealed --label final-<date>                # once, for a frozen candidate
```
