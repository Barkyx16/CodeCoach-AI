"""A frozen candidate (Durable Saves brief 15): the record names what will be measured, and the
check fails as soon as anything it froze moves."""

from __future__ import annotations

import pytest

from evals import freeze


@pytest.fixture
def rec(monkeypatch):
    monkeypatch.setattr(freeze, "_dirty", lambda: [])
    return freeze.record("test")


def test_a_freeze_records_versions_hashes_metrics_and_the_release_rule(rec):
    assert rec["rubric_version"] and rec["coach_prompt_version"] and rec["protocol_version"] >= 7
    assert set(rec["scoring_files"]) == set(freeze.SCORING)
    assert "career-rn-sealed" in rec["datasets"]  # hashes only: the file isn't read for content
    for m in (
        "contradiction_detection_precision",
        "meaning_changed_false_award",
        "keyword_false_award",
        "benign_false_exclusion",
        "quote_validity",
    ):
        assert rec["declared_metrics"][m]  # each with what its denominator counts
    assert rec["release_rule"]["non_inferiority"]
    assert freeze.check(rec) == []


def test_the_check_fails_when_scoring_prompts_or_data_move(rec):
    moved = {
        **rec,
        "rubric_version": "v0",
        "scoring_files": {**rec["scoring_files"], "backend/app/careers/grading.py": "0" * 64},
        "datasets": {**rec["datasets"], "career-rn-dev": "0" * 64},
        "coach_request_fingerprint": "0" * 64,
    }
    problems = freeze.check(moved)
    assert any("rubric" in p for p in problems)
    assert any("grading.py changed" in p for p in problems)
    assert any("career-rn-dev changed" in p for p in problems)
    assert any("fingerprint" in p for p in problems)


def test_a_freeze_refuses_uncommitted_changes(monkeypatch):
    monkeypatch.setattr(freeze, "_dirty", lambda: [" M backend/app/careers/grading.py"])
    with pytest.raises(SystemExit, match="uncommitted"):
        freeze.record("test")
