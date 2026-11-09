"""Test design against authored faulty versions (Volume 10, prompt 4; docs/TEST_DESIGN.md).

An exercise (app/seed/testdesign/*.json) is a small function specification with a trusted
reference implementation and a few faulty versions ("variants"), each with one known defect. The
learner proposes cases (inputs and the output they expect); the cases run, in the existing isolated
judge, against the reference and every variant in one sandbox run, and the report says which
variants each case tells apart from the reference.

What decides an answer is the reference's actual output, never the learner's expectation and
never a model: a case whose expected output disagrees with the reference isn't evidence against
anything. Coverage is counted over these authored variants only.

One input shape is supported: a first parameter `int[]`, then up to two `int` parameters,
returning `int` or `boolean`. Inputs are bounded (`limits`) and checked here before anything runs.
scripts/verify_reference_solutions.py checks every exercise with a real JDK: the examples' expected
outputs are what the reference returns, each variant's witness case shows its defect, and nothing
hangs or crashes the reference on random inputs within the limits.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).resolve().parents[1] / "seed" / "testdesign"
RETURNS = ("int", "boolean")
LABELS = ("boundary", "equivalence", "edge", "other")
LABEL_TEXT = {
    "boundary": "Boundary",
    "equivalence": "Equivalence class",
    "edge": "Edge condition",
    "other": "Other",
}


@dataclass(frozen=True)
class Limits:
    max_cases: int
    max_length: int
    min_value: int
    max_value: int


@dataclass(frozen=True)
class Variant:
    id: str
    title: str
    defect: str
    gap: str
    witness: dict[str, Any]
    code: str


@dataclass(frozen=True)
class Exercise:
    slug: str
    version: int
    title: str
    summary: str
    spec: str
    signature: dict[str, Any]
    limits: Limits
    examples: tuple[dict[str, Any], ...]
    reference: str
    variants: tuple[Variant, ...]
    lesson: str | None
    review_status: str

    @property
    def params(self) -> list[dict[str, str]]:
        return list(self.signature["params"])

    @property
    def returns(self) -> str:
        return str(self.signature["returns"])

    def implementations(self) -> list[tuple[str, str]]:
        """(id, code): the reference first, then each variant."""
        return [("reference", self.reference)] + [(v.id, v.code) for v in self.variants]


def variant_key(index: int) -> str:
    """How a faulty version is named to the learner: A, B, C… (never its id)."""
    return chr(ord("A") + index)


def supported_signature(signature: dict[str, Any]) -> bool:
    params = signature.get("params") or []
    types = [p.get("type") for p in params]
    return (
        bool(types)
        and types[0] == "int[]"
        and all(t == "int" for t in types[1:])
        and len(types) <= 3
        and signature.get("returns") in RETURNS
    )


def parse(data: dict[str, Any]) -> Exercise:
    return Exercise(
        slug=data["slug"],
        version=int(data["version"]),
        title=data["title"],
        summary=data["summary"],
        spec=data["spec"],
        signature=data["signature"],
        limits=Limits(**data["limits"]),
        examples=tuple(data["examples"]),
        reference=data["reference"],
        variants=tuple(Variant(**v) for v in data["variants"]),
        lesson=data.get("lesson"),
        review_status=data["review_status"],
    )


def load(directory: Path = SEED_DIR) -> tuple[Exercise, ...]:
    return tuple(parse(json.loads(p.read_text())) for p in sorted(directory.glob("*.json")))


EXERCISES = load()
BY_SLUG = {e.slug: e for e in EXERCISES}


# -- one learner case ------------------------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def case_errors(ex: Exercise, case_input: Any, expected: Any) -> list[str]:
    """Plain-language problems with one case, or [] if it can run. Checked on the server before
    anything runs; the page shows the same messages."""
    errors: list[str] = []
    lim = ex.limits
    if not isinstance(case_input, dict):
        return ["The input must give a value for each parameter."]
    names = [p["name"] for p in ex.params]
    unknown = sorted(set(case_input) - set(names))
    if unknown:
        errors.append(f"Unknown parameter{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}.")
    for p in ex.params:
        name, kind = p["name"], p["type"]
        if name not in case_input:
            errors.append(f"{name}: give a value.")
            continue
        value = case_input[name]
        if kind == "int[]":
            if not isinstance(value, list) or not all(_is_int(v) for v in value):
                errors.append(f"{name}: a list of whole numbers, like 3, -1, 7.")
                continue
            if len(value) > lim.max_length:
                errors.append(f"{name}: at most {lim.max_length} values (this has {len(value)}).")
            if any(not lim.min_value <= v <= lim.max_value for v in value):
                errors.append(f"{name}: each value between {lim.min_value} and {lim.max_value}.")
        else:
            if not _is_int(value):
                errors.append(f"{name}: a whole number.")
            elif not lim.min_value <= value <= lim.max_value:
                errors.append(f"{name}: between {lim.min_value} and {lim.max_value}.")
    if ex.returns == "boolean":
        if not isinstance(expected, bool):
            errors.append("Expected output: true or false.")
    elif not _is_int(expected):
        errors.append("Expected output: a whole number.")
    return errors


def same_input(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# -- running every implementation in one sandbox job ----------------------------------------

_CLASS = re.compile(r"\bclass\s+Solution\b")


def class_name(index: int) -> str:
    return f"Impl{index}"


def build_sources(ex: Exercise, inputs: list[dict[str, Any]]) -> tuple[dict[str, str], int]:
    """Solution.java with the reference and every variant as classes Impl0..ImplK, and a driver
    that calls each of them on every input. The runner accepts exactly Solution.java and Main.java,
    so nothing about the sandbox changes. Returns (files, number of implementations)."""
    from app.services.judge.harness import build_driver

    impls = ex.implementations()
    solution = "\n".join(
        _CLASS.sub(f"class {class_name(k)}", code, count=1) for k, (_, code) in enumerate(impls)
    )
    flat_inputs = [case for _ in impls for case in inputs]
    targets = [class_name(k) for k in range(len(impls)) for _ in inputs]
    return {"Solution.java": solution, "Main.java": build_driver(ex.signature, flat_inputs, targets)}, len(
        impls
    )
