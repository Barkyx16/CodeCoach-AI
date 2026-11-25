"""CI change classification and the fail-closed summary (Volume 8, prompt 10; docs/CI.md)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ci_classify = load("ci_classify")
ci_summary = load("ci_summary")
ALL = set(ci_classify.LANES)


def needed(paths, removed=False) -> set[str]:
    lanes = ci_classify.classify(paths, removed)
    return {k for k in ci_classify.LANES if lanes[k]}


@pytest.mark.parametrize(
    ("paths", "lanes"),
    [
        (["docs/RECOVERY.md"], set()),
        (["docs/screenshots/durable/x.png", "README.md"], set()),
        (["backend/app/services/notes.py"], {"backend", "e2e", "sandbox", "docker"}),
        (["backend/migrations/versions/20261109_x.py"], {"backend", "e2e", "sandbox", "docker"}),
        (["frontend/src/app/Layout.tsx"], {"frontend", "e2e", "sandbox", "docker"}),
        (["runner/app/main.py"], {"runner", "sandbox", "docker"}),
        (["docs/openapi.json"], {"backend", "frontend", "e2e"}),
        (["scripts/rehearse_production_storage.sh"], {"docker"}),
        (["docs/RECOVERY.md", "frontend/src/x.ts"], {"frontend", "e2e", "sandbox", "docker"}),
        # Shared configuration, lockfiles, dependency lists, workflows, the CI scripts, unknowns: all.
        ([".github/workflows/ci.yml"], ALL),
        (["frontend/package-lock.json"], ALL),
        (["backend/requirements.txt"], ALL),
        (["deploy/docker-compose.production.yml"], ALL),
        (["scripts/ci_classify.py"], ALL),
        (["Makefile"], ALL),
        (["somewhere/new/file.py"], ALL),
        ([], ALL),  # nothing to compare: everything
    ],
)
def test_changes_are_classified_conservatively(paths, lanes):
    assert needed(paths) == lanes


def test_docs_only_is_labelled_and_a_deletion_means_everything():
    assert ci_classify.classify(["docs/CI.md"])["docs_only"] is True
    assert ci_classify.classify(["backend/app/x.py"])["docs_only"] is False
    assert needed(["docs/old.md"], removed=True) == ALL


def test_an_unreadable_diff_means_everything(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.chdir(tmp_path)  # not a git repository
    assert ci_classify.main(["--base", "abc123", "--head", "def456"]) == 0
    written = dict(line.split("=", 1) for line in out.read_text().splitlines())
    assert all(written[lane] == "true" for lane in ci_classify.LANES) and written["docs_only"] == "false"


def test_the_real_diff_of_this_repository_is_read(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.chdir(ROOT)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert ci_classify.main(["--base", f"{head}~1", "--head", head]) == 0
    assert "lanes=" in out.read_text()


def lanes(**on) -> str:
    base = dict.fromkeys(ci_classify.LANES, False)
    base.update(on)
    base["docs_only"] = not any(on.values())
    base["full"] = all(base[k] for k in ci_classify.LANES)
    return json.dumps(base)


def needs(lanes_json: str, **results) -> dict:
    jobs = {job: {"result": results.get(job.replace("-", "_"), "skipped")} for job in ci_summary.JOBS}
    return {"changes": {"result": "success", "outputs": {"lanes": lanes_json}}, **jobs}


def test_a_full_run_passes_only_when_every_job_succeeded():
    all_ok = {job.replace("-", "_"): "success" for job in ci_summary.JOBS}
    full = lanes(**dict.fromkeys(ci_classify.LANES, True))
    assert ci_summary.evaluate(needs(full, **all_ok))[0] is True
    for job in ci_summary.JOBS:
        for bad in ("failure", "cancelled", "skipped"):
            results = {**all_ok, job.replace("-", "_"): bad}
            passed, rows, _ = ci_summary.evaluate(needs(full, **results))
            assert passed is False, (job, bad)
            assert dict((r[0], r[3]) for r in rows)[job] == "FAIL"


def test_a_required_job_cant_be_skipped_into_success():
    only_frontend = lanes(frontend=True, e2e=True, sandbox=True, docker=True)
    ok = dict(security="success", frontend="success", e2e="success", sandbox="success", docker="success")
    assert ci_summary.evaluate(needs(only_frontend, **ok))[0] is True
    assert ci_summary.evaluate(needs(only_frontend, **{**ok, "e2e": "skipped"}))[0] is False


def test_a_job_that_ran_and_failed_fails_the_summary_even_if_not_required():
    docs = lanes()
    assert ci_summary.evaluate(needs(docs, security="success", backend="failure"))[0] is False


def test_documentation_only_passes_and_says_it_isnt_code_evidence():
    passed, rows, headline = ci_summary.evaluate(needs(lanes(), security="success"))
    assert passed is True and "not code evidence" in headline
    assert dict((r[0], r[3]) for r in rows)["backend"] == "not required for this change"
    # Even documentation needs the security job.
    assert ci_summary.evaluate(needs(lanes(), security="skipped"))[0] is False


def test_no_classification_or_a_missing_job_fails_closed():
    assert ci_summary.evaluate({"changes": {"result": "failure"}})[0] is False
    # Even with lanes written and every job green, a classification that didn't finish is no evidence.
    full = lanes(**dict.fromkeys(ci_classify.LANES, True))
    green = needs(full, **{job.replace("-", "_"): "success" for job in ci_summary.JOBS})
    assert (
        ci_summary.evaluate({**green, "changes": {"result": "failure", "outputs": {"lanes": full}}})[0]
        is False
    )
    assert ci_summary.evaluate({"changes": {"result": "cancelled"}})[0] is False
    assert ci_summary.evaluate({"changes": {"result": "success", "outputs": {}}})[0] is False
    full = lanes(**dict.fromkeys(ci_classify.LANES, True))
    present = needs(full, **{job.replace("-", "_"): "success" for job in ci_summary.JOBS})
    del present["sandbox"]
    assert ci_summary.evaluate(present)[0] is False


def test_the_workflow_lists_every_job_the_summary_expects():
    """The summary must wait for every job; a job added to the workflow but not to the summary
    (or the other way round) would be evidence nobody checks."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    jobs_block = workflow.split("\njobs:\n", 1)[1]
    defined = {
        line.strip()[:-1]
        for line in jobs_block.splitlines()
        if line.startswith("  ") and not line.startswith("   ") and line.strip().endswith(":")
    }
    assert defined == set(ci_summary.JOBS) | {"changes", "summary"}, defined
    summary_needs = workflow.split("  summary:", 1)[1].split("needs:", 1)[1].split("\n", 1)[0]
    assert {n.strip() for n in summary_needs.strip(" []").split(",")} == set(ci_summary.JOBS) | {"changes"}
