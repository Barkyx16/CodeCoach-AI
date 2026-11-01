"""Execution backends: how a queued submission gets judged.

The API only ever talks to the ExecutionBackend interface. Today the only implementation is
DisabledExecutionBackend: submissions are stored and queued, but untrusted Java is NOT run.
That is a deliberate security decision (blueprint section 07, docs/security/threat-model.md).

A future SandboxedExecutionBackend will push jobs to a queue consumed by isolated runner
workers, which compile the learner's Solution.java together with the driver produced by
app.services.judge.harness.build_driver, then report results back through record_result().
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.models import Submission

EXECUTION_DISABLED_DETAIL = (
    "Saved and queued. Automatic judging is turned off until the sandboxed Java runner "
    "is approved and deployed, so this submission will not run yet."
)


class ExecutionBackend(Protocol):
    name: str
    enabled: bool

    def enqueue(self, db: Session, submission: Submission) -> None:
        """Schedule a submission for judging. Must not block on execution."""


class DisabledExecutionBackend:
    name = "disabled"
    enabled = False

    def enqueue(self, db: Session, submission: Submission) -> None:
        submission.status_detail = EXECUTION_DISABLED_DETAIL
