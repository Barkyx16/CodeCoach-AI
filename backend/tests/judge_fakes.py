"""Fake runner and helpers shared by judge-related tests (no sandbox needed)."""

import json

from sqlalchemy import select

from app.services.judge.harness import result_prefix
from app.services.judge.runner_client import RunnerResult

TOKEN = "r" * 40

# Expected outputs for the problem under test, filled in by each test once its app exists, and
# read by the fake runner's script to produce "correct" driver output.
EXPECTED: list = []


class FakeRunner:
    """Answers like the real runner. `script(files, nonce)` returns (status, stdout, extra)."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def run(self, files, nonce, time_limit_s):
        self.calls.append({"files": files, "nonce": nonce, "time_limit_s": time_limit_s})
        out = self.script(files, nonce)
        if isinstance(out, Exception):
            raise out
        status, stdout, extra = out
        return RunnerResult(
            status=status,
            exit_code=extra.get("exit_code", 0),
            stdout=stdout,
            stderr=extra.get("stderr", ""),
            compile_output=extra.get("compile_output"),
            run_started=status != "compile_error",
            output_truncated=status == "output_limit",
            duration_ms=900,
        )


def lines(nonce, outputs):
    """Driver output where test i returned outputs[i] (or raised, if a dict with 'exception')."""
    rows = []
    for i, out in enumerate(outputs):
        if out is None:
            continue
        if isinstance(out, dict) and "exception" in out:
            rows.append(result_prefix(nonce) + json.dumps({"index": i, "ok": False, **out, "ms": 0.2}))
        else:
            rows.append(result_prefix(nonce) + json.dumps({"index": i, "ok": True, "output": out, "ms": 0.2}))
    return "\n".join(rows)


def expected_outputs(client, slug):
    from app.models import Problem

    with client.app.state.session_factory() as db:
        p = db.scalar(select(Problem).where(Problem.slug == slug))
        return [t.expected_output for t in p.test_cases], [t.visibility.value for t in p.test_cases]


def submit(c, headers, slug="two-sum", code="class Solution { /* learner code */ }"):
    return c.post("/api/v1/submissions", headers=headers, json={"problem_slug": slug, "source_code": code})
