"""Is code execution actually available right now? A truthful answer for the UI.

States:
- not_configured: this deployment has no judge (EXECUTION_ENABLED is false).
- unavailable:    a judge is configured but an authenticated probe failed, the runner can't start
                  sandboxes, or queued submissions aren't being picked up.
- ready:          the runner answered the authenticated probe and the queue is moving.

The probe result is cached briefly so the capabilities endpoint stays cheap. Nothing here
reveals hostnames, tokens or internal errors; `setup_help` is only filled outside production.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Submission, SubmissionStatus
from app.services.judge.runner_client import HttpRunner, RunnerAuthError, RunnerUnavailable

State = Literal["ready", "unavailable", "not_configured"]
Reason = Literal[
    "ok", "not_configured", "judge_unreachable", "judge_not_ready", "judge_misconfigured", "queue_delayed"
]

MESSAGES: dict[Reason, str] = {
    "ok": "Run and Submit execute your code in an isolated Linux judge.",
    "not_configured": "This server isn't connected to a code judge, so code can't run here. Submitting saves "
    "your attempt without a verdict; you can still ask for a code review.",
    "judge_unreachable": "The code judge can't be reached right now. Submissions wait in the queue and are judged "
    "when it's back; Run is paused.",
    "judge_not_ready": "The code judge is starting or busy. Submissions wait in the queue; Run is paused.",
    "judge_misconfigured": "The code judge is temporarily unavailable. Submissions wait in the queue; Run is paused.",
    "queue_delayed": "Submissions are taking longer than usual to start. Yours will still be judged.",
}
SETUP_HELP: dict[Reason, str] = {
    "not_configured": "Set EXECUTION_ENABLED=true, RUNNER_URL and RUNNER_TOKEN, and start the worker "
    "(python -m app.worker). The runner needs Linux with gVisor; from a Mac, run it on a Linux host and reach it "
    "through an SSH tunnel or HTTPS. See docs/REMOTE_JUDGE.md, then run python -m app.cli judge-check.",
    "judge_unreachable": "The API can't reach RUNNER_URL. Check the runner is running, the SSH tunnel or TLS proxy "
    "is up, and run python -m app.cli judge-check.",
    "judge_not_ready": "The runner answered but can't start sandboxes (Docker or gVisor isn't available on its host).",
    "judge_misconfigured": "The runner rejected RUNNER_TOKEN: it must match the runner's own RUNNER_TOKEN.",
    "queue_delayed": "Queued submissions aren't being picked up. Is the worker (python -m app.worker) running?",
}


class ExecutionHealth:
    def __init__(self, settings: Settings, probe: Callable[[], bool] | None = None, ttl_s: float = 15.0):
        self.settings = settings
        self.ttl_s = ttl_s
        self.probe = probe or self._http_probe
        self._runner: HttpRunner | None = None
        self._cached: tuple[float, Reason] | None = None
        self._lock = threading.Lock()

    def _http_probe(self) -> bool:
        if self._runner is None:
            self._runner = HttpRunner(
                self.settings.runner_url,
                self.settings.runner_token_value,
                ca_bundle=self.settings.runner_ca_bundle,
            )
        return self._runner.status()

    def _runner_reason(self) -> Reason:
        with self._lock:
            now = time.monotonic()
            if self._cached and now - self._cached[0] < self.ttl_s:
                return self._cached[1]
            try:
                reason: Reason = "ok" if self.probe() else "judge_not_ready"
            except RunnerAuthError:
                reason = "judge_misconfigured"
            except RunnerUnavailable:
                reason = "judge_unreachable"
            self._cached = (now, reason)
            return reason

    def forget(self) -> None:
        with self._lock:
            self._cached = None

    def check(self, db: Session) -> tuple[State, Reason, datetime]:
        now = datetime.now(UTC)
        if not self.settings.execution_enabled:
            return "not_configured", "not_configured", now
        reason = self._runner_reason()
        if reason == "ok":
            oldest = db.scalar(
                select(func.min(Submission.created_at)).where(Submission.status == SubmissionStatus.QUEUED)
            )
            if oldest is not None:
                oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=UTC)
                if oldest < now - timedelta(seconds=self.settings.queue_stall_seconds):
                    reason = "queue_delayed"
        state: State = "ready" if reason == "ok" else "unavailable"
        return state, reason, now
