"""Build app/seed/problems/*.json and app/seed/reference/*.java from the problem bank.

    python -m scripts.problembank.build          (from backend/)

Expected outputs come from each spec's Python model. Run scripts/verify_reference_solutions.py
afterwards (CI does) to prove the Java references agree on every test.
"""

from __future__ import annotations

import copy
import importlib
import json
import pkgutil
import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from scripts import problembank  # noqa: E402
from scripts.problembank import REGISTRY, Spec  # noqa: E402

SEED = BACKEND / "app" / "seed" / "problems"
REFERENCE = BACKEND / "app" / "seed" / "reference"
LEVEL_ORDER = {"easy": 0, "medium": 1, "hard": 2}
DEFAULTS = {
    "int": "0",
    "long": "0L",
    "boolean": "false",
    "char": "' '",
    "String": '""',
    "int[]": "new int[0]",
    "String[]": "new String[0]",
    "int[][]": "new int[0][]",
}


def load_specs() -> list[Spec]:
    REGISTRY.clear()
    for mod in sorted(m.name for m in pkgutil.iter_modules(problembank.__path__)):
        if mod == "build":
            continue
        name = f"scripts.problembank.{mod}"
        if name in sys.modules:
            importlib.reload(sys.modules[name])  # re-run so its specs register again
        else:
            importlib.import_module(name)
    return list(REGISTRY)


def fmt(value: object) -> str:
    """How a value is shown in examples: Java-ish literals."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(fmt(v) for v in value) + "]"
    return str(value)


def starter(sig: dict) -> str:
    params = ", ".join(f"{p['type']} {p['name']}" for p in sig["params"])
    return (
        "class Solution {\n"
        f"    public {sig['returns']} {sig['method']}({params}) {{\n"
        "        // TODO: write your solution here\n"
        f"        return {DEFAULTS[sig['returns']]};\n"
        "    }\n"
        "}\n"
    )


def check_type(value: object, java_type: str, where: str) -> None:
    ok = {
        "int": lambda v: isinstance(v, int) and not isinstance(v, bool) and -(2**31) <= v < 2**31,
        "long": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "char": lambda v: isinstance(v, str) and len(v) == 1,
        "String": lambda v: isinstance(v, str),
        "int[]": lambda v: (
            isinstance(v, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in v)
        ),
        "String[]": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
        "int[][]": lambda v: isinstance(v, list) and all(isinstance(r, list) for r in v),
    }[java_type](value)
    if not ok:
        raise TypeError(f"{where}: {value!r} is not a valid {java_type}")


def build_one(spec: Spec, order: int) -> dict:
    sig = spec.signature
    rng = random.Random(spec.slug)
    inputs, seen_inputs = list(spec.tests), {json.dumps(t, sort_keys=True) for t in spec.tests}
    if spec.gen:
        # Draw until we have gen_count new, distinct inputs (small spaces repeat; give up after a while).
        added = attempts = 0
        while added < spec.gen_count and attempts < spec.gen_count * 25:
            attempts += 1
            candidate = spec.gen(rng)
            key = json.dumps(candidate, sort_keys=True)
            if key not in seen_inputs:
                seen_inputs.add(key)
                inputs.append(candidate)
                added += 1
    tests, seen = [], set()
    for i, inp in enumerate(inputs):
        key = json.dumps(inp, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        if set(inp) != {p["name"] for p in sig["params"]}:
            raise ValueError(f"{spec.slug} test {i}: input keys {sorted(inp)} don't match the signature")
        for p in sig["params"]:
            check_type(inp[p["name"]], p["type"], f"{spec.slug} test {i} input {p['name']}")
        expected = spec.model(**copy.deepcopy(inp))
        check_type(expected, sig["returns"], f"{spec.slug} test {i} expected output")
        tests.append(
            {
                "input": inp,
                "expected_output": expected,
                "visibility": "public" if len(tests) < spec.public else "hidden",
            }
        )
    if sum(t["visibility"] == "hidden" for t in tests) < 3:
        raise ValueError(f"{spec.slug}: needs at least 3 hidden tests")
    examples = []
    for i, t in enumerate(tests[: spec.public]):
        ex = {
            "input": ", ".join(f"{p['name']} = {fmt(t['input'][p['name']])}" for p in sig["params"]),
            "output": fmt(t["expected_output"]),
        }
        if i in spec.explain:
            ex["explanation"] = spec.explain[i]
        examples.append(ex)
    if len(spec.hints) != 4:
        raise ValueError(f"{spec.slug}: needs exactly 4 hints")
    return {
        "order": order,
        "slug": spec.slug,
        "title": spec.title,
        "difficulty": spec.difficulty,
        "topics": spec.topics,
        "summary": spec.summary,
        "statement": spec.statement,
        "constraints": spec.constraints,
        "examples": examples,
        "signature": sig,
        "starter_code": starter(sig),
        "hints": spec.hints,
        "expected_complexity": {"time": spec.time, "space": spec.space},
        "tests": tests,
    }


def main() -> int:
    specs = sorted(load_specs(), key=lambda s: LEVEL_ORDER[s.difficulty])  # stable within a level
    existing = {json.loads(f.read_text())["slug"]: f for f in SEED.glob("*.json")}
    hand_written = [s for s, f in existing.items() if not json.loads(f.read_text()).get("bank")]
    clash = {s.slug for s in specs} & set(hand_written)
    if clash:
        raise SystemExit(f"bank slugs clash with hand-written problems: {sorted(clash)}")
    if len({s.slug for s in specs}) != len(specs):
        raise SystemExit("duplicate slug in the bank")
    for f in SEED.glob("*.json"):  # rebuild bank files from scratch
        if json.loads(f.read_text()).get("bank"):
            f.unlink()
    start = 100
    for i, spec in enumerate(specs):
        order = start + i
        data = build_one(spec, order)
        data["bank"] = True
        (SEED / f"{order:03d}-{spec.slug}.json").write_text(json.dumps(data, indent=2) + "\n")
        (REFERENCE / f"{spec.slug}.java").write_text(spec.java)
    print(f"Built {len(specs)} problems from the bank.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
