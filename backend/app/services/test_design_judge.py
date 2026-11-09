"""The judge worker's side of test design (docs/TEST_DESIGN.md).

A queued run is claimed like a submission (oldest first, FOR UPDATE SKIP LOCKED on PostgreSQL),
run once in the sandbox through the same runner and driver, and reported from the outputs that
came back. Infrastructure failures are retried up to JUDGE_MAX_ATTEMPTS; a run whose worker died
is put back or failed by the same staleness rule. A run queued against an exercise version that has
since changed isn't run against the new one: it's failed with a message to run the cases again.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.config import Settings
from app.models import TestDesignRun
from app.services.judge.harness import parse_driver_output
from app.services.judge.runner_client import Runner, RunnerUnavailable
from app.testdesign import BY_SLUG, build_sources
from app.testdesign.report import report, unique_inputs

logger = logging.getLogger("codecoach.worker")

RUNNING_DETAIL = "Running your cases against the reference and the faulty versions…"
RETRY_DETAIL = "Retrying: the judge had a temporary problem."
FAILED_DETAIL = "The judge couldn't run these cases. Nothing was guessed; run them again later."
CHANGED_DETAIL = "This exercise changed before your cases ran, so they weren't run. Run them again."
STOPPED_EARLY = {
    "timeout": "The run hit the time limit before every result arrived.",
    "output_limit": "The run printed more than the judge keeps, so some results are missing.",
    "memory_limit": "The run ran out of memory before every result arrived.",
}


def _now() -> datetime:
    return datetime.now(UTC)


def claim(db: Session) -> TestDesignRun | None:
    stmt = (
        select(TestDesignRun)
        .where(TestDesignRun.status == "queued")
        .order_by(TestDesignRun.created_at, TestDesignRun.id)
        .limit(1)
    )
    if db.get_bind().dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    run = db.scalar(stmt)
    if run is None:
        return None
    run.status, run.status_detail = "running", RUNNING_DETAIL
    run.attempts += 1
    run.judge_started_at = _now()
    db.commit()
    return run


def _retry_or_fail(run: TestDesignRun, settings: Settings, reason: str) -> None:
    if run.attempts < settings.judge_max_attempts:
        run.status, run.status_detail = "queued", RETRY_DETAIL
    else:
        run.status, run.status_detail = "failed", FAILED_DETAIL
        run.judged_at = _now()
    logger.info("test design run %s: %s (attempt %d)", run.id, reason, run.attempts)


def recover_stale(db: Session, settings: Settings) -> int:
    cutoff = _now() - timedelta(seconds=settings.judge_stale_after_s)
    stale = db.scalars(
        select(TestDesignRun).where(
            TestDesignRun.status == "running", TestDesignRun.judge_started_at < cutoff
        )
    ).all()
    for run in stale:
        _retry_or_fail(run, settings, "worker stopped while running")
    db.commit()
    return len(stale)


def execute(db: Session, run_id: str, runner: Runner, settings: Settings) -> str:
    """Run one claimed run. Returns its new status."""
    run = db.get(TestDesignRun, run_id)
    if run is None:
        return "gone"
    ex = BY_SLUG.get(run.exercise_slug)
    if ex is None or ex.version != run.exercise_version:
        run.status, run.status_detail, run.judged_at = "failed", CHANGED_DETAIL, _now()
        db.commit()
        return run.status
    unique, _, _ = unique_inputs(run.cases)
    files, _ = build_sources(ex, unique)
    nonce = secrets.token_hex(16)
    try:
        raw = runner.run(files, nonce, settings.judge_time_limit_s)
        if raw.status == "sandbox_error":
            raise RunnerUnavailable(f"sandbox error (exit {raw.exit_code})")
    except RunnerUnavailable as exc:
        _retry_or_fail(run, settings, str(exc))
        db.commit()
        return run.status
    if raw.status == "compile_error":
        # The exercise's own code is checked with a JDK in CI; this would be our fault, not the cases'.
        logger.error("test design %s: authored code didn't compile in the judge", ex.slug)
        run.status, run.status_detail, run.judged_at = "failed", FAILED_DETAIL, _now()
        db.commit()
        return run.status
    result = report(ex, run.cases, parse_driver_output(raw.stdout, nonce))
    if raw.status in STOPPED_EARLY:
        result["summary"].insert(1, STOPPED_EARLY[raw.status])
    run.report = result
    run.status, run.judged_at = "done", _now()
    run.status_detail = "Ran against the reference and every faulty version."
    try:
        db.commit()
    except (IntegrityError, StaleDataError):
        db.rollback()  # the account was deleted while this ran: nothing is written back
        return "gone"
    return run.status
