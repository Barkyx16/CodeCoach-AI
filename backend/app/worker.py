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
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.config import Settings, get_settings
from app.db.session import make_engine, make_session_factory
from app.models import ProgressEvent, ProgressEventType, Submission, SubmissionMode, SubmissionStatus
from app.observability import configure_logging
from app.services.judge.judge import STATUS_DETAIL, JudgeInfrastructureError, judge_submission
from app.services.judge.runner_client import HttpRunner, Runner, RunnerUnavailable
from app.services.retention import prune_inactive_guests

logger = logging.getLogger("codecoach.worker")


def _now() -> datetime:
    return datetime.now(UTC)


class JudgeWorker:
    def __init__(self, session_factory: sessionmaker[Session], runner: Runner, settings: Settings):
        self.session_factory = session_factory
        self.runner = runner
        self.settings = settings
        self._stop = False

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
            self._retry_or_fail(sub, "worker stopped while judging")
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
            sub_id = sub.id
        with self.session_factory() as db:
            sub = db.scalar(
                select(Submission).options(selectinload(Submission.problem)).where(Submission.id == sub_id)
            )
            assert sub is not None
            tests = sub.problem.test_cases
            try:
                verdict = judge_submission(sub, self.runner, self.settings.judge_time_limit_s)
            except (RunnerUnavailable, JudgeInfrastructureError) as exc:
                self._retry_or_fail(sub, str(exc))
                db.commit()
                return True
            sub.status = verdict.status
            sub.status_detail = STATUS_DETAIL[verdict.status]
            sub.judged_at = _now()
            sub.test_version = max((t.version for t in tests), default=None)
            sub.result = verdict.result
            if verdict.status == SubmissionStatus.PASSED and sub.mode == SubmissionMode.SUBMIT:
                db.add(
                    ProgressEvent(
                        user_id=sub.user_id, problem_id=sub.problem_id, event_type=ProgressEventType.SOLVED
                    )
                )
            db.commit()
            logger.info("judged submission %s -> %s", sub_id, verdict.status.value)
            return True

    def run_forever(self) -> None:
        last_recovery = 0.0
        last_retention = 0.0
        while not self._stop:
            if time.monotonic() - last_recovery > 30:
                with self.session_factory() as db:
                    self.recover_stale(db)
                last_recovery = time.monotonic()
            if time.monotonic() - last_retention > 24 * 3600:  # housekeeping, once a day
                try:
                    with self.session_factory() as db:
                        prune_inactive_guests(db, self.settings.guest_retention_days)
                except Exception:  # noqa: BLE001 - never let housekeeping stop judging
                    logger.exception("guest retention failed")
                last_retention = time.monotonic()
            try:
                worked = self.process_one()
            except Exception:  # noqa: BLE001 - keep the worker alive; the job is recovered later
                logger.exception("unexpected worker error")
                worked = False
            if not worked:
                time.sleep(self.settings.worker_poll_interval_s)


def main() -> None:  # pragma: no cover - process entry point
    settings = get_settings()
    configure_logging()
    if not settings.execution_enabled or not settings.runner_token:
        raise SystemExit("EXECUTION_ENABLED=true and RUNNER_TOKEN are required to run the judge worker")
    worker = JudgeWorker(
        make_session_factory(make_engine(settings.database_url)),
        HttpRunner(settings.runner_url, settings.runner_token),
        settings,
    )
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    logger.info("judge worker started")
    worker.run_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
