"""What a learner may see of a judged submission. One place, so every consumer (the
submissions API, the AI failure explainer) applies the same hidden-test rules."""

from __future__ import annotations

from app.models import Submission, TestVisibility
from app.schemas.submission import ExecutionResultOut, PublicCaseResult
from app.services.judge.judge import redact_driver_diagnostics


def public_result_view(sub: Submission) -> ExecutionResultOut | None:
    if sub.result is None:
        return None
    # public_results are only ever written for PUBLIC tests; re-check defensively so a
    # runner bug can never leak hidden test data.
    public_inputs = {
        i: t for i, t in enumerate(t for t in sub.problem.test_cases if t.visibility == TestVisibility.PUBLIC)
    }
    rows = [PublicCaseResult(**r) for r in sub.result.public_results if r.get("index") in public_inputs]
    public_passed = sum(r.passed for r in rows)
    stderr = sub.result.stderr_excerpt
    return ExecutionResultOut(
        runtime_ms=sub.result.runtime_ms,
        memory_kb=sub.result.memory_kb,
        passed_count=sub.result.passed_count,
        total_count=sub.result.total_count,
        hidden_passed=max(0, sub.result.passed_count - public_passed),
        hidden_total=max(0, sub.result.total_count - len(public_inputs)),
        public_results=rows,
        # Re-redacted on read so output stored before driver redaction existed is safe too.
        stderr_excerpt=redact_driver_diagnostics(stderr) if stderr else None,
    )
