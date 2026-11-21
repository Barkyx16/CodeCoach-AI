"""scripts/suite_table.py records a run's counts and exit delay however quiet pytest was asked to be
(Volume 16, prompt 1): given -q on top of its own, it used to hide pytest's summary line and record
neither. Synthetic test files only."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

SMALL = """
import pytest


def test_passes():
    assert True


@pytest.mark.skip(reason="synthetic")
def test_skips():
    pass


@pytest.fixture
def broken():
    raise RuntimeError("synthetic set-up failure")


def test_cannot_be_set_up(broken):
    pass
"""


def run(tmp_path, *extra):
    (tmp_path / "test_small.py").write_text(SMALL)
    out = tmp_path / "run.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/suite_table.py",
            "--out",
            str(out),
            *extra,
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(tmp_path),
            "-c",
            "/dev/null",
            str(tmp_path / "test_small.py"),
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return proc, json.loads(out.read_text())


def test_an_extra_quiet_flag_is_dropped_and_the_counts_and_exit_delay_are_recorded(tmp_path):
    proc, record = run(tmp_path, "-q")
    assert "ignoring -q" in proc.stdout
    assert record["counts"] == {"passed": 1, "skipped": 1, "error": 1}
    assert record["counts_from"] == "summary" and record["exit_delay_seconds"] is not None


def test_the_plugin_counts_set_up_failures_as_errors(tmp_path):
    proc, record = run(tmp_path)
    [f] = record["files"]
    assert f["outcomes"] == {"passed": 1, "skipped": 1, "error": 1}
