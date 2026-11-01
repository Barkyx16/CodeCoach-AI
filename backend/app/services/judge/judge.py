"""Turn a submission into a verdict.

Flow: build the driver from ALL test inputs (public + hidden) → send Solution.java + Main.java
to the isolated runner with a fresh nonce → parse the driver's nonce-tagged lines → compare
with expected outputs HERE (expected outputs never enter the sandbox) → store a result that
reveals details for public tests only.

Verdict precedence: COMPILE_ERROR > TIME_LIMIT > MEMORY_LIMIT > RUNTIME_ERROR > FAILED > PASSED.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from app.models import ExecutionResult, Submission, SubmissionStatus, TestVisibility
from app.services.judge.harness import CaseOutcome, build_driver, judge_cases
from app.services.judge.runner_client import Runner, RunnerResult

MAX_COMPILE_OUTPUT = 4000
_SANDBOX_PATHS = re.compile(r"/tmp/src/")

STATUS_DETAIL = {
    SubmissionStatus.PASSED: "All tests passed.",
    SubmissionStatus.FAILED: "Some tests failed.",
    SubmissionStatus.COMPILE_ERROR: "Your code didn't compile.",
    SubmissionStatus.RUNTIME_ERROR: "Your code crashed or exited before finishing all tests.",
    SubmissionStatus.TIME_LIMIT: "Time limit exceeded.",
    SubmissionStatus.MEMORY_LIMIT: "Memory limit exceeded.",
    SubmissionStatus.INTERNAL_ERROR: "The judge had a problem running your code. This wasn't your fault.",
}


class JudgeInfrastructureError(Exception):
    """The sandbox itself failed (not the learner's code). Retry later."""


@dataclass(frozen=True)
class Verdict:
    status: SubmissionStatus
    result: ExecutionResult


_DIAGNOSTIC = re.compile(
    r"^(?P<file>[\w$]+\.java)(?::\d+)?(?: \(judge driver\))?: (?P<kind>error|warning): (?P<msg>.*)$"
)
_FOOTER = re.compile(r"^\d+ (?:errors?|warnings?)$")
# Driver diagnostics may only keep messages and symbol lines that can't carry test data:
# identifiers, type names and fixed wording. Anything else is replaced by a generic message.
_SAFE_DRIVER_MESSAGES = [
    re.compile(r"^cannot find symbol$"),
    re.compile(r"^incompatible types: [\w$.<>\[\], ?]+$"),
    re.compile(r"^method [\w$]+ in class [\w$]+ cannot be applied to given types;$"),
    re.compile(r"^[\w$.()<>\[\], ]+ is not public in [\w$.]+; cannot be accessed from outside package$"),
    re.compile(r"^[\w$.()<>\[\], ]+ has private access in [\w$.]+$"),
    re.compile(r"^unreported exception [\w$.]+; must be caught or declared to be thrown$"),
    re.compile(r"^[\w$]+ is abstract; cannot be instantiated$"),
]
_SAFE_DRIVER_DETAIL = re.compile(r"^\s+(?:symbol|location|required|found|reason):\s+[\w$.<>\[\](), ]+$")
DRIVER_HIDDEN = "error in the judge's test driver (details hidden: they would include test data)"


def redact_driver_diagnostics(text: str) -> str:
    """Remove anything javac printed about Main.java (the judge driver) that could reveal tests.

    javac echoes the offending source line under each diagnostic. In the driver those lines are
    test calls containing *hidden* inputs, which appear when a learner renames the method or
    changes its parameters. Driver diagnostics keep only a vetted message and symbol lines, and
    identical ones are collapsed. Idempotent, so it is also applied when reading stored output.
    """
    out: list[str] = []
    seen: set[tuple[str, ...]] = set()
    block: list[str] | None = None  # current driver diagnostic being collected
    in_driver = False

    def flush() -> None:
        nonlocal block
        if block is not None and tuple(block) not in seen:
            seen.add(tuple(block))
            out.extend(block)
        block = None

    for line in text.splitlines():
        m = _DIAGNOSTIC.match(line)
        if m:
            flush()
            in_driver = m["file"] != "Solution.java"
            if in_driver:
                msg = m["msg"].strip()
                safe = any(p.match(msg) for p in _SAFE_DRIVER_MESSAGES) or msg == DRIVER_HIDDEN
                block = [f"Main.java (judge driver): {m['kind']}: {msg if safe else DRIVER_HIDDEN}"]
            else:
                out.append(line)
            continue
        if _FOOTER.match(line.strip()):
            flush()
            in_driver = False
            out.append(line)
        elif in_driver:
            if block is not None and _SAFE_DRIVER_DETAIL.match(line):
                block.append(line)
        else:
            out.append(line)
    flush()
    return "\n".join(out)


def clean_compile_output(text: str) -> str:
    text = redact_driver_diagnostics(_SANDBOX_PATHS.sub("", text))
    return text[:MAX_COMPILE_OUTPUT] + ("\n… (truncated)" if len(text) > MAX_COMPILE_OUTPUT else "")


def judge_submission(submission: Submission, runner: Runner, time_limit_s: float) -> Verdict:
    problem = submission.problem
    tests = list(problem.test_cases)
    nonce = secrets.token_hex(16)
    driver = build_driver(problem.signature, [t.input for t in tests])
    raw = runner.run({"Solution.java": submission.source_code, "Main.java": driver}, nonce, time_limit_s)
    if raw.status == "sandbox_error":
        raise JudgeInfrastructureError(f"sandbox error (exit {raw.exit_code})")
    return _verdict(tests, raw, nonce)


def _verdict(tests: list, raw: RunnerResult, nonce: str) -> Verdict:
    total = len(tests)
    if raw.status == "compile_error":
        return Verdict(
            SubmissionStatus.COMPILE_ERROR,
            ExecutionResult(
                passed_count=0,
                total_count=total,
                public_results=[],
                stderr_excerpt=clean_compile_output(raw.compile_output or raw.stderr),
                runtime_ms=raw.duration_ms,
            ),
        )

    outcomes = judge_cases([t.expected_output for t in tests], raw.stdout, nonce)
    passed = sum(o.passed for o in outcomes)
    runtime_ms = round(sum(o.ms or 0 for o in outcomes)) if any(o.ms for o in outcomes) else None

    if raw.status == "timeout":
        status = SubmissionStatus.TIME_LIMIT
    elif raw.status == "memory_limit" or any(o.exception in ("OutOfMemoryError",) for o in outcomes):
        status = SubmissionStatus.MEMORY_LIMIT
    elif (
        raw.status == "output_limit"
        or any(o.missing for o in outcomes)
        or any(o.exception == "StackOverflowError" for o in outcomes)
    ):
        status = SubmissionStatus.RUNTIME_ERROR
    elif passed == total:
        status = SubmissionStatus.PASSED
    else:
        status = SubmissionStatus.FAILED

    return Verdict(
        status,
        ExecutionResult(
            runtime_ms=runtime_ms,
            memory_kb=None,  # the sandbox doesn't report peak memory yet; never invent a number
            passed_count=passed,
            total_count=total,
            public_results=_public_results(tests, outcomes),
            # Raw run-phase output is NEVER returned: learner code could print hidden inputs.
            stderr_excerpt=None,
        ),
    )


def _public_results(tests: list, outcomes: list[CaseOutcome]) -> list[dict]:
    rows = []
    public_index = 0
    for t, o in zip(tests, outcomes, strict=True):
        if t.visibility != TestVisibility.PUBLIC:
            continue
        rows.append(
            {
                "index": public_index,
                "passed": o.passed,
                "input": t.input,
                "expected_output": t.expected_output,
                "actual_output": o.actual,
                "exception": o.exception,
                "exception_message": o.message,
                "missing": o.missing,
                "line": o.line,
                "runtime_ms": round(o.ms, 3) if o.ms is not None else None,
            }
        )
        public_index += 1
    return rows
