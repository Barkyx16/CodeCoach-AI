"""Branching scenarios: authored graphs of nodes and transitions, validated before use.

A scenario is data (see `content.py` and docs/SCENARIOS.md). Every transition comes from the
graph; the server walks it, so a client can't jump to an ending. Feedback on decisions is
authored with the scenario ("decision rules"); no model is involved.

Node kinds
- info:    reveals information, then `next`
- choice:  options, each with its own `to`, an authored `quality` and `feedback`
- written: a short written response checked against authored rubric points, then `next`
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
class Node:
    id: str
    kind: Literal["info", "choice", "written", "ending"]
    title: str
    text: str
    next: str | None = None  # info, written
    options: tuple[Option, ...] = ()  # choice
    rubric: tuple[RubricPoint, ...] = ()  # written
    outcome: str | None = None  # ending: a short label
    debrief: str | None = None  # ending


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
    return [n.next] if n.next else []


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
