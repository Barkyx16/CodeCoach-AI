"""The coding problem bank: one compact spec per problem, built into app/seed by build.py.

Each spec carries two independent implementations: `model` (plain Python, written for clarity,
often brute force) computes every expected output, and `java` (the reference solution, written
for the target complexity) must reproduce them through the real judge driver. A shared
misunderstanding would have to be made twice, in two languages, to slip through.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

REGISTRY: list[Spec] = []


@dataclass
class Spec:
    slug: str
    title: str
    difficulty: str
    topics: list[str]
    summary: str
    statement: str
    constraints: list[str]
    sig: str  # "int[] twoSum(int[] nums, int target)"
    hints: list[str]
    time: str
    space: str
    model: Callable[..., Any]
    java: str
    tests: list[dict]  # hand-picked inputs; the first `public` are shown to learners
    gen: Callable[[random.Random], dict] | None = None
    gen_count: int = 4
    public: int = 3
    explain: dict[int, str] = field(default_factory=dict)  # example explanations by test index

    @property
    def signature(self) -> dict:
        m = re.fullmatch(r"\s*([\w\[\]]+)\s+(\w+)\((.*)\)\s*", self.sig)
        if not m:
            raise ValueError(f"bad signature: {self.sig}")
        returns, method, params = m.groups()
        parsed = []
        for part in [p.strip() for p in params.split(",") if p.strip()]:
            ptype, pname = part.rsplit(" ", 1)
            parsed.append({"name": pname, "type": ptype.strip()})
        return {"method": method, "params": parsed, "returns": returns}


def P(**kwargs: Any) -> Spec:
    spec = Spec(**kwargs)
    spec.statement = _dedent(spec.statement)
    spec.java = _dedent(spec.java) + "\n"
    spec.hints = [_dedent(h) for h in spec.hints]
    REGISTRY.append(spec)
    return spec


def _dedent(text: str) -> str:
    import textwrap

    return textwrap.dedent(text).strip("\n")


# Helpers for seeded random test inputs (deterministic per problem slug).
def ints(rng: random.Random, n_lo: int, n_hi: int, lo: int, hi: int) -> list[int]:
    return [rng.randint(lo, hi) for _ in range(rng.randint(n_lo, n_hi))]


def word(rng: random.Random, n_lo: int, n_hi: int, alphabet: str = "abcdefghijklmnopqrstuvwxyz") -> str:
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(n_lo, n_hi)))


def grid(rng: random.Random, rows: int, cols: int, lo: int, hi: int) -> list[list[int]]:
    return [[rng.randint(lo, hi) for _ in range(cols)] for _ in range(rows)]
