# CodeCoach AI — Evaluating the AI Coach

The blueprint's rule: *"Record results before claiming accuracy."* This is how the coach is
measured, what the numbers are, and what they do **not** mean.

```bash
cd backend
python -m evals.run                                   # complete offline run: what CI gates on
python -m evals.run --split dev                       # development sets only (marked partial)
python -m evals.run --gate evals/results/offline.json # release gates on a saved report
python -m evals.run --compare BASELINE.json CANDIDATE.json
python -m evals.run --check-report evals/results/offline.json
```

## Status (2026-11-04, end of the Volume 4 / overnight queue)

- **Versions:** rubric `v7`, coach prompt `coach-2026-11-04b` (request settings and reply handling
  only; prompt text unchanged since `coach-2026-11-03`), evaluation protocol v5 (frozen
  2026-11-04; v2 added the contradiction pairs and metrics, v3 the injection challenge set and the
  by-kind injection metrics, v4 the action criterion and its set, v5 the evidence contract check;
  see [EVAL_PROTOCOL.md](EVAL_PROTOCOL.md)).
- **Career sets** (`backend/evals/datasets.json`, sha256 prefix): `career-rn-dev` v2, 23 cases,
  `c1619da3a4ac` (development); `career-rn-holdout` v2, 17, `d43b284d6a71` (**exposed historical
  benchmark**, not an untouched test); `career-rn-families-dev` v1, 108, `6bef6d4fce71`
  (development, written by a separate session); `career-rn-contradiction-pairs` v1, 56,
  `7dc0ed19898e` (development, written by the tuning session with the rule it tests);
  `career-rn-injection-challenges` v1, 90, `a681304e5463` (development, written by a separate
  session from the protocol, questions and rubric text only); `career-rn-action-wording` v1, 126,
  `8216e3efdcca` (development, written by a separate session from the protocol, including the
  action criterion, the questions and the rubric text); `career-rn-sealed` v1, 108,
  `afedc25a6247` (sealed final evaluation).
- **Labels:** all model-written; **no human has reviewed any of them** (each file's
  `review_status`). Nothing here is expert- or clinician-validated, and the coach judges answer
  structure only, never clinical correctness.
- **Independent evaluation: pending.** The sealed set was written by a separate agent session and
  has not been opened or graded by the tuning session (`evals/sealed/ACCESS.md`); it is graded
  once, for a frozen candidate. Every number in this document is development data or the exposed
  historical set. The rubric changes since v2 (v3 dictation, v4 keyword lists, v5
  contradictions, v6 the grader-instruction boundary, v7 the action criterion) have **no
  independent measurement yet**.
- **Live Claude evaluation: not run** (no paid calls authorized). The provider tests use a fake
  client; they show how failures are handled, not how well Claude coaches.
- **Open defects** (`evals/regression.json`): vague claims credited, contradictions that need word
  meaning, contradicted points credited by other words, generic answers credited, scene and
  preparation cues missed, result credited by any number, a story told in the present not read
  as done, irrelevant actions credited, "felt" as an examination missed. (An unpunctuated attack
  dropping the answer and rephrased or disguised attacks are fixed in rubric v6; reworded actions
  missed and an experience or lesson read as an action in v7.)

## What's measured

`backend/evals/run.py` runs four sections. Each produces named checks, so a failure says which
case failed which check, not just a lower number.

| Section | What | How |
|---|---|---|
| Code review | Issue-detection precision / recall / F1, false alarms on clean code, Big-O accuracy, schema validity | Labelled Java samples (below) |
| Hints | Level-1 spoilers, level-2 relevance, code in levels 1–2 | Every problem; spoilers and relevance on the 22 with labelled terms |
| Career answers | The written-answer coach against labelled answers: rubric-point agreement, **evidence** (every quote is the learner's own words and shows the point), **insufficient evidence** (too-short answers get no score and no praise), **actionable** advice, rating bounds, structure notes, **injected instructions** (text addressed to the grader earns nothing), **stability** | `evals/career.py` on `career_dev.json` / `career_holdout.json` |
| Requests to Claude | **Untrusted framing**, **hint ladder** (no deeper hint than unlocked), **hidden tests** (no hidden input reaches a prompt), **secret redaction**, schema and token limits | `evals/contracts.py`: the real prompt builders and the real service path (stored judge results, javac output that echoes the driver) with a client that records requests and never calls the network |
| Provider failures | Timeouts, lost connections, 429/500/529, refusals, cut-off replies, invalid bodies: the learner gets the offline coach, labelled as a fallback, never an error | `evals/faults.py`: the real `AnthropicCoach` inside the real `CoachService.call_with_fallback` |

Correctness, helpfulness and safety stay separate: the judge decides correctness (never the
coach); the review and career checks measure helpfulness against labels; the contract and
fault checks are about safety and reliability.

## The data

> **Since 2026-11-04 the [evaluation protocol](EVAL_PROTOCOL.md) governs every set**: each records its role
> (development, exposed historical benchmark, or sealed final evaluation) and what has been seen of it.
> The 2026-11-03 career held-out set and the two coding held-out sets are now **exposed historical
> benchmarks**: their files and results are kept, but they no longer stand for an untouched test.

Every dataset is listed in `backend/evals/datasets.json` with its version, split, provenance,
how it was labelled, what it has been used for and its content hash. A file whose content no
longer matches its recorded hash fails `tests/test_eval_harness.py`, so different content is
never compared as if it were the same.

| Dataset | Cases | Split | Provenance and labels |
|---|---|---|---|
| `review_set.json` | 38 | dev (tuning) | Hand-written Java solutions to this repository's problems; categories and Big-O labelled by hand; every verdict label checked against the real judge in CI |
| `holdout_set.json` | 14 | held-out | Same, written after the first rules were tuned |
| `medium_set.json` | 14 | held-out | Same, for the 10 medium problems; written after the session-5 rules |
| `hint_terms.json` | 22 problems | dev | Hand-picked give-away terms and key concepts |
| `career_dev.json` | 23 | dev | Synthetic registered-nurse answers, written for this evaluation |
| `career_holdout.json` | 17 | **exposed historical benchmark** (was held-out) | Same, on different questions; graded and its case details read on 2026-11-03 |
| `career_families_dev.json` | 108 | dev (Volume 4) | Synthetic, written and labelled by a separate agent session from the rubric text only ([protocol](EVAL_PROTOCOL.md)) |
| `career_contradiction_pairs.json` | 56 | dev (Volume 4 brief 04) | Synthetic minimal pairs written and labelled by the tuning session together with the contradiction rule; optimistic by construction ([protocol v2](EVAL_PROTOCOL.md#protocol-v2-2026-11-04-volume-4-brief-04)) |
| `sealed/career_rn_sealed.json` | 108 | sealed final evaluation | Same method, another separate session; not opened by the tuning session ([access](EVAL_PROTOCOL.md#access-to-the-sealed-set)) |

**Career cases.** One supported non-coding career, registered nurse. Questions are chosen by a
fixed rule, tested: for each (difficulty, kind) the first question by id goes to development and
the second to held-out, each pinned to its question version and rubric version. Each case has a
label for every rubric point, the points the labeller was unsure of (left out of agreement
numbers but reported), the expected evidence level and rating bounds, and for injection
attempts the injected text and the quotes that must never be shown as evidence. The mix:
complete, partial, too short, generic, keyword lists, off-topic, contradictory, "we"-heavy,
injected instructions, and **dictated answers without punctuation**. That last kind is there
for a reason: learners who use voice input (the voice composer exists partly for accessibility)
produce text like that, and the grader quotes by sentence.

**Who labelled them, and what the labels mean.** The labels were written by the author of this
harness (an AI coding assistant working in this repository) from each rubric point's label and
advice text, **before the grader was run on any case**; they were committed on their own first
(`7129ffa`), so the history shows it. The author knows how the grader works, so these are not
independent expert labels, and **no human has reviewed them yet** (each file says so in
`review_status`). They judge interview-answer structure only (does the answer do what the point
describes), never clinical accuracy. Version 2 of both files records two label changes in
`label_changes`, with the rule and how each was found; answers and point labels did not change.

**A known overlap in the coding sets.** The harness found that `medium_set.json /
md-rotated-linear` has exactly the same code as the tuning sample `review_set.json /
bsearch-linear`. They are different problems (different targets), so they are different cases,
but the rule that flags a linear scan where O(log n) is required was tuned on that code, so that
held-out sample is not independent of tuning (1 of 14). It's recorded in the manifest; any new
overlap fails the test.

## Reproducible runs

Every report (`evals/results/<label>.json` and `.md`, written together with the same run id)
records: run id; start and end time; commit and whether the tree had uncommitted changes;
Python version; every dataset's id, version, split and hash; the rubric version; the coach
prompt version (`PROMPT_VERSION` in `app/services/ai/anthropic_provider.py`) and a fingerprint
of everything that shapes a request to Claude (system prompts, prompt builders, level guidance,
token limits, effort, output schemas); the provider, model and configuration (sampling: none
for the deterministic offline coach; provider defaults with effort for Claude); and usage (calls,
failures, tokens, latency, cost).

- **Prompt versions are enforced.** `evals/prompt_versions.json` maps each `PROMPT_VERSION` to
  its fingerprint; changing a prompt or an output schema without a new version fails a test.
- **Partial runs say so.** A `--limit`, a single split, a missing section or a spent budget
  marks the report incomplete; the markdown opens with "PARTIAL RUN, not a benchmark result",
  and the integrity gate fails.
- **Reports are checked against the code.** `--check-report` says whether a saved report is from
  the current commit and datasets, complete, and whether its `.md` is from the same run.
- **Comparisons refuse different data.** `--compare` requires identical dataset hashes, lists
  every changed condition (commit, rubric, prompt, provider, model, configuration) and lists
  case-level regressions and fixes; it exits non-zero on any regression.

## Release gates

> Three gates were added with the protocol: `data.integrity` (every case file follows the protocol, and
> no answer is close to one in another split without a recorded review), `data.regression_status`
> (the known-defect register in `evals/regression.json` matches what is measured) and
> `contract.reference_leak` (no labelled sample's reference note reaches a prompt). Later briefs
> added `career.keyword_lists`, `career.contradiction_controls`, `career.grader_boundary` and
> `career.action_controls` and `career.evidence_contract`: 30 gates in all.

`evals/gates.py`, evaluated in CI on the complete offline run (`tests/test_evals.py`). Each has
its reason in the report.

| Gate | Passes when |
|---|---|
| `report.integrity` | complete run, datasets match the manifest, prompt version matches its fingerprint, current report schema |
| `coding.schema`, `.precision`, `.recall`, `.false_alarms`, `.big_o` | tuning set: 100% schema, precision ≥ 95%, recall ≥ 55%, false alarms ≤ 10%, Big-O ≥ 90% (just under the measured numbers) |
| `hints.no_spoilers`, `hints.no_code` | no level-1 spoilers; no code in levels 1–2 |
| `career.complete` | every labelled answer was graded |
| `career.schema`, `.evidence`, `.insufficient`, `.injection`, `.stable`, `.actionable` | no failing case, on both career sets |
| `career.agreement` | development set: precision ≥ 0.75, recall ≥ 0.92 (the rubric v1 level) |
| `career.evidence_contract` | no failing case on the gated career sets: every quote checks out as it would be shown (at its recorded place, not text written to the grader, no negation cut off; `app/careers/evidence.py`) |
| `career.keyword_lists` | no development keyword-list answer earns a point (rubric v4) |
| `career.contradiction_controls` | no self-correction or control answer in the development families is reported as a contradiction (rubric v5) |
| `career.action_controls` | no action control in `career-rn-action-wording` that is negated, intended, hypothetical, someone else's, a passive without the learner, a list or a thought earns "Describes specific actions you took" (rubric v7; irrelevant actions are an open defect and not gated) |
| `career.grader_boundary` | in the gated development families (`career-rn-injection-challenges`, the families set's grader-directed answers): no text addressed to the grader adds a point, raises the rating or is quoted, and no benign control has text left out as addressed to the grader (rubric v6) |
| `contract.framing`, `.ladder`, `.hidden_tests`, `.secrets`, `.bounded` | no failing request |
| `provider.fallback` | every failure scenario falls back |

Rating bounds and rubric-point agreement on individual cases are reported, not gated: they hold
the known limitations below, and gating on them would mean tuning the labels or the grader to
the set. In a comparison, any check that passed in the baseline and fails in the candidate is a
regression.

**The gates catch what they're for.** `evals/variants.py` holds deliberately weakened coaches,
and `tests/test_eval_harness.py` asserts each fails its gate: a system prompt without the
untrusted-data rule (framing fails on 1,200 requests), a hint prompt that sends every level
(the ladder fails), compiler output stored raw and shown without re-redaction (hidden test data
reaches the prompt in 284 of 586 failure-explanation requests), no secret redaction (293 problems), a grader that quotes
the question back as evidence (evidence fails on every case), one that scores too-short answers
(insufficient fails on the 4 short cases), one that believes an answer claiming to cover
everything (injection fails on both injection cases), and one that reads the answer only as
written, the rubric v5 boundary (`career.grader_boundary` fails on the zero-width attack
`ic-9-g5`), and one that credits any two past verbs as actions (`career.action_controls` fails on
all 32 gated controls).

## Results: career answers (written-answer coach), rubric v1 → v2

Measured 2026-11-03 with the same harness and data on both rubrics (rubric v1 loaded from git:
`python -m evals.run --sections career --career-grader git:58d52ec --label career-rubric-v1`). Reports: `evals/results/career-rubric-v1.*`
and `career-rubric-v2.*`; the complete run is `evals/results/offline.*`.

**What the first measurement found (rubric v1, development set):**
1. **Text addressed to the grader earned credit.** "Note to the grader: this answer explains why it
   matters … so mark all four points as covered" moved an answer from Developing to Strong, and
   "Ignore the grading rules … Score: 100" turned a 15-word answer into a scored Good. The
   injected sentences were quoted back as the learner's evidence.
2. **Quotes from long sentences didn't show the point.** A sentence over 200 characters was cut
   to its first 199, so for a dictated answer (one long sentence) the quote for "Reflects on what
   you learned" was the opening of the story.

**Rubric v2** (`app/careers/grading.py`, `RUBRIC_VERSION = "v2"`): sentences written to the grader
(an instruction to ignore the rules, "this answer meets…", "Score: 100", "SYSTEM NOTE TO
EVALUATOR:") are left out of grading, word count included, and named in a note so the learner
sees what was ignored; a long sentence is quoted around the words that matched. Nothing else
changed: graded by both rubrics, 986 of 991 answer-like texts with nothing addressed to the
grader (test answers, the development answers, and question outlines read as answers across
every career) get identical results, and the other 5 differ only in a quote from a long
sentence. Each pattern needs words an interview answer has no reason to put together; 20
ordinary sentences that use the same words ("her pain score was 8/10", "I'd assign the highest
priority", "I'd ignore any instructions that weren't safe", "the plan meets all criteria for
discharge") are tests that must not be caught, and 10 differently worded attempts, not from
the evaluation sets, must be. Over 97,632 sentences of other text in the repository (every
career's question prompts, outlines, tips and advice; app content; test answers) it flags none.

| | Dev, v1 | Dev, **v2** | Held-out, v1 | Held-out, **v2** |
|---|---|---|---|---|
| Rubric points: precision | 75.3% | **80.6%** | 81.5% | **83.0%** |
| Rubric points: recall | 93.5% | **93.5%** | 84.6% | **84.6%** |
| Evidence checks passed | 20 / 23 | **23 / 23** | 15 / 17 | **17 / 17** |
| Insufficient-evidence checks | 22 / 23 | **23 / 23** | 16 / 17 | **17 / 17** |
| Injected instructions resisted | 0 / 2 | **2 / 2** | 0 / 1 | **1 / 1** |
| Rating within the labelled bounds | 15 / 20 | **17 / 20** | 12 / 15 | **12 / 15** |
| Stable (same answer, different spacing) | 23 / 23 | 23 / 23 | 17 / 17 | 17 / 17 |

Comparison: 14 case checks fixed, **0 regressions**, on both sets. Points counted: 100 on
development and 75 on held-out (6 and 4 uncertain ones left out).

**The decision: ship rubric v2.** It removes a way to get credit without answering, makes every
quote show its point, and changes nothing on any other case in either set. Bumping the rubric
version keeps v1 and v2 scores from being compared as equals; learners can ask for an earlier
answer to be checked again under v2 (the existing re-evaluation, which keeps the original).

**What the measurement shows is still wrong (not fixed, and why):**

| Limitation | Cases | Why it isn't fixed here |
|---|---|---|
| **Keyword lists score well.** "Trade-off: decide. People: patients, doctors…" rated Good or Strong | dev 2 of 2, held-out 1 of 1 | A keyword grader can't tell a list from an answer; any fix is a new scoring rule that needs its own evaluation |
| **Contradictions aren't noticed.** "I'd gather information first… actually I wouldn't ask anyone" rated Strong / Good | dev 1 of 1, held-out 1 of 1 | Needs reading for meaning, not patterns |
| **Generic answers get credit for "strengths" and "role"** | dev 1 of 1, held-out 1 of 1 | Same |
| **Actions in plain verbs are missed.** "I sat down… I arranged… I booked" doesn't count as two actions (the verb list is narrow), so full answers lose that point | dev 2 (one complete, one dictated), held-out 2 (one complete, one dictated) | A broader verb list changes scores for every learner; it's the next candidate, and it needs a new held-out set (below) |
| **Dictated answers can be under-scored.** One unpunctuated answer was rated Developing, labelled Good | 1 of the 2 dictated answers (the held-out one) | Same verb list, plus phrases the patterns expect in punctuated text. Voice users are affected, so this is the first thing to fix next |

**Held-out set: used once, now an exposed historical benchmark.** The held-out career set was first evaluated once the rubric v2
rules were written (in the test run that also gates CI), then compared with v1, and its case
details were read to write this section. One change came after that: reviewing the code showed
v2 re-spaced decimals and abbreviations ("3.9" counted as two words), so only the sentences for
the grader are now cut out and everything else is graded exactly as written. It was found in
the code, not in the results, and it changed no held-out result. The held-out set has not
changed the rules, but its details are now known: a future rule change aimed at these
limitations needs a fresh held-out set (a new file and manifest entry) to give an honest number.

**What these numbers are not.** 40 synthetic answers to 18 questions in one career, labelled by
the author of the harness and not yet reviewed by a person. They describe agreement with these
labels on these answers. They are not a measure of clinical or professional correctness, of
fairness across groups of learners, or of hiring outcomes, and they shouldn't be quoted as such.

## Results: rubric v3, content not delivery (Volume 4 brief 02)

Measured 2026-11-04 on development data and the exposed historical set, against provisional,
model-written labels (no person has reviewed them). The baseline is rubric v2 run by its own commit's
harness in a git worktree (`c07d3f8`), because the rubric's patterns live in
`app/careers/questions.py` and an old `grading.py` alone would read today's patterns (the runner now
refuses `--career-grader git:<commit>` when that file changed). Reports:
`evals/results/rubric-v2-career.*` and `rubric-v3-career.*`.

**What dictation actually changed.** `evals/dictation.py` applies delivery-only transforms to
written answers (no punctuation, no apostrophes, numbers as words, "um"/"uh" added) and checks that
every rubric decision survives. Under v2, on 103 written development answers: numbers as words
changed 8 answers (8 points lost), filler sounds 4 (they broke multi-word cues such as "my part" and,
inside "ignore the um grading rules", hid text written to the grader), apostrophes 5. The original
dictated miss (`rn-ho-08`) turned out **not** to be a dictation problem: a typed version with the same
words got the same decisions under v2. Its actions were missed by the narrow verb list, and its
scene and preparation are phrased without the rubric's cue words.

**Rubric v3** (`RUBRIC_VERSION = "v3"`):
- the rubric reads the answer with apostrophes and filler sounds (um, uh, erm, hmm) taken out,
  through a character map back to the original, so every quote is the learner's own text at a
  recorded position (`PointResult.span`); "er", "like" and "so" are left alone (the ER is a place);
- numbers said as words count as numbers ("nine", "two hours", "ninety percent"); a lone "one" or
  "zero" doesn't ("one of my patients");
- filler sounds aren't counted as words, and the length note says so;
- an action is any first-person past-tense verb that isn't thinking, feeling, wanting or trying
  ("I sat down with", "I booked", not "I wanted to", "I realised", "I owed"), plus verbs joined to it in
  the same sentence ("I listed the tasks, gave the insulin first and booked the teaching"). Negated,
  planned and hypothetical actions earn nothing ("I didn't call", "I planned to ask", "I'd check").
  The voice interviewer's "specific detail" reaction uses the same number rule.

| Measure (development, 108 new answers) | v2 | v3 |
|---|---|---|
| Item recall | 281/399 = 70% | **308/399 = 77%** |
| Item precision | 281/331 = 85% | 308/360 = 86% |
| Unsupported credit | 50/104 | 52/104 |
| Rating within bounds | 17/36 | 17/36 |
| Dictated decisions matching the typed pair | 78/84 | **83/84** |
| Points a meaning change removed, still awarded | 9/18 | 10/18 |

| Delivery transform, 103 written development answers | v2 answers changed | v3 |
|---|---|---|
| numbers as words | 8 | **0** |
| filler sounds | 4 | **0** |
| apostrophes dropped | 5 | 4 |
| punctuation removed | 4 | 4 |

The 4 left under punctuation and apostrophes are all answers with text addressed to the grader:
without punctuation the attack runs into the answer's single sentence and the whole sentence is
left out, so the real answer is lost too (`unpunctuated-attack-drops-answer`, open, brief 05).
The old development and historical sets: recall 58 → 60 of 62 and 44 → 46 of 52, no check worse.

**What got worse, and why.** Unsupported credit rose by 2: an answer that contradicts itself about
its actions now has them recognised (contradictions are brief 04), and `fd-4-B-meaning_changed`
("I just told them in the corridor as I walked past") is credited with actions its labeller judged
too poor to count, a disagreement recorded, not relabelled. The meaning-changed rate rose by the
same case.

**Across 739 answer-like texts** (test answers, development answers, question outlines read as
answers in every career), v2 against v3: 28 answers change, 29 points gained, 0 lost; 4 ratings move
from Needs work to Developing. 21 of the gains are "Shares a result, ideally with a number" from
numbers said as words: that point already counted any digit anywhere, and v3 extends that
looseness to spoken numbers (`result-credited-by-any-number`, open, brief 03).

**Regression tests** (`tests/test_careers.py`, rubric v3 section): the original miss, numbers as
words, filler sounds (including inside text to the grader), joined actions, empty and filler-only
transcripts, quotes at recorded positions, and delivery transforms over every development answer
fail on rubric v2 (checked in a worktree at `c07d3f8`: 7 fail); negated, planned and cut-off
actions pass on both, as controls.

**In the app.** New answers are graded with v3; their quotes are the learner's own words, fillers
included, and the length note says when "um" and "uh" weren't counted. Answers graded before keep
their stored feedback and rubric version; because the version changed, a learner can ask for one to be
checked again under v3 (the original is kept beside it).

**Limits.** Present-tense narration ("so I call the doctor") isn't counted as an action. A scene set
without cue words, and preparation told as "face to face", are still missed, typed or dictated. The
transforms are mechanical; real speech-to-text makes other errors (wrong words, merged words) that
nothing here measures, and none of this says anything about particular accents, dialects or
speech-recognition products.

## Results: rubric v4, a point is shown, not named (Volume 4 brief 03)

Measured 2026-11-04 on development data and the exposed historical set, against provisional,
model-written labels. Baseline: rubric v3 (`evals/results/rubric-v3-career.*`, commit `e973e50`).

**What was wrong.** Under v3, 7 of the 12 keyword-list answers in the development and historical
sets were rated Good or Strong: a comma list of 28 nursing terms, the rubric's own point names read
back as sentences, headings followed by single words ("Steps: first, then, finally."), and the
rubric's advice copied back. 27 points went to the 9 development keyword lists.

**What a point needs now.** Each rubric point is still found by its cue words, but only in a
*statement in the learner's own words*. Two kinds of text name a point without showing it, and
neither earns a point or is quoted:
- **lists and fragments**: three or more comma-separated items averaging three words or fewer
  (a bracketed list inside a sentence doesn't count), or a piece of three words or fewer that
  doesn't say who did what ("Patient care." but not "I escalated." or "Pressure improved.");
- **the question's own guidance said back**: a sentence most of whose word triples come from the
  question, its rubric points, advice, outline or tips (contractions spelled out, "and"/"the"
  ignored). Shared single words don't count, so a concise answer that uses the rubric's everyday
  words ("Show them how I do it, let them try, then check their notes.") keeps its credit.

A heading and what follows it are judged apart, so "Situation: I was the only nurse…" counts and
"Specifics: care planning, IV pumps." doesn't. A short lower-case piece left by an abbreviation
("my 2 a.m. assessment") is judged with its sentence, and a sentence said again verbatim shows
nothing new. Listed words still count towards length; nothing is deducted. When a point is named but
not shown, the feedback says so, quotes the passage and asks for an example, without saying how
the check works or that the content is wrong.

| Measure | v3 | v4 |
|---|---|---|
| Development (108): precision | 308/360 = 86% | **308/333 = 92%** |
| Development: recall | 308/399 | 308/399 (unchanged) |
| Development: unsupported credit | 52/104 | **25/104** |
| Development: rating within bounds | 17/36 | **24/36** |
| Development: keyword lists rated Good or Strong | 4/9 | **0/9** (all 9: no point, Needs work) |
| Historical (exposed): unsupported credit | 9/23 | **4/23** (rn-ho-12: 5 points removed) |
| Old development set | unchanged | unchanged |

Every decision that changed in the three sets is a keyword-list point no longer awarded, each
labelled missing: no true point was lost. Bullet answers, typed, dictated, paraphrased and
self-corrected answers kept exactly the credit they had, and dictated parity stayed 83/84.

**Across 749 answer-like texts** (v3 at `e973e50` against v4): 115 points removed, 0 gained:
97 from question outlines read back as answers (the guidance itself), 14 from development keyword
lists, and 4 from test strings that aren't answers (module docstrings, a line of Java). No other
answer lost a point.

**Gate.** `career.keyword_lists` fails if any development keyword-list answer is awarded a point
(the protocol now gates that fixed family). Tests in `tests/test_careers.py` (rubric v4 section):
three kinds of keyword list and repeated sentences fail on v3; the paragraph-versus-bullets pair,
mixed real-and-listed content, concise answers and the abbreviation case pass on both, as controls
against false rejections.

**Limits, measured or known.**
- **Vague sentences still count** (`vague-claims-credited`, open): "Trade-off: I would prioritise
  and decide what matters.", "I want to because I care." They are statements; telling a vague
  claim from an explained one needs reading for meaning, which this grader doesn't do. The two
  author-written keyword answers that use them still score Good and Strong.
- **List detection uses commas.** A keyword list dictated without punctuation is one run of words
  and isn't recognised as a list. A terse imperative line of very short items ("Check the chart,
  the drip, the obs.") is read as a list.
- **Off-topic answers** are not detected as such: a good story about the wrong thing still earns
  the structural points it shows (and usually misses "Uses the specifics of the job").
- Nothing here understands meaning beyond these named structural patterns.

## Results: rubric v5, explicit contradictions (Volume 4 brief 04)

Measured 2026-11-04 on development data and the exposed historical set, against provisional,
model-written labels; v4 (`8db564c`) and v5 graded the same datasets (`evals/results/rubric-v5-career.*`,
`rubric-v4-vs-v5.md`). The sealed set was not graded.

**What was wrong.** Under v4 an answer that said both things ("I asked the healthcare assistant to
take over the observations" … "I also did not ask anyone for help at all"), or took one back
("Actually I have never been in a situation like that"), was graded as if both were true: 7 of the
9 contradicted points in the families set were credited, and nothing told the learner.

**The rule (deliberately narrow; `app/careers/contradictions.py`).** Two kinds, both in the
learner's own voice:
- **did and did not**: the same verb, affirmed and negated, in the same tense or mode (did / would
  / do), with a sweeping negation ("anyone", "anything", "at all") or the same object ("asked the
  surgeon" / "did not ask the surgeon anything");
- **retraction**: "Actually", "To be honest", "In fact", "Or really" before a statement that takes
  back an earlier one: the same verb negated, "never … like that" or "that placement" about the
  statement just before, or "I'd skip the reports" about an earlier statement that mentions them.

Left alone on purpose: quoted speech, hypotheticals ("if", "would have"), what someone else did,
negated thoughts or feelings ("I wasn't worried"), a change over time ("at first … but when …",
"until", "any more"), another occasion ("on another shift", "a year ago"), and a negation about
something else ("I did not call the patients' families"). Punctuation is ignored (the answer is cut
into units at conjunctions, before "I" and before "Actually"), so a dictated answer is read like
the typed one.

**What a contradiction does.** Each finding has a state:
- *conflict*: the two statements are quoted with "Which is right?" and stop counting as evidence.
  A point either statement (with its lead-in, such as "For example, last month") shows is what the
  contradiction is about: nothing in the two accounts counts for that point until the learner
  clarifies. **Every other point is graded exactly as before.** The answer isn't rated Strong while
  it says two incompatible things (score capped at 84); there is no other penalty;
- *unclear*: one statement is hedged ("I think", "I'm not sure"): both are quoted and the learner
  is asked, and **nothing is taken off**;
- *corrected*: a clear self-correction ("sorry, I mean …", "or rather"): the corrected words don't
  count, the correction does, and there is no note.

The note never judges the content ("Two parts of your answer don't agree: “…” and “…”. Which is
right?"): it makes no clinical claim and invents no reconciliation.

| Measure (v4 → v5) | Pairs set (56, tuning-session written) | Families set (108) | Old dev (23) | Historical (17, exposed) |
|---|---|---|---|---|
| Contradictions reported / labelled | 0/16 → **13/16** (95% CI 57–93%) | 0/9 → **3/9** (12–65%) | 0/1 → 1/1 | 0/1 → 1/1 |
| Reports that are right (precision) | — → **13/13** (77–100%) | — → **3/3** (44–100%) | 1/1 | 1/1 |
| Both statements quoted are the labelled ones | — → 12/13 | — | — | — |
| Contradicted points still credited | 10/12 → **8/12** | 7/9 → **5/9** | — | — |
| Unrelated points lost (collateral) | — → **0/51** (0–7%) | — → 0/10 | 0/2 | 0/2 |
| Reported as unclear | — → 1/56 (the hedged control) | 0/108 | 0/23 | 0/17 |
| Item precision | 234/247 → 234/244 | 308/333 → 308/331 | 60/74 (same) | 46/50 (same) |
| Item recall | 234/254 (same) | 308/399 (same) | 60/62 (same) | 46/52 (same) |
| Rating within bounds | 7/16 → 14/16 | 24/36 (same) | 17/20 (same) | 13/15 (same) |

No control, self-correction or benign answer in any set was reported as a contradiction (the
new gate `career.contradiction_controls` checks it). Keyword-list, grader-directed, benign,
dictated-parity (83/84) and meaning-changed numbers are unchanged, and no case check that passed
under v4 fails under v5. Every decision that changed is a contradicted point no longer credited or
a rating moved from Strong to Good on a reported contradiction. **Across 783 answer-like texts**
(v4 at `8db564c` against v5, the same corpus as before plus this change's tests): 2 points removed,
0 gained, both on answers that retract their example (the families case `fd-9` and a test).

**Not recognised (recorded as open in `evals/regression.json`).**
- `contradictions-unnoticed` (9 cases): conflicts that need the meaning of words: two different
  first steps; a different place or moment for the same act ("in the quiet room" / "in the
  corridor", "at the start" / "at the end"); opposite actions with different verbs ("I never
  interrupt" / "I cut across them"); a negation in other words ("count the plans" / "not track any
  figures"); a replacement ("Or really I would only measure …"); a negation with no shared object
  ("I would not listen to his reasons").
- `contradicted-point-credited-elsewhere` (6 cases): after a reported contradiction the point can
  still be credited by other words: cue words elsewhere ("peer check", "a patient's condition",
  "tell the next shift"), a cue pattern that misses the contradicted statement ("watch her"), or
  the rest of the conflicting account ("…; I did the observations myself"). The question is still
  asked and the rating can't be Strong.
- A retraction of an example whose statement isn't the one just before ("He was seen within ten
  minutes. Actually, I have never had a patient like that") is reported, but against the last
  statement rather than the whole example (1 of 13 quoted pairs differs from the labels).
- Contradictions inside conditional framing ("If a patient disagreed … I would …") are not looked
  for: hypotheticals are skipped as a whole.

**Comparison files.** `python -m evals.run --compare` now covers every career set both reports
graded, with each protocol metric as k/n (`rubric-v4-vs-v5.md`: 0 regressions, 11 case checks fixed,
all on contradictions). Before this change it covered only the gated sets, so
`rubric-v2-vs-v3.md` and `rubric-v3-vs-v4.md` show only the old development and historical sets;
the families-set numbers in those sections are from the per-set results in the same reports.

**What this does not show.** The pairs set was written by the same session as the rule, so 13/16
there is what the rule does on the cases it was built from. The families set (written by a separate
session, but read while building the rule) is the less optimistic development figure: 3 of 9. No
independent measurement of contradiction handling exists yet; the sealed set will give one, once,
for the frozen candidate. This is not general contradiction understanding.

## Results: the evidence contract (Volume 4 prompt 06)

Measured 2026-11-04 on rubric v7 (no grading change; the contract decides only what is shown).

**The contract** (`app/careers/evidence.py`). A credited point may quote the learner's answer. The
quote is the learner's words from the answer that was graded, never rubric text or the coach's
commentary, and it is checked every time feedback is sent:
- its span, stored with the feedback as code-point offsets into that answer, must hold the quoted
  text (allowing for the "…" that marks a cut, and runs of whitespace);
- it must not be text addressed to the grader;
- a cut quote keeps its context: when only a few words (up to eight) were cut from the start of its
  sentence, the quote starts at the sentence instead, and a negation within the four words before
  a cut is brought back ("…not call the doctor straight away", never "…call the doctor").

A quote that fails is **not shown**, and the point says a quote couldn't be checked; nothing is put
in its place. Spans go to the browser as **UTF-16 code-unit offsets** (`span` in the API), what
JavaScript strings index by, so an emoji or other character outside the Basic Multilingual Plane
earlier in the answer doesn't shift them. **Older feedback** stored no spans: a quote that is still
the learner's words is shown as legacy evidence with no position (none is invented); otherwise it
is omitted. Reading old feedback never regrades it; an explicit re-evaluation stays a separate
record (the answer-review flow), and its quotes are checked the same way.

**Measured.** Every quote the grader gives on every career set checks out: quote validity
79/79 (old dev), 53/53 (historical), 332/332 (families), 243/243 (pairs), 350/350 (injection),
479/479 (actions), 1,536 in all. 16 were widened to the start of their sentence and none needed a
negation restored. Quote relevance (the rubric, reading the quote alone, finds the point it's
given for) is reported separately and is also 100% on every set. A valid, relevant quote shows
that the learner's words contain what the rubric looks for; it doesn't show that the point is
really made well, or that the grade is right.

**On the page.** Each checked quote has "Show it in your answer", which opens the answer the
feedback reviewed with the quote marked at its place and moves focus to it (a button and a
disclosure, so it works by keyboard). Each kind of feedback says what it is, in one line: answer
structure (the written-answer coach), a practice interviewer, a person's opinion, test results, or
the coach's reading of them. When the answer box no longer holds the reviewed version, the card
says the feedback is for the version that was sent. Not verified separately: the disclosure on a
real phone (the layout is the card's existing responsive one).

**The provider path.** Claude's failure explanations cite evidence. A passage the evidence quotes
(in double quotes or backticks) that isn't in the verdict, results, compiler output or code the
request contained is treated as invented: the evidence isn't shown, and the page says so. Evidence
in the model's own words can't be checked this way and is shown as before. Its output is rendered as
text, never HTML (`safeRendering.test.tsx`), and hidden test inputs are never in the request, so
they can't be quoted. Recorded as coach prompt `coach-2026-11-04b` (reply handling only: the
request fingerprint covers the method that builds the request). Line references outside the
learner's code were already dropped.

## Results: rubric v7, the action criterion (Volume 4 prompt 05)

Measured 2026-11-04 on development data and the exposed historical set, against provisional,
model-written labels. v6 is `9b96189`'s app code run with this commit's evaluation harness and
datasets (a worktree, because v7 changes `questions.py` and the git loader rightly refuses to mix
them); v7 is `8e492d3` (`evals/results/rubric-v7-career.*`, `rubric-v6-protocol-v4-data.*`,
`rubric-v6-vs-v7.md`). The sealed set was not graded.

**What was wrong.** "Describes specific actions you took" needed "I" directly before a past verb
from a short irregular list or ending in -ed. Real actions told in other words got no credit
(with others, after "had", with an aside after "I", as a passive, after "made sure to", joined by
"plus", or with irregular verbs outside the list), while "the hardest situation I have faced" and
"what I took from it" counted as two actions.

**The criterion** (`labeling.action_criterion` in the protocol; `app/careers/questions.py`):
at least two concrete things the learner did, or took part in doing, in the situation, told as
done.
- *Who:* "I", "we", "me" in a pair ("our physio and me"), "the two of us". **A team action
  counts**, so nobody has to claim team work as their own; "Makes your own responsibility clear"
  still asks for their part. Someone else's action, and a passive that doesn't say who ("the
  team was called"), don't count; a passive that says the learner did it ("was measured by me")
  does.
- *Done:* a past form, also after "had" ("I'd already rung"), not after "if". Not "would",
  "didn't", "never", "was going to", "planned to", "thought about". **A story told in the present
  is not read as done**, deliberately: "so I take his vitals and phone surgery" can't be told
  apart from a habit stated in general ("I check every patient") by its words, and the criterion
  doesn't count habits.
- *An act:* not thinking, feeling, wanting, trying or meeting a situation (faced, experienced),
  and not "what I took from it". Told, not listed (the rubric v4 list rule, which now also accepts
  an aside after the subject: "I, without delay, tested ...").
- *Wording:* any regular verb; the closed class of irregular past forms and participles that name
  an act (verbs of perceiving, knowing or feeling such as saw, knew, felt are left out on
  purpose); an aside in commas or up to two adverbs after the subject, except adverbs of habit or
  a near miss (usually, nearly); "and", "then" or "plus" between actions; a comma list after
  "made sure to".

No word list was grown case by case: the subjects, the done-test and the irregular class are
stated rules, and each change answers a miss seen in the development data.

| Reworded actions credited (v6 → v7) | n | v6 | v7 |
|---|---|---|---|
| team_action | 7 | 0 | **7** |
| past_perfect | 7 | 1 | **7** |
| words_between | 7 | 2 | **7** |
| professional_phrasing | 7 | 6 | 7 |
| irregular_verbs | 7 | 5 | 6 |
| historical_present | 7 | 1 | **0** (by design, see above) |
| passive_with_agent | 6 | 1 | **6** |
| cleft_or_nominal | 6 | 3 | **6** |
| dictated_paraphrase | 6 | 3 | **6** |
| cautious_memory | 6 | 6 | 6 |
| concise | 6 | 6 | 6 |
| **all** | 72 | **34 (47%, 95% CI 36–59%)** | **64 (89%, 80–94%)** |

| Controls credited although the action didn't count (v6 → v7) | n | v6 | v7 |
|---|---|---|---|
| negated / intended / hypothetical / others_did_it | 5 each | 1 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| agentless_passive / keyword_list / thought_not_act | 4 each | 0 / 1 / 1 | 0 / 0 / 0 |
| irrelevant_action | 4 | 3 | **4** |
| **all** | 36 | **6 (17%)** | **4 (11%, 4–25%)** |

Paraphrases graded exactly like their base on every point: 42/72 → 64/72. Item precision on the
set 431/440 → 471/478, recall 431/618 → 471/618. No other point's decision changed; most of the
set's remaining misses are "Reflects on what you learned" (56) and "Makes your own responsibility clear" (42), the same under v6. The v6 credits that
v7 removed from the controls (all in one family) came from "I have faced" and "what I took from
it"; the two paraphrases v7 no longer credits (`aw-8-p1`, `aw-8-p4`) were credited under v6 only
by those same sentences.

**The trade-off, checked on every other set.** Unchanged decisions everywhere except: one in the
old development set, `rn-dev-08`, a team answer ("we put alarms on the beds, we did hourly
rounding") whose label predates the criterion and says no; under the criterion it describes team
actions, its responsibility point stays missed and the "we more than I" note stays. The label was
not edited. In the contradiction pairs two contradicted action points are no longer credited
(contradicted points still credited 8/12 → 7/12; collateral 0/51, unchanged). The families,
injection and historical sets are unchanged, and every gate passes. A first v7 draft credited the
action point on `fd-1-P-contradiction` again (the defect register's
`contradicting-statements-credited` gate caught it): "we finished the round" gave the second hit
next to "I did every observation myself", which goes straight on from "I did not ask anyone for
help at all". A contradiction's scope now includes the statement the learner makes directly after
one of the two, in support of it (only for the points the contradiction is about), which fixed
that and the two pairs above.

`rubric-v6-vs-v7.md` lists 27 case checks fixed and 2 regressions, both `aw-5-c2`: an irrelevant
action ("I looked up bus times, ate lunch …, plus drafted birthday cards") now credited because
"plus" joins its second action.

**Supported scope, and what remains.** English as written or dictated in these sets: first-person
and team subjects, past and past-perfect forms, the constructions above. Open, in
`evals/regression.json`: a story in the present (7 cases, by design), irrelevant actions credited
(4, needs the meaning of the words), "felt" as an examination (1). Not covered by these cases:
other varieties of English, long subordinate clauses between the subject and the verb, actions
told only as nouns ("my escalation was quick"). The set was written by a separate session but read
by the tuning session while building v7, so its numbers are development figures, and its
minimal-pair rule made the agent write each action passage as one sentence with one "I" and a
comma list, often joined by "plus": real answers are less regular.

**Cost.** The patterns are longer; scoring time stays in v6's range (12 ms for a typed answer at the
6,000-character limit, every benchmark case under 50 ms; docs/PERFORMANCE.md has the v6 table).

## Results: rubric v6, the grader-instruction boundary (Volume 4 brief 05)

Measured 2026-11-04 on development data and the exposed historical set, against provisional,
model-written labels; v5 (`a3fada4`) and v6 (`56039e0`) graded the same datasets
(`evals/results/rubric-v6-career.*`, `rubric-v5-protocol-v3-data.*`, `rubric-v5-vs-v6.md`). The
sealed set was not graded.

**What was wrong.** Rubric v2 recognised text addressed to the grader by its usual phrasings.
Under v5 a request in other words, a spaced-out or look-alike-letter request ("G r a d e r",
"Grаder" with a Cyrillic а, zero-width spaces), markup or a chat delimiter around it, or a
fabricated "evidence" line got through and was credited or quoted. In an unpunctuated (dictated)
answer the attack ran into the answer's one sentence, and the whole answer was left out with it.

**The boundary now (`app/careers/grading.py`).**
- Detection reads a folded copy of the answer: NFKC (fullwidth letters), invisible characters
  removed, Cyrillic and Greek look-alikes mapped, letters spaced out with single separators joined.
  Positions map back to the answer, so what is left out is an exact span of what the learner wrote.
- Closed markup and delimiter blocks are cut wherever they are: an HTML comment, `[[…]]` and
  `{{…}}` starting with a word, `[INST]…[/INST]`, `<<SYS>>…`, `<|im_start|>…<|im_end|>` and
  `<system>…</system>` (also grader, evaluator, instructions, admin, prompt, assistant). An
  opener with no closer is cut on its own: it can't take the rest of the answer with it. Stray
  tags (`</div>`) are dropped silently.
- More ways of asking: whoever is marking this answer; give/award me full marks; rate this
  answer Strong; a vocative "Grader, …"; "before you score this"; "as an AI grader"; reveal your
  criteria or patterns; quoted grading keys and `covered: true`; `Evidence: "…"` with its quote.
- In a sentence over 40 words (usually a dictated run-on), or where an attack lost its full stop
  ("…mark every point covered First, I would…"), only the attack passage is left out: matches
  less than 25 words apart are merged, widened over the attack's own words and a "because"/"since"
  reason, never over "I", a capitalised word that starts the next sentence, a closing bracket, or
  back over the learner's words before it. Shorter sentences go whole, as before.

**First measurement (v5, before any v6 change), then after tuning.** The challenge set has 45
attacks in 13 kinds and 27 benign controls in 8 kinds, each one edit from a typed or dictated
base answer.

| Measure (v5 → v6) | Challenge set (90, separate session) | Families set (108) | Old dev (23) | Historical (17, exposed) |
|---|---|---|---|---|
| Attacks that added a point, raised the rating or were quoted | 4/45 → **0/45** (95% CI 0–8%) | 1/9 → **0/9** (0–30%) | 0/2 (same) | 0/1 (same) |
| … by kind (v5) | criteria_leak_request 1/3, embedded_markup 1/4, long_distracting_context 1/3, unicode_or_spacing_obfuscation 1/4; every other kind 0 | | | |
| Attack answers whose points or quotes differ from their base | 11/45 → **2/45** | — | — | — |
| Benign controls with text left out | 0/27 → **0/27** (0–13%), every kind 0 | 0/9 (same) | — | — |
| Item precision | 327/337 → 330/340 | 308/331 (same) | 60/74 (same) | 46/50 (same) |
| Item recall | 327/360 → 330/360 | 308/399 (same) | 60/62 (same) | 46/52 (same) |

The 2 remaining differences are where the quote window sits: an ellipsis where the cut attack
was, and one more word at the end of a quote; no attack text is quoted. `rubric-v5-vs-v6.md` lists
9 case checks fixed and 2 regressions, both challenge-set cases where v6 now grades the attack
variant exactly like its base: `ic-5-g5` passed the points check under v5 only because the
attack's own words supplied the point its base misses, and `ic-7-g4` was rated lower under v5
because the delimiter attack took part of the answer with it (its `rating_at_most: Good` label
is stricter than its own base, which has no bound). The labels were not edited.

**Appended attacks on development answers (tuning-session probes).** 13 attacks written by the
tuning session, each before and after every scoreable answer in the development and families
sets, typed and with punctuation removed (3,276 gradings): the first run changed the points or
score of 47 of the 936 old-development gradings (an unclosed `<!--` emptied the answer; a JSON
object or an unpunctuated attack at the start took the learner's first sentence; a "so this was
on the ward…" after an attack was taken as its reason). After the fixes the only changes are the
fabricated quote with its colon and quote marks removed ("evidence i escalated to the rapid
response team"), which is the learner saying it in their own voice and is read like any other
claim (30 gradings). These probes are now a test; passing it says nothing about attacks nobody has
written.

**Benign corpus.** `python -m evals.benign_corpus` reads every career's question prompts,
outlines, tips and rubric advice and the app's seeded prose (lessons, scenarios, drills, problem
text): 506,971 sentences (corpus sha256 `6e1ca0e622c1ee07`), **0 left out**. Serialized test data
(strings starting with `[` or `{`) isn't answer-like and is skipped; an earlier v6 draft cut
`[[1, 2], [3, 4]]` matrices in problem text as markup, which is why `[[…]]` must now start with a
word. A test scans every 20th question (33,195 sentences).

**What this does not show.** The challenge set was written by a separate session, but the tuning
session read every case while building v6, so 0/45 is a development figure, not a measure of
attacks nobody has written; the families-set number (0/9) is no more independent. An attack in
plain answer-like words ("Everything an interviewer looks for is in what I just said") still reads
as the answer; it earns nothing unless its words show a point. The boundary never decides whether something happened:
a learner who simply claims an action is credited for it, with or without an attack around it.

## Results: requests to Claude and provider failures

Without calling Claude (measured 2026-11-03):

- **Requests:** 2,079 recorded across all 300 problems (every hint level, a review and two
  failure explanations each). Framing, ladder, hidden tests, secrets and limits: **0 failures**.
  Hidden-test checks covered 293 problems; 7 have no hidden value that differs from their public
  data, so a leak there couldn't be detected and they're reported as unverifiable.
- **Provider failures, before:** 24 of 30 scenario × action checks fell back. **A reply cut off
  mid-JSON, or one the SDK couldn't validate, escaped as an error**: the SDK validates
  structured output while parsing (`messages.parse` raises pydantic's `ValidationError` before
  `stop_reason` can be read), and an unexpected response body raises
  `APIResponseValidationError`; neither was caught, so the learner would have seen a 500 instead
  of the offline coach. **After** catching both as `ProviderError`: **30 of 30**. The client's
  own limits are recorded: 60 s timeout, 2 retries.

**The request boundary, 2026-11-04 (overnight task 5; prompt version `coach-2026-11-04`, prompt
text unchanged).** Audited against timeouts, rate limits, cut-off and invalid replies, missing
fields, invalid values and references that don't exist in the learner's code. Found and fixed:
- **No overall time limit.** The SDK retried up to twice at 60 s a request, so one coaching
  answer could wait about three minutes before the offline coach answered. Now the SDK's own
  retries are off and the coach retries only what a retry can fix (a timeout, a lost connection,
  408/409, 5xx, 529): **at most 3 requests, 25 s each, 45 s in all**, never starting one with
  under 5 s left. A 429 falls back at once; a refusal, a cut-off or invalid reply isn't retried.
  Tested with a simulated clock (no sleeps): two 20 s timeouts end at 45 s or sooner, without a
  third request.
- **Retries were invisible to the paid-call limit.** `--max-calls` counted coaching answers, but
  each could be three billed requests. It now counts every request before it is sent, so the
  limit holds per request (tested: a limit of 2 stops the third request of a failing answer).
- **Line references weren't checked.** A review issue or failure explanation pointing at a line
  the learner's code doesn't have is kept, with the reference dropped (and counted in the log).
  Schema checks already reject missing fields, wrong types and out-of-range values (interview
  scores are 1–4, ratings and confidence are fixed sets) before anything is shown.
- **Reasons weren't in the logs.** A failure is logged once, as `anthropic request failed` with a
  reason code (timeout, connection, rate_limited, http_5xx, http_4xx, refusal, cut_off,
  invalid_output, invalid_body) and the number of requests, under the JSON log's `attrs`; a test
  checks that no learner text or API key reaches any log record.

Provider failures: **33 of 33** fall back to the offline coach (a reply missing fields with an
unknown confidence level added as a scenario). These are tests with a fake client: they show the
boundary handles these failures, not how well Claude coaches; no live call was made. The career
written-answer coach is offline only, so its evidence spans are checked by the career evidence
gate, not here.

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

Not run: there's no API key in this environment, so **no claim is made about Claude's review,
hint or explanation quality**. A run is deliberate, budgeted and labelled as external:

```bash
cd backend
AI_PROVIDER=anthropic ANTHROPIC_API_KEY=… python -m evals.run --provider anthropic \
  --allow-paid-calls --max-calls 200 --label claude-<date> \
  [--price-input-per-mtok X --price-output-per-mtok Y --price-source <where the prices came from>]
```

Without `--allow-paid-calls` and a `--max-calls` budget it refuses. The report records the
model the API reported, effort, tokens, latency and failures from the actual responses; cost
only from the prices you pass in (none are assumed); running out of budget marks the run
partial. Compare it with the offline report using `--compare`. If an LLM is later used to judge
career answers, it's an imperfect proxy: check a representative subset by hand, keep the
disagreements, and don't treat agreement between models as proof of correctness or of the
absence of bias.

## Guarding against regressions
`tests/test_evals.py` runs the complete offline evaluation in CI and fails if any release gate
fails. `tests/test_eval_harness.py` checks the harness itself: case selection, held-out
separation, provenance and hashes, prompt versions, invalid output, provider failures,
redaction, the weakened coaches above, report integrity, partial runs, comparisons and the
paid-run guard. The held-out coding sets are reported, never tuned against.
