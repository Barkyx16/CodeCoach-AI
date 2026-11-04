"""Release gates for the offline coach, using the evaluation suite (evals/run.py).

CI runs the complete offline evaluation (every set, every section) and fails if any release
gate fails (evals/gates.py: each gate has its reason). The coding thresholds sit just under the
measured tuning-set numbers so a rule change that makes the reviewer worse fails; the held-out
coding sets are reported, never tuned against.
"""

import json
from pathlib import Path

from evals.run import run

EVALS = Path(__file__).resolve().parents[1] / "evals"


def test_the_complete_offline_evaluation_passes_every_release_gate():
    report = run("offline")
    assert report["complete"], report["incomplete_reasons"]
    failed = {g["id"]: g["failures"] for g in report["gates"] if g["status"] != "passed"}
    assert failed == {}, json.dumps(failed, indent=2)
    assert report["review_holdout"]["samples"] >= 10 and report["review_medium"]["samples"] >= 10  # reported
    assert report["hints"]["level2_relevance"] >= 0.9
    # Every career set except the sealed one, which only a sealed run grades.
    assert set(report["career"]) == {
        "career-rn-dev",
        "career-rn-holdout",
        "career-rn-families-dev",
        "career-rn-contradiction-pairs",
        "career-rn-injection-challenges",
    }


def test_eval_sets_are_well_formed():
    problems = {
        json.loads(p.read_text())["slug"] for p in (EVALS.parent / "app/seed/problems").glob("*.json")
    }
    seen = set()
    for name in ("review_set.json", "holdout_set.json", "medium_set.json"):
        for s in json.loads((EVALS / name).read_text())["samples"]:
            assert s["id"] not in seen, s["id"]
            seen.add(s["id"])
            assert s["problem"] in problems
            assert s["verdict"] in {"PASSED", "FAILED"}
            assert set(s["categories"]) <= {"correctness", "edge-case", "complexity", "readability", "style"}
            assert s["time"].startswith("O(") and s["note"] and "class Solution" in s["code"]
    assert len(seen) >= 60
