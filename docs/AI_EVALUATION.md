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
> `contract.reference_leak` (no labelled sample's reference note reaches a prompt). 25 gates in all.

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
(insufficient fails on the 4 short cases), and one that believes an answer claiming to cover
everything (injection fails on both injection cases).

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
