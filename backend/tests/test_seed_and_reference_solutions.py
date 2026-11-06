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


def _verifier():
    spec = importlib.util.spec_from_file_location("verify_reference_solutions", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def reference_results():
    """Every reference solution compiled and run in one JVM (fast even with hundreds of problems)."""
    return _verifier().check_all(sorted(SEED_DIR.glob("*.json")))


@pytest.fixture(scope="module")
def starter_results(tmp_path_factory):
    """The same, with each problem's untouched starter code in place of the reference."""
    ref_dir = tmp_path_factory.mktemp("starters")
    for p in PROBLEMS:
        (ref_dir / f"{p['slug']}.java").write_text(p["starter_code"])
    return _verifier().check_all(sorted(SEED_DIR.glob("*.json")), reference_dir=ref_dir)


@pytest.mark.skipif(shutil.which("javac") is None, reason="JDK not installed")
@pytest.mark.parametrize("slug", [p["slug"] for p in PROBLEMS])
def test_reference_solution_passes_all_tests(slug, reference_results):
    """Compiles the repo's own trusted reference solution and runs every test case through
    the real driver. Proves the expected outputs are right before a learner ever sees them."""
    assert reference_results[slug] == []


@pytest.mark.skipif(shutil.which("javac") is None, reason="JDK not installed")
@pytest.mark.parametrize("slug", [p["slug"] for p in PROBLEMS])
def test_starter_code_fails_tests(slug, starter_results):
    """The tests must be able to tell: every problem's untouched starter code fails at least one."""
    assert starter_results[slug], "starter code unexpectedly passed every test"


def _python_models():
    spec = importlib.util.spec_from_file_location("python_models", SCRIPT.parent / "python_models.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MODELS


@pytest.mark.parametrize("slug", sorted(_python_models()))
def test_independent_python_model_agrees_with_every_expected_output(slug):
    """Second implementation: expected outputs must match a separate Python model, not just the
    Java reference (a shared misunderstanding would have to happen twice, in two languages)."""
    model = _python_models()[slug]
    problem = next(p for p in PROBLEMS if p["slug"] == slug)
    for t in problem["tests"]:
        assert model(**t["input"]) == t["expected_output"], t["input"]
