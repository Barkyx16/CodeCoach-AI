"""The evaluation harness itself (evals/): case selection, held-out separation, provenance,
versions, invalid output, provider failures, redaction, weakened coaches, reports and partial runs.

The full offline evaluation and its release gates run in tests/test_evals.py.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

from app.careers.grading import grade
from app.careers.questions import get_question, questions_for
from evals import career, meta, variants
from evals.contracts import check_framing_and_ladder, check_hidden_tests_and_secrets
from evals.faults import run_faults
from evals.gates import compare, evaluate_gates
from evals.run import BudgetExhausted, Metered, main, report_problems, run, to_markdown, write_report

EVALS = Path(__file__).resolve().parents[1] / "evals"
logging.getLogger("codecoach.ai.anthropic").setLevel(logging.ERROR)


def _gate(report: dict, gate_id: str) -> dict:
    return next(g for g in evaluate_gates(report) if g["id"] == gate_id)


@pytest.fixture(scope="module")
def dev_report() -> dict:
    return run(split="dev", sections=("career",))


# --- datasets ---------------------------------------------------------------------------------


def test_career_cases_are_the_ones_the_selection_rule_picks():
    by_cell = defaultdict(list)
    for q in questions_for("registered-nurse"):
        by_cell[(q.difficulty, q.kind)].append(q.id)
    picks = {
        "dev": {sorted(v)[0] for v in by_cell.values()},
        "holdout": {sorted(v)[1] for v in by_cell.values()},
    }
    for name in ("career_dev.json", "career_holdout.json"):
        data = career.load(name)
        assert {c["question_id"] for c in data["cases"]} == picks[data["split"]], name


def test_held_out_cases_share_nothing_with_development_cases():
    dev, held = career.load("career_dev.json"), career.load("career_holdout.json")
    assert {c["id"] for c in dev["cases"]}.isdisjoint(c["id"] for c in held["cases"])
    assert {c["question_id"] for c in dev["cases"]}.isdisjoint(c["question_id"] for c in held["cases"])
    assert {c["answer"] for c in dev["cases"]}.isdisjoint(c["answer"] for c in held["cases"])
    code = defaultdict(set)
    for name in ("review_set.json", "holdout_set.json", "medium_set.json"):
        for s in json.loads((EVALS / name).read_text())["samples"]:
            code[s["code"]].add((name, s["id"], s["problem"]))
    known = {o["sample"] for d in meta.manifest()["datasets"] for o in d.get("known_overlap", [])}
    for where in code.values():
        assert len({(n, p) for n, _, p in where}) == len(where), f"the same case twice: {where}"
        if len({n for n, _, _ in where}) > 1:  # identical code in a tuning and a held-out set
            held = {i for n, i, _ in where if n != "review_set.json"}
            assert held <= known, f"code shared across sets and not recorded in datasets.json: {where}"


def test_every_dataset_has_provenance_a_split_and_its_recorded_hash():
    assert meta.manifest_problems() == []
    for d in meta.manifest()["datasets"]:
        assert d["split"] in {"dev", "holdout"} and d["version"] >= 1
        assert d["provenance"] and d["labels"] and d["used_for"]
    for name in ("career_dev.json", "career_holdout.json"):
        data = career.load(name)
        assert data["provenance"].startswith("Synthetic") and data["labeling"] and data["review_status"]


def test_a_dataset_edited_without_a_new_version_is_reported(tmp_path, monkeypatch):
    for f in EVALS.glob("*.json"):
        (tmp_path / f.name).write_bytes(f.read_bytes())
    edited = json.loads((tmp_path / "career_holdout.json").read_text())
    edited["cases"][0]["labels"]["points"] = {k: False for k in edited["cases"][0]["labels"]["points"]}
    (tmp_path / "career_holdout.json").write_text(json.dumps(edited))
    monkeypatch.setattr(meta, "EVAL_DIR", tmp_path)
    monkeypatch.setattr(meta, "MANIFEST", tmp_path / "datasets.json")
    problems = meta.manifest_problems()
    assert len(problems) == 1 and "career_holdout.json changed since version" in problems[0]


def test_every_case_labels_every_rubric_point_of_its_pinned_question_version():
    for name in ("career_dev.json", "career_holdout.json"):
        data = career.load(name)
        for c in data["cases"]:
            q = get_question(data["track"], c["question_id"], c["question_version"])
            assert q is not None and sorted(r.label for r in q.rubric) == sorted(c["labels"]["points"]), c[
                "id"
            ]
            assert set(c["labels"]["uncertain"]) <= set(c["labels"]["points"])
            if c.get("injection"):
                assert c["injection"] in c["answer"] and c.get("forbidden_evidence")


def test_a_case_whose_rubric_changed_is_an_error_not_a_score():
    data = career.load("career_dev.json")
    case = {**data["cases"][0], "labels": {"points": {"An old point": True}, "uncertain": []}}
    out = career.evaluate_case(case, data["track"], grade)
    assert "relabel" in out["error"] and not out["checks"]


# --- versions ---------------------------------------------------------------------------------


def test_the_prompt_version_names_the_current_prompts():
    assert meta.prompt_version_problems() == []


def test_a_prompt_or_schema_change_without_a_new_version_is_reported(monkeypatch):
    from app.schemas.ai import HintContent
    from app.services.ai import anthropic_provider as ap

    monkeypatch.setattr(ap, "SYSTEM_PROMPT", ap.SYSTEM_PROMPT + " Always answer in French.")
    assert "changed since coach-" in meta.prompt_version_problems()[0]
    monkeypatch.undo()
    schema = HintContent.model_json_schema()
    monkeypatch.setattr(
        HintContent, "model_json_schema", classmethod(lambda cls, **kw: {**schema, "extra": 1})
    )
    assert meta.prompt_version_problems()


def test_a_report_from_another_schema_fails_the_integrity_gate(dev_report):
    old = {**dev_report, "meta": {**dev_report["meta"], "report_schema": 1}}
    assert any("report schema 1" in f for f in _gate(old, "report.integrity")["failures"])


# --- invalid output and provider failures -----------------------------------------------------


def test_invalid_feedback_fails_the_schema_check_and_a_crash_is_a_failed_case():
    data = career.load("career_dev.json")

    def out_of_range(q, a):
        return replace(grade(q, a), score=140)

    def crashes(q, a):
        raise RuntimeError("boom")

    bad = career.evaluate_set({**data, "cases": data["cases"][:3]}, out_of_range)
    assert bad["dimensions"]["schema"]["failed"] == ["rn-dev-01", "rn-dev-02", "rn-dev-03"]
    crashed = career.evaluate_set({**data, "cases": data["cases"][:3]}, crashes)
    assert crashed["cases_scored"] == 0 and len(crashed["case_errors"]) == 3
    report = {"career": {"career-rn-dev": crashed}}
    assert "grader raised RuntimeError" in _gate(report, "career.complete")["failures"][0]


def test_every_provider_failure_falls_back_to_the_offline_coach():
    result = run_faults()
    assert result["failed"] == [] and result["checks"] == 30
    assert {r["scenario"] for r in result["rows"]} >= {
        "timeout",
        "cut_off_json",
        "invalid_response_body",
        "refusal",
    }
    assert result["client_limits"] == {"timeout_s": 60.0, "max_retries": 2}


def test_a_coach_that_lets_errors_escape_fails_the_fallback_gate():
    from app.services.ai.anthropic_provider import AnthropicCoach

    class Leaky(AnthropicCoach):
        def _call(self, prompt, schema, *, max_tokens, system=""):
            return self._client.messages.parse(model=self.model, output_format=schema)  # no error handling

    result = run_faults(lambda client: Leaky(api_key=None, model="m", client=client))
    assert result["failed"] and _gate({"faults": result}, "provider.fallback")["status"] == "failed"


# --- requests to Claude: weakened prompts and paths fail ----------------------------------------


def _coach(cls):
    return lambda client: cls(api_key=None, model="weak", client=client)


def test_the_real_prompts_pass_the_contract():
    a = check_framing_and_ladder()
    assert a["requests"] > 1000 and not (a["framing"] or a["ladder"] or a["bounded"])


def test_a_system_prompt_without_the_untrusted_data_rule_fails():
    assert check_framing_and_ladder(_coach(variants.NoUntrustedRule))["framing"]


def test_a_hint_prompt_that_carries_deeper_hints_fails():
    ladder = check_framing_and_ladder(_coach(variants.LeakyHints))["ladder"]
    assert any("L1: carries the level-2 hint" in f for f in ladder)


def test_hidden_tests_and_secrets_never_reach_the_prompt_and_weakened_paths_are_caught():
    real = check_hidden_tests_and_secrets()
    assert real["problems_checked"] > 250 and real["hidden_tests"] == [] and real["secrets"] == []
    with variants.raw_judge_output() as kwargs:
        assert check_hidden_tests_and_secrets(**kwargs)["hidden_tests"]
    with variants.no_redaction():
        assert check_hidden_tests_and_secrets()["secrets"]


# --- career graders: fake evidence and weakened rules fail ------------------------------------


def test_fabricated_evidence_fails_the_evidence_gate():
    data = career.load("career_dev.json")
    s = career.evaluate_set(data, variants.fabricated_evidence)
    failures = _gate({"career": {"career-rn-dev": s}}, "career.evidence")["failures"]
    assert failures and "quote is not the learner's words" in failures[0]


def test_scoring_too_short_answers_fails_the_insufficient_evidence_gate():
    s = career.evaluate_set(career.load("career_dev.json"), variants.no_short_answer_cap)
    assert s["dimensions"]["insufficient"]["failed"] == ["rn-dev-03", "rn-dev-10", "rn-dev-19", "rn-dev-22"]


def test_a_grader_that_believes_the_answer_fails_the_injection_gate():
    s = career.evaluate_set(career.load("career_dev.json"), variants.obeys_the_answer)
    assert s["dimensions"]["injection"]["failed"] == ["rn-dev-10", "rn-dev-23"]


def test_held_out_gate_failures_name_the_case_but_not_the_answer():
    held = career.load("career_holdout.json")
    s = career.evaluate_set(held, variants.fabricated_evidence)
    failures = _gate({"career": {held["id"]: s}}, "career.evidence")["failures"]
    assert failures and all("held-out: details in the JSON report" in f for f in failures)
    assert not any(c["answer"][:30] in "".join(failures) for c in held["cases"])


# --- reports ----------------------------------------------------------------------------------


def test_a_report_records_what_is_needed_to_reproduce_it(dev_report):
    m = dev_report["meta"]
    for key in (
        "run_id",
        "commit",
        "uncommitted_changes",
        "started_at",
        "rubric_version",
        "prompt_version",
        "prompt_fingerprint",
        "provider",
        "model",
        "config",
        "datasets",
        "python",
    ):
        assert key in m, key
    assert {d["id"] for d in m["datasets"]} >= {"career-rn-dev", "career-rn-holdout", "coding-review-tuning"}
    assert all(len(d["sha256_actual"]) == 64 for d in m["datasets"])
    assert dev_report["finished_at"] and dev_report["usage"]["cost_usd"] is None


def test_partial_runs_say_so_and_fail_the_integrity_gate():
    r = run(split="dev", sections=("career",), limit=2)
    assert r["complete"] is False
    assert any("first 2 cases" in x for x in r["incomplete_reasons"])
    assert r["career"]["career-rn-dev"]["cases_scored"] == 2
    assert _gate(r, "report.integrity")["status"] == "failed"
    assert "PARTIAL RUN, not a benchmark result" in to_markdown(r)


def test_a_saved_report_is_checked_against_this_commit_and_these_datasets(dev_report, tmp_path):
    path = write_report(dev_report, "check", out=tmp_path)
    problems = report_problems(path)
    assert any("partial run" in p for p in problems)  # dev split and one section only
    md = path.with_suffix(".md")
    md.write_text(md.read_text().replace(dev_report["meta"]["run_id"], "0" * 32))
    assert any("from a different run" in p for p in report_problems(path))
    stale = json.loads(path.read_text())
    stale["meta"]["commit"] = "0" * 40
    stale["meta"]["datasets"][0]["sha256_actual"] = "0" * 64
    path.write_text(json.dumps(stale))
    problems = report_problems(path)
    assert any("from commit 000000000000" in p for p in problems)
    assert any("changed since the run" in p for p in problems)


def test_compare_refuses_different_data_and_lists_conditions_and_case_regressions(dev_report):
    weak = run(
        split="dev",
        sections=("career",),
        career_grader=(variants.obeys_the_answer, "weak", "variants.obeys_the_answer"),
    )
    c = compare(dev_report, weak)
    assert (
        c["comparable"]
        and "rubric_version" in c["changed_conditions"]
        and "config" in c["changed_conditions"]
    )
    assert "career-rn-dev / rn-dev-23: injection" in c["regressed"] and c["fixed"] == []
    other = json.loads(json.dumps(weak))
    other["meta"]["datasets"][4]["sha256_actual"] = "f" * 64
    refused = compare(dev_report, other)
    assert refused["comparable"] is False and refused["changed_datasets"] == [
        other["meta"]["datasets"][4]["id"]
    ]


def test_calls_to_claude_need_an_explicit_flag_and_a_budget(monkeypatch):
    monkeypatch.setattr("sys.argv", ["evals.run", "--provider", "anthropic"])
    with pytest.raises(SystemExit, match="cost money"):
        main()

    class Fake:
        name, model = "anthropic", "m"

        def review(self, ctx):
            raise AssertionError("never reached")

    metered = Metered(Fake(), max_calls=0)
    with pytest.raises(BudgetExhausted):
        metered.review(None)


def test_another_rubric_can_be_loaded_from_git_for_a_comparison():
    from app.careers.grading import RUBRIC_VERSION
    from evals.run import load_grader

    grader, version, described = load_grader("git:HEAD")
    assert version == RUBRIC_VERSION and described.startswith(
        "git HEAD:backend/app/careers/grading.py (sha256 "
    )
    data = career.load("career_dev.json")
    assert career.evaluate_case(data["cases"][0], data["track"], grader)["checks"]["evidence"]["passed"]
