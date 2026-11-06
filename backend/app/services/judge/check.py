"""`python -m app.cli judge-check`: prove the configured judge works, end to end.

Changing settings doesn't prove a remote judge works. This command uses the real configuration
(URL, token, CA bundle) to: 1) call the runner's authenticated status endpoint, 2) judge a known
correct solution and check every public test passes, and 3) judge a known wrong one and check it
fails. It prints no secrets.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from app.config import Settings
from app.services.judge.harness import build_driver, judge_cases
from app.services.judge.runner_client import HttpRunner, Runner, RunnerAuthError, RunnerUnavailable

SEED = Path(__file__).resolve().parents[2] / "seed"
WRONG = "class Solution { public int[] twoSum(int[] nums, int target) { return new int[]{-1, -1}; } }"


def _judge(runner: Runner, source: str, signature: dict, tests: list[dict]) -> tuple[int, int, str]:
    nonce = secrets.token_hex(16)
    driver = build_driver(signature, [t["input"] for t in tests])
    raw = runner.run({"Solution.java": source, "Main.java": driver}, nonce, 10.0)
    if raw.status not in ("ok", "timeout", "memory_limit", "output_limit"):
        return 0, len(tests), raw.status
    outcomes = judge_cases([t["expected_output"] for t in tests], raw.stdout, nonce)
    return sum(o.passed for o in outcomes), len(tests), raw.status


def judge_check(settings: Settings, runner: HttpRunner | None = None, out=print) -> int:
    if not settings.execution_enabled or not settings.runner_token:
        out("Code execution is not configured (EXECUTION_ENABLED is false). Nothing to check.")
        return 2
    runner = runner or HttpRunner(
        settings.runner_url, settings.runner_token_value, ca_bundle=settings.runner_ca_bundle
    )
    try:
        ready = runner.status()
    except RunnerAuthError:
        out("FAIL: the runner rejected RUNNER_TOKEN (it must match the runner's own token).")
        return 1
    except RunnerUnavailable as exc:
        out(
            f"FAIL: the runner can't be reached ({exc}). Check the URL, the SSH tunnel or TLS proxy, and TLS trust."
        )
        return 1
    out("ok: runner reachable over the configured URL and the token was accepted")
    if not ready:
        out("FAIL: the runner can't start sandboxes (Docker or gVisor unavailable on its host).")
        return 1
    problem = json.loads((SEED / "problems" / "003-two-sum.json").read_text())
    tests = [t for t in problem["tests"] if t["visibility"] == "public"]
    reference = (SEED / "reference" / "two-sum.java").read_text()
    try:
        passed, total, status = _judge(runner, reference, problem["signature"], tests)
        if passed != total:
            out(
                f"FAIL: a known-correct solution passed {passed}/{total} public tests (runner status: {status})."
            )
            return 1
        out(f"ok: a known-correct solution passed {passed}/{total} public tests in the sandbox")
        passed, total, status = _judge(runner, WRONG, problem["signature"], tests)
        if passed == total:
            out("FAIL: a known-wrong solution passed every test; the judge isn't checking output.")
            return 1
        out(f"ok: a known-wrong solution was rejected ({passed}/{total} passed)")
    except RunnerUnavailable as exc:
        out(f"FAIL: the runner failed while judging ({exc}).")
        return 1
    out("Judge check passed.")
    return 0
