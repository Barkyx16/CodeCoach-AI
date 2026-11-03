"""Learn mode: short, versioned learning units that teach a skill before it's assessed.

A unit is authored in this repository (see `units.py` and docs/LEARN_CONTENT.md), never generated
on a page view. Each unit has a version; learner progress records the version it happened on, so
revising a unit keeps everyone's history and shows which version they used.

Coverage is deliberately small and explicit: a few units for Software Engineer and Registered
Nurse. Other careers have none yet, and the API says so instead of pretending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ReviewStatus = Literal["author_reviewed", "generated_draft"]


@dataclass(frozen=True)
class Reference:
    title: str
    publisher: str
    url: str | None = None  # None: no link recorded (never a guessed URL)
    published: str | None = None  # version or publication date, when known
    kind: Literal["external", "repository"] = "external"
    note: str | None = None


@dataclass(frozen=True)
class Review:
    status: ReviewStatus
    by: str
    on: str  # ISO date
    note: str


@dataclass(frozen=True)
class Example:
    title: str
    intro: str
    code: str | None = None  # shown as an accessible code block
    language: str | None = None
    walkthrough: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckQuestion:
    id: str
    prompt: str
    options: tuple[str, ...]
    answer: int  # index into options; never sent to the browser before an attempt
    explanation: str


@dataclass(frozen=True)
class Exercise:
    prompt: str
    draft_label: str  # "Your code" or "Your answer"
    # Guided mode reveals these in order: a question to think about, a concept, an example, then
    # the fuller explanation.
    think: str
    concept: str
    example: str
    explanation: str
    solution: str  # independent mode: hidden until explicitly requested
    solution_language: str | None = None


@dataclass(frozen=True)
class Practice:
    kind: Literal["question", "problem"]
    ref_id: str
    label: str


@dataclass(frozen=True)
class Unit:
    id: str
    track: str
    version: int
    changes: tuple[str, ...]  # what changed in each version, newest last
    title: str
    skill: str | None  # a career skill (links the unit to the practice plan), or None
    topics: tuple[str, ...]  # coding problem topics it prepares for
    minutes: int
    objective: str
    prerequisites: tuple[str, ...]  # unit ids
    explanation: tuple[str, ...]
    example: Example
    mistakes: tuple[str, ...]
    exercise: Exercise
    check: tuple[CheckQuestion, ...]
    practice: Practice
    references: tuple[Reference, ...]
    review: Review
    scope_note: str | None = None  # regulated careers: scope and jurisdiction, shown prominently
    question_ids: tuple[str, ...] = field(default=())  # questions this unit prepares for


PASS_RULE = "Every answer in the check is right."


def _registry() -> dict[str, Unit]:
    from app.learn.units import UNITS

    out: dict[str, Unit] = {}
    for u in UNITS:
        if u.id in out:
            raise ValueError(f"duplicate unit id {u.id}")
        out[u.id] = u
    return out


UNIT_INDEX: dict[str, Unit] = _registry()


def get_unit(unit_id: str) -> Unit | None:
    return UNIT_INDEX.get(unit_id)


def units_for(track: str) -> list[Unit]:
    return [u for u in UNIT_INDEX.values() if u.track == track]


def tracks_with_units() -> list[str]:
    return sorted({u.track for u in UNIT_INDEX.values()})
