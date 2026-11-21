"""The whiteboard diagram format and its evaluation.

A diagram is small and plain on purpose: labelled components, labelled connections between them,
an optional group name, positions on a grid, and four notes (assumptions, requirements,
capacity, tradeoffs). No HTML, images or scripts: every string is plain text with a length
limit, so an imported file can't carry active content.

Evaluation is deterministic and has two clearly separate parts:
- **Checks** of the diagram's structure (broken connections, unnamed components, components
  with no connections). These are facts about the file.
- **Rubric feedback**: which of the prompt's requirements the learner's own labels, notes and
  explanation address, with the exact element ids as evidence. It says what's present, not
  whether a design is correct, secure or production-ready, and never judges how it looks.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.whiteboard import RUBRIC_VERSION, Prompt

MAX_NODES = 40
MAX_EDGES = 80
NodeKind = Literal["client", "service", "database", "cache", "queue", "external", "other"]
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ID = r"^[a-z][a-z0-9-]{0,15}$"


def _text(v: str) -> str:
    return _CONTROL.sub("", v).strip()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields in an imported file are refused


class WhiteboardNode(Strict):
    id: str = Field(pattern=_ID)
    label: str = Field(max_length=60)
    kind: NodeKind = "service"
    x: int = Field(ge=0, le=4000)
    y: int = Field(ge=0, le=4000)
    group: str | None = Field(default=None, max_length=40)

    _clean = field_validator("label", "group")(lambda v: _text(v) if isinstance(v, str) else v)


class WhiteboardEdge(Strict):
    id: str = Field(pattern=_ID)
    source: str = Field(pattern=_ID)
    target: str = Field(pattern=_ID)
    label: str = Field(default="", max_length=60)

    _clean = field_validator("label")(lambda v: _text(v))


class WhiteboardNotes(Strict):
    assumptions: str = Field(default="", max_length=2000)
    requirements: str = Field(default="", max_length=2000)
    capacity: str = Field(default="", max_length=2000)
    tradeoffs: str = Field(default="", max_length=2000)

    _clean = field_validator("assumptions", "requirements", "capacity", "tradeoffs")(lambda v: _text(v))


class WhiteboardDiagram(Strict):
    format: Literal["codecoach-whiteboard"] = "codecoach-whiteboard"
    version: Literal[1] = 1
    nodes: list[WhiteboardNode] = Field(default_factory=list, max_length=MAX_NODES)
    edges: list[WhiteboardEdge] = Field(default_factory=list, max_length=MAX_EDGES)
    notes: WhiteboardNotes = Field(default_factory=WhiteboardNotes)


def digest(d: WhiteboardDiagram) -> str:
    """A fingerprint of the diagram's content, to tell an edited draft from an evaluated one."""
    payload = d.model_dump(exclude={"format", "version"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def checks(d: WhiteboardDiagram) -> list[dict]:
    """Structural facts, each with the element ids it's about."""
    out: list[dict] = []
    ids = [n.id for n in d.nodes]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        out.append(
            {"ok": False, "message": f"Two components share an id: {', '.join(dupes)}.", "refs": dupes}
        )
    known = set(ids)
    edge_ids = [e.id for e in d.edges]
    for e in d.edges:
        missing = [x for x in (e.source, e.target) if x not in known]
        if missing:
            out.append(
                {
                    "ok": False,
                    "message": f"Connection {e.id} points to a component that isn't there ({', '.join(missing)}).",
                    "refs": [e.id],
                }
            )
        elif e.source == e.target:
            out.append(
                {"ok": False, "message": f"Connection {e.id} connects a component to itself.", "refs": [e.id]}
            )
    if len(set(edge_ids)) != len(edge_ids):
        out.append(
            {
                "ok": False,
                "message": "Two connections share an id.",
                "refs": sorted({i for i in edge_ids if edge_ids.count(i) > 1}),
            }
        )
    unnamed = [n.id for n in d.nodes if not n.label]
    if unnamed:
        out.append({"ok": False, "message": "Some components have no name.", "refs": unnamed})
    linked = {e.source for e in d.edges} | {e.target for e in d.edges}
    lonely = [n.id for n in d.nodes if n.id not in linked]
    groups: dict[str, int] = {}
    for n in d.nodes:
        if n.group:
            groups[n.group] = groups.get(n.group, 0) + 1
    if lonely and len(d.nodes) > 1:
        out.append({"ok": False, "message": "Some components aren't connected to anything.", "refs": lonely})
    if not d.nodes:
        out.append(
            {
                "ok": False,
                "message": "The diagram is empty, so only your notes and explanation were read.",
                "refs": [],
            }
        )
    if not out:
        grouped = f" in {len(groups)} group{'s' if len(groups) != 1 else ''}" if groups else ""
        out.append(
            {
                "ok": True,
                "message": f"{len(d.nodes)} components{grouped} and {len(d.edges)} connections, all named and connected.",
                "refs": [],
            }
        )
    return out


def _hits(keywords: tuple[str, ...], text: str) -> bool:
    low = text.lower()
    return any(re.search(rf"(?<![a-z]){re.escape(k)}", low) for k in keywords)


def evaluate(prompt: Prompt, d: WhiteboardDiagram, explanation: str) -> dict:
    words = len(re.findall(r"\w+", explanation))
    by_id = {n.id: n for n in d.nodes}
    rubric = []
    for r in prompt.requirements:
        evidence = [
            {"kind": "component", "id": n.id, "text": n.label} for n in d.nodes if _hits(r.keywords, n.label)
        ]
        evidence += [
            {
                "kind": "connection",
                "id": e.id,
                "text": f"{by_id[e.source].label if e.source in by_id else e.source} → {by_id[e.target].label if e.target in by_id else e.target}: {e.label}",
            }
            for e in d.edges
            if e.label and _hits(r.keywords, e.label)
        ]
        for field in ("assumptions", "requirements", "capacity", "tradeoffs"):
            if _hits(r.keywords, getattr(d.notes, field)):
                evidence.append(
                    {"kind": "note", "id": f"notes.{field}", "text": getattr(d.notes, field)[:120]}
                )
        if _hits(r.keywords, explanation):
            evidence.append({"kind": "explanation", "id": "explanation", "text": explanation[:120]})
        rubric.append(
            {"requirement": r.id, "text": r.text, "addressed": bool(evidence), "evidence": evidence[:5]}
        )
    reasoning = []
    if re.search(r"\d", d.notes.capacity):
        reasoning.append(
            {"ok": True, "message": "You gave rough numbers for capacity.", "refs": ["notes.capacity"]}
        )
    else:
        reasoning.append(
            {
                "ok": False,
                "message": "No capacity estimate yet. Rough numbers (requests per second, storage) help explain choices; they don't need to be exact.",
                "refs": ["notes.capacity"],
            }
        )
    tradeoff_text = f"{d.notes.tradeoffs} {explanation}"
    if re.search(r"\b(because|instead|trade-?off|versus|vs\.?|but|cost)\b", tradeoff_text, re.I):
        reasoning.append(
            {
                "ok": True,
                "message": "You explained at least one choice and what it costs or gives up.",
                "refs": ["notes.tradeoffs", "explanation"],
            }
        )
    else:
        reasoning.append(
            {
                "ok": False,
                "message": "Say why you chose one option over another (for example: “a cache because reads far outnumber writes”).",
                "refs": ["notes.tradeoffs"],
            }
        )
    return {
        "rubric_version": RUBRIC_VERSION,
        "prompt_version": prompt.version,
        "checks": checks(d),
        "rubric": rubric,
        "reasoning": reasoning,
        "explanation_words": words,
        "limitations": [
            "Built-in rules, not a reviewer: it finds whether your labels, notes and explanation address each point, not whether the design would work.",
            "It never judges how the diagram looks, and it doesn't certify a design as correct, secure or ready for production.",
        ],
    }


Diagram = WhiteboardDiagram  # the short name used inside the backend
