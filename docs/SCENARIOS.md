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
| IT Support Specialist | The 08:45 support queue (work queue) | ~6 min | 1 queue | 1 |
| Logistics Coordinator | Dispatch before the 11:00 truck (work queue) | ~8 min | 2 queues | 2 |

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
  - `prioritize`: a work queue (see [Work queues](#work-queues)), then `next`, or `invalid_next`
    when the order breaks a hard constraint and the case authors a consequence for that.
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

## Work queues

Volume 10, prompt 7. A `prioritize` node is several tasks at once instead of one conversation: the
learner orders all of them and says what they'd do first and why. It reuses everything above (the
server walks the graph, steps are snapshots, versions, "Try another approach" as a separate
attempt, the debrief), so there's no new table: the order, the reasoning and the evaluation are
part of the attempt's recorded steps.

### What a queue holds (`app/scenarios/__init__.py`, cases in `app/scenarios/queues.py`)

- `clock`: when the queue starts. Tasks are done one after another at the case's estimates.
- `tasks`: stable `id`, `title`, `facts` (everything the learner needs, in plain words: a
  dependency or a hard deadline is also stated here), `minutes`, optional `due` ("HH:MM"),
  `due_is_hard` (later is impossible in the case, not just worse) and `consequence`.
- **Hard constraints**, checked deterministically on the order: `dependencies` (`first`, `then`,
  `why`) and hard deadlines. They decide which orders are possible at all.
- **Tradeoffs**, kept separate: `rubric` points on the reasoning (urgency, impact,
  communication; the same disclosed keyword check as written nodes, not AI) and `strategies`:
  named reasonable approaches defined by pairs of tasks (`before`), each saying what it gives up.
  An order may follow none, one or several; they're never ranked, and no single order is "the"
  answer.

`validate()` also refuses a queue with fewer than 3 or more than 8 tasks, a dependency that names
another node's task or goes round in a circle, no order meeting every hard constraint (checked
exhaustively), fewer than two strategies, a strategy that can't be followed without breaking a
hard constraint, missing rubric points, and tasks on any other kind of node.

### The cases

| Case | Career | What it shows |
|---|---|---|
| The 08:45 support queue | IT Support Specialist | No impossible order: "Most people blocked first", "Fixed times first" and "A five-minute unblock first" are all defensible. Soft deadlines (Priya's 09:30 start, the 10:00 board meeting) show when each task would finish, never as broken constraints. |
| Dispatch before the 11:00 truck | Logistics Coordinator | Labels need the pick list first, and the truck slot is released at 09:00: an order breaking either is named and goes to an authored consequence. Before work starts, new information (an urgent part-order with a 09:15 courier deadline) brings a re-plan with one more task and one more dependency. 48 of the 120 first orders and 33 of the 720 re-plans are possible; two strategies are offered for each. |

Both are fictional and author-reviewed only. Regulated careers have no queue: a case claiming
what's correct for patients, clients' money or safety would need review by a practitioner first.

### The server decides

- The client sends the node, the order (every task id exactly once: `invalid_order` otherwise)
  and the reasoning (five words or more: `reasoning_required`). It can't send facts, times,
  deadlines or a verdict; extra fields are ignored. A step for any node but the current one is
  `stale_step`; a repeat of the same order and reasoning changes nothing.
- The step records the tasks and facts as shown, the order with each task's start and finish,
  the broken constraints, the strategies followed and the others, and the rubric points named.

### Information at the time

Each plan in the debrief is judged on what the case had said by then: its own tasks and facts,
and the info steps shown before it ("Judged on what you knew at 08:10, after: …"). A first plan
made before the news isn't marked down for not knowing it.

### The page

Every task's facts are on the card. Move up / Move down (focus stays on the moved task) and a
position list reorder from the keyboard; dragging works too but is never needed. The order and
the reasoning are kept on this device until sent (`scenario-queue-draft:<account>:<attempt>:<node>`,
cleared at sign-out) and offered back after a reload. The page never says whether an order is
valid before it's sent. An optional practice timer is labelled as just for the learner: it isn't
saved or sent, and nothing is judged on speed.

### Limits

- Times are the case's estimates, done strictly one at a time; there's no delegation, overlap or
  overrun. A soft deadline missed is shown, not judged.
- The rubric is keyword matching on the reasoning; it can't tell whether a reason is sound, and a
  reason phrased differently can read as "not mentioned".
- Strategies are authored; an order that follows none is still fine if it meets the hard
  constraints and its reasons hold, and the debrief says so.
- No AI. If AI commentary is added later it must stay inside the case's facts, run only when asked
  (within the existing budgets), and keep an authored consequence apart from any prediction about
  a real workplace.
