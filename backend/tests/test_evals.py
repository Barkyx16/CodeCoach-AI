"""Regression guard for the offline coach, using the evaluation suite (evals/run.py).

Thresholds are set just under the measured tuning-set numbers so a rule change that makes the
reviewer worse fails CI. The held-out set is only checked to run, never tuned against.
"""

import json
from pathlib import Path

from evals.run import run

EVALS = Path(__file__).resolve().parents[1] / "evals"


def test_offline_coach_quality_does_not_regress():
    report = run("offline")
    review, hints = report["review"], report["hints"]
    assert review["schema_validity"] == 1.0
    assert review["issue_detection_micro"]["precision"] >= 0.95
    assert review["issue_detection_micro"]["recall"] >= 0.55
    assert review["false_alarm_rate_on_clean_code"] <= 0.10
    assert review["complexity_accuracy"] >= 0.90
    assert hints["level1_spoiler_rate"] == 0.0 and hints["code_leak_rate_levels_1_2"] == 0.0
    assert hints["level2_relevance"] >= 0.9
    assert report["review_holdout"]["samples"] >= 10  # reported, not tuned
    assert report["review_medium"]["samples"] >= 10  # reported, not tuned


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
