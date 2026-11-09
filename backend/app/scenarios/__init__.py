"""Branching scenarios: authored graphs of nodes and transitions, validated before use.

A scenario is data (see `content.py` and docs/SCENARIOS.md). Every transition comes from the
graph; the server walks it, so a client can't jump to an ending. Feedback on decisions is
authored with the scenario ("decision rules"); no model is involved.

Node kinds
- info:    reveals information, then `next`
- choice:  options, each with its own `to`, an authored `quality` and `feedback`
- written: a short written response checked against authored rubric points, then `next`
- prioritize: a fictional work queue; the learner orders every task and explains the first
  actions. Hard constraints (a task that needs another first; a deadline the case says can't be
  missed) are checked deterministically on the order; tradeoffs (urgency, impact,
  communication) are an authored rubric on the reasoning, and named strategies say which
  reasonable approach the order follows. Several orders can be valid. An order that breaks a hard
  constraint goes to `invalid_next` when the case authors a consequence for it, else to `next`.
- ending:  a simulated outcome and its debrief text

Validation (`validate`) rejects: a missing start, transitions to unknown nodes, nodes that can't
be reached, non-ending nodes with no way out, required endings that can't be reached, and any
cycle (scenarios are acyclic, so every attempt is bounded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.learn import Reference, Review

Quality = Literal["strong", "acceptable", "risky"]


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    to: str
    quality: Quality
    feedback: str  # the authored decision rule, shown in the debrief


@dataclass(frozen=True)
class RubricPoint:
    id: str
    label: str
    keywords: tuple[str, ...]  # any of these (as words or phrases) counts as covering the point


@dataclass(frozen=True)
class Task:
    """One item in a work queue (prioritize nodes). Its facts are all the learner gets; a
    dependency or a hard deadline must also be stated in them, in plain words."""

    id: str
    title: str
    facts: tuple[str, ...]
    minutes: int  # the case's estimate, stated in the facts; tasks are done one after another
    due: str | None = None  # "HH:MM" on the node's clock, as the case states it
    due_is_hard: bool = False  # True: finishing later is impossible in the case, not just worse
    consequence: str | None = None  # what the case says happens if it waits (authored, simulated)


@dataclass(frozen=True)
class Dependency:
    first: str  # the task that has to come first
    then: str  # the task that needs it
    why: str


@dataclass(frozen=True)
class Strategy:
    """A reasonable approach, defined by the order of some pairs of tasks; an order follows it
    when every pair is in that order. Strategies aren't ranked: each says what it gives up."""

    id: str
    label: str
    before: tuple[tuple[str, str], ...]
    explanation: str


@dataclass(frozen=True)
class Node:
    id: str
    kind: Literal["info", "choice", "written", "prioritize", "ending"]
    title: str
    text: str
    next: str | None = None  # info, written, prioritize
    options: tuple[Option, ...] = ()  # choice
    rubric: tuple[RubricPoint, ...] = ()  # written; prioritize (the tradeoffs, on the reasoning)
    outcome: str | None = None  # ending: a short label
    debrief: str | None = None  # ending
    clock: str | None = None  # prioritize: "HH:MM" when the queue starts
    tasks: tuple[Task, ...] = ()  # prioritize
    dependencies: tuple[Dependency, ...] = ()  # prioritize: hard constraints
    strategies: tuple[Strategy, ...] = ()  # prioritize: reasonable approaches, two or more
    invalid_next: str | None = None  # prioritize: where an order breaking a hard constraint goes


@dataclass(frozen=True)
class Scenario:
    id: str
    track: str
    version: int
    changes: tuple[str, ...]
    title: str
    role: str
    objective: str
    minutes: int
    scope: str
    start: str
    nodes: tuple[Node, ...]
    required_endings: tuple[str, ...]
    references: tuple[Reference, ...]
    review: Review
    regulated: bool = False
    _index: dict[str, Node] = field(default_factory=dict, compare=False, repr=False)

    def node(self, node_id: str) -> Node | None:
        if not self._index:
            self._index.update({n.id: n for n in self.nodes})
        return self._index.get(node_id)


class ScenarioError(ValueError):
    pass


def _targets(n: Node) -> list[str]:
    if n.kind == "choice":
        return [o.to for o in n.options]
    out = [n.next] if n.next else []
    if n.kind == "prioritize" and n.invalid_next and n.invalid_next not in out:
        out.append(n.invalid_next)
    return out


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _clock(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def _acyclic(ids: set[str], pairs: list[tuple[str, str]]) -> bool:
    after: dict[str, set[str]] = {i: set() for i in ids}
    indegree = dict.fromkeys(ids, 0)
    for a, b in set(pairs):
        if b not in after[a]:
            after[a].add(b)
            indegree[b] += 1
    ready = [i for i, d in indegree.items() if d == 0]
    seen = 0
    while ready:
        i = ready.pop()
        seen += 1
        for j in after[i]:
            indegree[j] -= 1
            if indegree[j] == 0:
                ready.append(j)
    return seen == len(ids)


def _some_valid_order(n: Node, extra: tuple[tuple[str, str], ...] = ()) -> list[str] | None:
    """An order meeting every hard constraint (and the extra pairs), or None. Exhaustive: queues
    are small (at most 8 tasks), so this is the honest check that a case is solvable."""
    from itertools import permutations

    for order in permutations([t.id for t in n.tasks]):
        if not order_check(n, list(order))["violations"] and all(
            order.index(a) < order.index(b) for a, b in extra
        ):
            return list(order)
    return None


def _validate_queue(s: Scenario, n: Node) -> None:
    where = f"{s.id}: queue '{n.id}'"
    ids = [t.id for t in n.tasks]
    if not 3 <= len(ids) <= 8 or len(set(ids)) != len(ids):
        raise ScenarioError(f"{where} needs 3 to 8 tasks with distinct ids")
    if not n.clock or not n.rubric:
        raise ScenarioError(f"{where} needs a clock and rubric points for the reasoning")
    for t in n.tasks:
        if not t.facts or t.minutes <= 0 or (t.due_is_hard and not t.due):
            raise ScenarioError(
                f"{where}: task '{t.id}' needs facts, minutes, and a time for a hard deadline"
            )
    known = set(ids)
    for d in n.dependencies:
        if d.first not in known or d.then not in known or d.first == d.then or not d.why:
            raise ScenarioError(
                f"{where}: dependency {d.first} -> {d.then} needs two of its tasks and a reason"
            )
    if not _acyclic(known, [(d.first, d.then) for d in n.dependencies]):
        raise ScenarioError(f"{where}: its dependencies go round in a circle")
    if _some_valid_order(n) is None:
        raise ScenarioError(f"{where}: no order meets every hard constraint")
    if len(n.strategies) < 2 or len({x.id for x in n.strategies}) != len(n.strategies):
        raise ScenarioError(f"{where} needs at least two strategies with distinct ids")
    for x in n.strategies:
        if not x.before or any(a not in known or b not in known for a, b in x.before) or not x.explanation:
            raise ScenarioError(f"{where}: strategy '{x.id}' needs pairs of its tasks and an explanation")
        if _some_valid_order(n, x.before) is None:
            raise ScenarioError(
                f"{where}: strategy '{x.id}' can't be followed without breaking a hard constraint"
            )
    if n.invalid_next and not (n.dependencies or any(t.due_is_hard for t in n.tasks)):
        raise ScenarioError(f"{where}: invalid_next without any hard constraint to break")


def order_check(n: Node, order: list[str]) -> dict[str, object]:
    """Times, broken hard constraints and the strategies an order follows (prioritize nodes).

    `order` must already be a permutation of the node's task ids. Tasks are done one after
    another from the node's clock, at the case's own estimates."""
    by_id = {t.id: t for t in n.tasks}
    pos = {task_id: i for i, task_id in enumerate(order)}
    at = _minutes(n.clock or "00:00")
    plan = []
    violations: list[dict[str, str]] = []
    for task_id in order:
        t = by_id[task_id]
        start, at = at, at + t.minutes
        late = t.due is not None and at > _minutes(t.due)
        plan.append(
            {
                "id": t.id,
                "title": t.title,
                "start": _clock(start),
                "finish": _clock(at),
                "due": t.due,
                "late": late,
            }
        )
        if late and t.due_is_hard:
            violations.append(
                {
                    "kind": "deadline",
                    "text": f"{t.title} has to be finished by {t.due}; in this order it finishes at {_clock(at)}.",
                }
            )
    for d in n.dependencies:
        if pos[d.then] < pos[d.first]:
            violations.append(
                {
                    "kind": "dependency",
                    "text": f"{by_id[d.then].title} comes before {by_id[d.first].title}, but it needs it first: {d.why}",
                }
            )
    follows = [x for x in n.strategies if all(pos[a] < pos[b] for a, b in x.before)]
    return {
        "plan": plan,
        "violations": violations,
        "follows": [{"label": x.label, "explanation": x.explanation} for x in follows],
        "others": [
            {"label": x.label, "explanation": x.explanation} for x in n.strategies if x not in follows
        ],
    }


def validate(s: Scenario) -> None:
    ids = [n.id for n in s.nodes]
    if len(ids) != len(set(ids)):
        raise ScenarioError(f"{s.id}: duplicate node ids")
    by_id = {n.id: n for n in s.nodes}
    if s.start not in by_id:
        raise ScenarioError(f"{s.id}: start node '{s.start}' is missing")
    for n in s.nodes:
        if n.kind == "ending":
            if n.next or n.options or not n.outcome or not n.debrief:
                raise ScenarioError(f"{s.id}: ending '{n.id}' needs an outcome and debrief and no way out")
            continue
        if n.kind == "choice":
            if len(n.options) < 2 or len({o.id for o in n.options}) != len(n.options):
                raise ScenarioError(f"{s.id}: choice '{n.id}' needs at least two options with distinct ids")
        elif not n.next:
            raise ScenarioError(f"{s.id}: '{n.id}' has no way out")
        if n.kind == "written" and not n.rubric:
            raise ScenarioError(f"{s.id}: written node '{n.id}' needs rubric points")
        if n.kind == "prioritize":
            _validate_queue(s, n)
        elif n.tasks or n.dependencies or n.strategies or n.invalid_next:
            raise ScenarioError(f"{s.id}: only a prioritize node has tasks")
        for t in _targets(n):
            if t not in by_id:
                raise ScenarioError(f"{s.id}: '{n.id}' leads to unknown node '{t}'")
    # Reachability from the start.
    seen: set[str] = set()
    queue = [s.start]
    while queue:
        node_id = queue.pop()
        if node_id not in seen:
            seen.add(node_id)
            queue.extend(_targets(by_id[node_id]))
    # Cycles (Kahn's algorithm): if some nodes can never be ordered, they sit on a cycle.
    indegree = dict.fromkeys(by_id, 0)
    for n in s.nodes:
        for t in _targets(n):
            indegree[t] += 1
    ready = [i for i, d in indegree.items() if d == 0]
    ordered = 0
    while ready:
        node_id = ready.pop()
        ordered += 1
        for t in _targets(by_id[node_id]):
            indegree[t] -= 1
            if indegree[t] == 0:
                ready.append(t)
    if ordered != len(by_id):
        looped = sorted(i for i, d in indegree.items() if d > 0)
        raise ScenarioError(f"{s.id}: cycle through {looped}")
    unreachable = set(by_id) - seen
    if unreachable:
        raise ScenarioError(f"{s.id}: unreachable nodes {sorted(unreachable)}")
    for e in s.required_endings:
        if e not in by_id or by_id[e].kind != "ending":
            raise ScenarioError(f"{s.id}: required ending '{e}' is missing")
        if e not in seen:
            raise ScenarioError(f"{s.id}: required ending '{e}' can't be reached")


def check_written(node: Node, text: str) -> tuple[list[str], list[str]]:
    """(covered, missing) rubric point labels for a written response."""
    low = f" {' '.join(text.lower().split())} "
    covered: list[str] = []
    missing: list[str] = []
    for p in node.rubric:
        hit = any(f" {k} " in low or (len(k) > 4 and k in low) for k in p.keywords)
        (covered if hit else missing).append(p.label)
    return covered, missing


def _registry() -> dict[str, Scenario]:
    from app.scenarios.content import SCENARIOS

    out: dict[str, Scenario] = {}
    for s in SCENARIOS:
        validate(s)
        if s.id in out:
            raise ScenarioError(f"duplicate scenario id {s.id}")
        out[s.id] = s
    return out


SCENARIO_INDEX: dict[str, Scenario] = _registry()


def get_scenario(scenario_id: str) -> Scenario | None:
    return SCENARIO_INDEX.get(scenario_id)


def scenarios_for(track: str) -> list[Scenario]:
    return [s for s in SCENARIO_INDEX.values() if s.track == track]
