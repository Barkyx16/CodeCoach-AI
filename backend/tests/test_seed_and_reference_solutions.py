"""Validates the curated content itself, not just the code around it."""

import importlib.util
import shutil
from pathlib import Path

import pytest

from app.db.seed import SEED_DIR, load_seed_files
from app.services.judge.harness import SUPPORTED_TYPES

PROBLEMS = load_seed_files()
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_reference_solutions.py"


def test_slugs_unique_and_ordered():
    slugs = [p["slug"] for p in PROBLEMS]
    assert len(slugs) == len(set(slugs)) >= 10
    assert [p["order"] for p in PROBLEMS] == sorted(p["order"] for p in PROBLEMS)


@pytest.mark.parametrize("problem", PROBLEMS, ids=lambda p: p["slug"])
def test_problem_content_is_complete(problem):
    assert problem["difficulty"] in {"easy", "medium", "hard"}
    assert len(problem["hints"]) == 4, "progressive ladder: nudge, concept, pseudocode, explanation"
    vis = [t["visibility"] for t in problem["tests"]]
    assert vis.count("public") >= 2 and vis.count("hidden") >= 3
    sig = problem["signature"]
    assert {p["type"] for p in sig["params"]} | {sig["returns"]} <= SUPPORTED_TYPES
    for t in problem["tests"]:
        assert set(t["input"]) == {p["name"] for p in sig["params"]}
    assert f"{sig['method']}(" in problem["starter_code"] and "class Solution" in problem["starter_code"]
    assert problem["expected_complexity"]["time"].startswith("O(")


@pytest.mark.skipif(shutil.which("javac") is None, reason="JDK not installed")
@pytest.mark.parametrize("problem_file", sorted(SEED_DIR.glob("*.json")), ids=lambda f: f.stem)
def test_reference_solution_passes_all_tests(problem_file):
    """Compiles the repo's own trusted reference solution and runs every test case through
    the real driver. Proves the expected outputs are right before a learner ever sees them."""
    spec = importlib.util.spec_from_file_location("verify_reference_solutions", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.check_problem(problem_file) == []


@pytest.mark.skipif(shutil.which("javac") is None, reason="JDK not installed")
def test_starter_code_fails_tests(tmp_path, monkeypatch):
    """Sanity check that the tests are meaningful: the untouched starter code must fail."""
    spec = importlib.util.spec_from_file_location("verify_reference_solutions", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    problem_file = SEED_DIR / "03-two-sum.json"
    ref_dir = tmp_path / "ref"
    ref_dir.mkdir()
    import json

    (ref_dir / "two-sum.java").write_text(json.loads(problem_file.read_text())["starter_code"])
    monkeypatch.setattr(module, "REFERENCE_DIR", ref_dir)
    assert module.check_problem(problem_file), "starter code unexpectedly passed every test"
