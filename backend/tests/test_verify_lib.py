"""Verification brief 03: a failing command, or a failing stage of a pipeline, fails its step and
the overall status, and its output is kept. (Before, ad-hoc `cmd | tail` chains reported tail's
success.)"""

from __future__ import annotations

import subprocess
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "scripts" / "verify_lib.sh"


def _run(tmp_path, body: str) -> subprocess.CompletedProcess:
    script = f'OUT="{tmp_path}"; . "{LIB}"\n{body}'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)


def test_a_failing_pipeline_stage_fails_the_step_and_keeps_its_output(tmp_path):
    r = _run(
        tmp_path,
        'run_sh migrate "echo applying; exit 3 | cat"; echo "rc=$?"\n'
        'run_sh hidden "(echo partial; false) | tail -n 1"; echo "rc=$?"\n'
        'run_sh fine "echo ok | cat"; echo "rc=$?"\n'
        'echo "failed=$FAILED"',
    )
    lines = r.stdout.split()
    assert lines == ["rc=3", "rc=1", "rc=0", "failed=2"], r.stdout
    summary = (tmp_path / "summary.txt").read_text()
    assert "migrate            rc=3" in summary and "hidden             rc=1" in summary
    assert "fine               rc=0" in summary
    assert "partial" in (tmp_path / "hidden.log").read_text()  # the output is kept when it fails
    assert "$ (echo partial; false) | tail -n 1" in (tmp_path / "hidden.log").read_text()


def test_the_revision_script_refuses_an_output_directory_inside_the_repository(tmp_path):
    root = LIB.parent.parent
    r = subprocess.run(
        ["bash", str(root / "scripts" / "verify_revision.sh"), "HEAD", str(root / "backend" / "tmp-out")],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
    )
    assert r.returncode == 2 and "outside the repository" in r.stderr
    assert not (root / "backend" / "tmp-out").exists()  # refused before anything is created


def test_a_rehearsal_that_cannot_run_says_so_and_fails(tmp_path):
    """Nothing listens on port 1: the rehearsal aborts on its first step, prints what it has,
    labelled aborted, and exits 1. A name outside codecoach_rehearsal_* is refused first."""
    import json
    import sys

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    url = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/codecoach_rehearsal_unreachable"
    r = subprocess.run(
        [sys.executable, str(scripts / "rehearse_answer_migration.py"), url],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert out["passed"] is False and out["aborted"].startswith("OperationalError")
    assert "nothing" not in r.stdout  # the password isn't printed
    refused = subprocess.run(
        [sys.executable, str(scripts / "rehearse_restore.py"), url.replace("_unreachable", ""), "x"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode != 0 and "refused" in (refused.stdout + refused.stderr)
