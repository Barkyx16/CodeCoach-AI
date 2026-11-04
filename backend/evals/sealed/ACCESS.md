# Sealed evaluation set: access log

`career_rn_sealed.json` (registered nurse) and `career_csr_sealed.json` (customer service
representative, since protocol v6) are the final, once-only measurement sets for the written-answer coach
(docs/EVAL_PROTOCOL.md). It was written by a separate agent session that saw only the protocol,
the questions and the rubric points' label and advice text. The session that tunes the coach does
not open this file or its case-level results; the tools it runs over the set print counts, ids and
hashes only. Every opening of the case text or case-level results, and every grading, is
recorded below. Once case-level results have been read for tuning, the set is consumed and a new
sealed set is needed for the next honest measurement.

| When (UTC) | What | Who / detail |
|---|---|---|
| 2026-11-04 | written | by a separate agent session from the protocol, its question file and the rubric text; 108 cases, 30 points marked uncertain |
| 2026-11-04 | revised | the duplicate check (ids only) flagged 4 keyword_list answers as near-identical to development answers (1 exact); the authoring session rewrote its side; nothing was shown to the tuning session |
| 2026-11-04 | registered | sha256 afedc25a6247…; the tuning session has run only the validator and duplicate check (counts and ids) |
| 2026-11-04 | written (`career_csr_sealed.json`) | by another separate agent session from the protocol, its question file (the 4th question by id of each cell) and the rubric text; 108 cases, 9 points marked uncertain; its duplicate check flagged one keyword-list answer as close to a development answer, which that session rewrote; its helper files with answer text were deleted |
| 2026-11-04 | registered (`career_csr_sealed.json`) | sha256 22af2c53d831…; the tuning session has run only the validator (counts and ids) |
