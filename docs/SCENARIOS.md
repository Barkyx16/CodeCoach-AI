# Branching scenarios: authoring and review

Scenarios are fictional situations where choices change what happens next. They're plain Python
data in [`backend/app/scenarios/content.py`](../backend/app/scenarios/content.py); the format and
validator are in [`backend/app/scenarios/__init__.py`](../backend/app/scenarios/__init__.py). Adding
a scenario needs no route or page changes: add it to `SCENARIOS` and it appears in the catalog.

## Coverage (honest)

| Career | Scenario | Estimate | Decisions | Endings |
| --- | --- | --- | --- | --- |
| Software Engineer | Checkout errors after a deploy | ~8 min | up to 2 | 3 |
| Registered Nurse | Two call lights at once | ~7 min | 2 | 2 |

Every other career shows "no scenarios yet". No scenario is validated by an outside professional
body; the nursing scenario says so on every screen.

## Format

- **Scenario**: `id`, `track`, `version` + `changes`, `title`, `role`, `objective`, `minutes`
  (author's estimate), `scope`, `start`, `nodes`, `required_endings`, `references`, `review`,
  `regulated`.
- **Nodes** have stable ids and a kind:
  - `info`: reveals information, then `next`.
  - `choice`: two or more `Option(id, label, to, quality, feedback)`; `quality` is `strong`,
    `acceptable` or `risky`, and `feedback` is the authored decision rule shown in the debrief.
  - `written`: a short response checked against `RubricPoint(id, label, keywords)` (any keyword
    covers the point; it's a simple, disclosed check, not AI), then `next`.
  - `ending`: `outcome` (labelled simulated) and `debrief`.

## Validation (run at startup and in tests)

`validate()` rejects duplicate node ids, a missing start, transitions to unknown nodes,
non-ending nodes with no way out, choices with fewer than two options, written nodes without
rubric points, unreachable nodes, required endings that can't be reached, and any cycle, so
every attempt is bounded.

## Rules

1. Fictional and scoped: state the role, objective, estimate and scope; never present a scenario
   as instructions for a live situation. Regulated careers set `regulated=True` and say they are
   not clinically validated unless that review has really happened.
2. Consequences come only from the graph. The server keeps the current node, checks every step,
   ignores where the client would like to go, and treats a repeated identical step as a no-op.
3. Feedback is authored. No model is used; the debrief says so.
4. Real references only (no guessed links), and an honest `review` note.
5. Versioning: bump `version` when the graph or feedback changes meaning. Attempts on an older
   version stay readable (each step stores a snapshot of its text and feedback) but can't be
   continued; the learner starts the new version.
