"""Judge worker: `python -m app.worker`

Claims queued submissions from the database and judges them through the isolated runner.
Runs as its own process (and container), separate from the API, so slow or hostile
submissions can never tie up API request handling.

Queue semantics
- Claim: oldest QUEUED submission, locked with FOR UPDATE SKIP LOCKED on PostgreSQL, so any
  number of workers can run without double-judging.
- Retry: only infrastructure failures (runner down, sandbox error) are retried, at most
  JUDGE_MAX_ATTEMPTS times; the learner's own errors are final verdicts.
- Recovery: a RUNNING job whose worker died (judge_started_at older than JUDGE_STALE_AFTER_S)
  is put back in the queue, or failed with INTERNAL_ERROR once its attempts are used up.
"""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app import tracing
from app.config import Settings, get_settings
from app.db import rls
from app.db.session import make_engine, make_session_factory
from app.metrics import Metrics
from app.models import ProgressEvent, ProgressEventType, Submission, SubmissionMode, SubmissionStatus
from app.observability import configure_logging
from app.services.judge.judge import STATUS_DETAIL, JudgeInfrastructureError, judge_submission
from app.services.judge.runner_client import HttpRunner, Runner, RunnerUnavailable

logger = logging.getLogger("codecoach.worker")


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def judge_queue_state(session_factory: sessionmaker[Session]) -> tuple[int, float]:
    """(queued submissions, age in seconds of the oldest one): for metrics, read at scrape time."""
    with session_factory() as db:
        count, oldest = db.execute(
            select(func.count(), func.min(Submission.created_at)).where(
                Submission.status == SubmissionStatus.QUEUED
            )
        ).one()
    age = (_now() - _as_utc(oldest)).total_seconds() if oldest is not None else 0.0
    return int(count), max(0.0, age)


class JudgeWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        runner: Runner,
        settings: Settings,
        traces: tracing.TraceStore | None = None,
        metrics: Metrics | None = None,
    ):
        # Worker scope: submissions aren't covered by row-level security, learners' rows are hidden
        # unless a step binds the one learner it's working for (recording a solved problem).
        self.session_factory = rls.scoped(session_factory, rls.WORKER)
        self.runner = runner
        self.settings = settings
        # Each job continues the trace of the request that queued it (Submission.trace_id). An
        # embedded worker shares the API's trace store and metrics; a separate worker process
        # writes its spans to its own log.
        self.traces = traces
        self.metrics = metrics
        self._stop = False

    def _trace(self, trace_id: str | None):
        return tracing.start_trace(trace_id=trace_id, store=self.traces, metrics=self.metrics)

    def stop(self, *_: object) -> None:
        self._stop = True

    # --- queue operations ---------------------------------------------------------------

    def claim(self, db: Session) -> Submission | None:
        stmt = (
            select(Submission)
            .where(Submission.status == SubmissionStatus.QUEUED)
            .order_by(Submission.created_at, Submission.id)
            .limit(1)
        )
        if db.get_bind().dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        sub = db.scalar(stmt)
        if sub is None:
            return None
        sub.status = SubmissionStatus.RUNNING
        sub.status_detail = "Running your code against the tests…"
        sub.attempts += 1
        sub.judge_started_at = _now()
        db.commit()
        return sub

    def recover_stale(self, db: Session) -> int:
        cutoff = _now() - timedelta(seconds=self.settings.judge_stale_after_s)
        stale = db.scalars(
            select(Submission).where(
                Submission.status == SubmissionStatus.RUNNING, Submission.judge_started_at < cutoff
            )
        ).all()
        for sub in stale:
            # The job ran past its time without a result: a timeout, recorded on its own trace.
            with self._trace(sub.trace_id), tracing.span("judge.recover", attempt=sub.attempts) as step:
                step.outcome = "timeout"
                self._retry_or_fail(sub, "worker stopped while judging")
                step.set(result="requeued" if sub.status == SubmissionStatus.QUEUED else "failed")
        db.commit()
        return len(stale)

    def _retry_or_fail(self, sub: Submission, reason: str) -> None:
        if sub.attempts < self.settings.judge_max_attempts:
            sub.status = SubmissionStatus.QUEUED
            sub.status_detail = "Retrying: the judge had a temporary problem."
        else:
            sub.status = SubmissionStatus.INTERNAL_ERROR
            sub.status_detail = STATUS_DETAIL[SubmissionStatus.INTERNAL_ERROR]
            sub.judged_at = _now()
        logger.warning("judge infrastructure failure", extra={"status": sub.status.value})
        logger.info("submission %s: %s (attempt %d)", sub.id, reason, sub.attempts)

    # --- main loop ----------------------------------------------------------------------

    def process_one(self) -> bool:
        """Judge at most one submission. Returns True if a job was processed."""
        with self.session_factory() as db:
            sub = self.claim(db)
            if sub is None:
                return False
            sub_id, trace_id, attempt, language = sub.id, sub.trace_id, sub.attempts, sub.language
            waited = (sub.judge_started_at or _now()) - _as_utc(sub.created_at)
        with (
            self.session_factory() as db,
            self._trace(trace_id),
            tracing.span(
                "judge.run",
                language=language,
                attempt=attempt,
                queue_wait_ms=max(0, round(waited.total_seconds() * 1000)),
            ) as step,
        ):
            return self._judge(db, sub_id, step)

    def _judge(self, db: Session, sub_id: str, step: tracing.Span) -> bool:
        sub = db.scalar(
            select(Submission).options(selectinload(Submission.problem)).where(Submission.id == sub_id)
        )
        if sub is not None:
            tests = sub.problem.test_cases
            try:
                verdict = judge_submission(sub, self.runner, self.settings.judge_time_limit_s)
            except (RunnerUnavailable, JudgeInfrastructureError) as exc:
                self._retry_or_fail(sub, str(exc))
                db.commit()
                step.outcome = "judge_unavailable"
                step.set(result="requeued" if sub.status == SubmissionStatus.QUEUED else "failed")
                return True
            step.set(verdict=verdict.status.value)
            sub.status = verdict.status
            sub.status_detail = STATUS_DETAIL[verdict.status]
            sub.judged_at = _now()
            sub.test_version = max((t.version for t in tests), default=None)
            sub.result = verdict.result
            if verdict.status == SubmissionStatus.PASSED and sub.mode == SubmissionMode.SUBMIT:
                rls.bind_user(db, sub.user_id)  # the one learner whose work this is
                db.add(
                    ProgressEvent(
                        user_id=sub.user_id, problem_id=sub.problem_id, event_type=ProgressEventType.SOLVED
                    )
                )
            db.commit()
            logger.info("judged submission %s -> %s", sub_id, verdict.status.value)
        return True

    def run_forever(self) -> None:
        # Housekeeping (guest retention among it) lives in app/jobs.py now, so it runs whether or
        # not the judge does; main() starts it next to this loop.
        last_recovery = 0.0
        while not self._stop:
            if time.monotonic() - last_recovery > 30:
                with self.session_factory() as db:
                    self.recover_stale(db)
                last_recovery = time.monotonic()
            try:
                worked = self.process_one()
            except Exception:  # noqa: BLE001 - keep the worker alive; the job is recovered later
                logger.exception("unexpected worker error")
                worked = False
            if not worked:
                time.sleep(self.settings.worker_poll_interval_s)


def main() -> None:  # pragma: no cover - process entry point
    """Background jobs (email retries, housekeeping) always; the judge too when code execution is
    configured. Without it, this is a jobs-only worker."""
    from app.jobs import JobsRunner
    from app.services.email import build_email_sender

    settings = get_settings()
    configure_logging()
    session_factory = make_session_factory(
        make_engine(
            settings.database_url, pool_timeout=settings.db_pool_timeout_seconds, pool_size=2, max_overflow=2
        )
    )
    jobs = JobsRunner(session_factory, settings, build_email_sender(settings))
    if not settings.execution_enabled or not settings.runner_token:
        logger.info("background jobs worker started (no judge: EXECUTION_ENABLED is off)")
        signal.signal(signal.SIGTERM, lambda *_: jobs.stop())
        signal.signal(signal.SIGINT, lambda *_: jobs.stop())
        jobs.run_forever()
        return
    worker = JudgeWorker(
        session_factory,
        HttpRunner(settings.runner_url, settings.runner_token_value, ca_bundle=settings.runner_ca_bundle),
        settings,
    )

    def stop(*_: object) -> None:
        jobs.stop()
        worker.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    jobs.start()
    logger.info("judge worker started")
    worker.run_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
