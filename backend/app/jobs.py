"""Background jobs that don't belong in a request: email retries and housekeeping.

`JobsRunner` runs in a thread in every API process (BACKGROUND_JOBS_IN_API, on by default) and
in `python -m app.worker`. Every replica can run it: emails are claimed atomically
(services/outbox.py) and every housekeeping step is an idempotent delete. Nothing here needs the
code judge, so it runs whether or not EXECUTION_ENABLED is set.

Each loop (every `interval` seconds):
- retries due emails;
- every 10 minutes, deletes rate-limit counters no limiter reads any more;
- once a day, deletes inactive guest accounts (GUEST_RETENTION_DAYS) and email jobs that
  finished over a week ago.

`python -m app.cli housekeeping` runs all of it once, now.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config import Settings
from app.db import rls
from app.services import create_intents, lifecycle, outbox, update_receipts
from app.services.email import EmailSender
from app.services.rate_limit import purge_expired
from app.services.retention import prune_inactive_guests, purge_expired_tokens

logger = logging.getLogger("codecoach.jobs")

COUNTERS_EVERY_S = 600.0
DAILY_S = 24 * 3600.0


def housekeeping(
    session_factory: Callable[[], Session], settings: Settings, *, daily: bool = True
) -> dict[str, int]:
    """One pass. Each step runs in its own transaction, and one failing doesn't stop the others."""
    done: dict[str, int] = {}

    def step(name: str, fn: Callable[[Session], int]) -> None:
        try:
            with session_factory() as db:
                done[name] = fn(db)
                db.commit()
        except Exception:  # noqa: BLE001 - housekeeping must never take anything else down
            logger.exception("housekeeping step failed", extra={"step": name})

    step("rate_limit_counters_purged", lambda db: purge_expired(db))
    if daily:
        step("guests_deleted", lambda db: _prune_guests(db, settings.guest_retention_days))
        step("email_jobs_purged", lambda db: outbox.purge_finished(db))
        step("expired_tokens_purged", lambda db: purge_expired_tokens(db))
        step("update_receipts_purged", lambda db: update_receipts.purge(db))
        step("lifecycle_receipts_purged", lambda db: lifecycle.purge(db))
        step("create_intents_purged", lambda db: create_intents.purge(db))
    return done


def _prune_guests(db: Session, days: int) -> int:
    # Reads each guest's latest activity time across learners (progress events), so it needs the
    # maintenance read. The deletes are of users (not covered by RLS); their rows go by cascade.
    with rls.maintenance(db, "guest clean-up: each guest's latest activity"):
        return prune_inactive_guests(db, days)


class JobsRunner:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings: Settings,
        sender: EmailSender,
        interval: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        # Worker scope: no learner's rows (emails and counters don't need any); the one step that
        # reads across learners asks for it by name (`rls.maintenance`).
        self.session_factory = rls.scoped(session_factory, rls.WORKER)
        self.settings = settings
        self.sender = sender
        self.interval = interval
        self._clock = clock
        self._stop = threading.Event()
        self._last_counters = float("-inf")
        self._last_daily = float("-inf")
        self.thread: threading.Thread | None = None

    def run_once(self) -> dict[str, int]:
        done: dict[str, int] = {}
        try:
            for outcome, n in outbox.drain(self.session_factory, self.settings, self.sender).items():
                done[f"emails_{outcome}"] = n
        except Exception:  # noqa: BLE001
            logger.exception("email retries failed")
        now = self._clock()
        if now - self._last_counters >= COUNTERS_EVERY_S:
            daily = now - self._last_daily >= DAILY_S
            done |= housekeeping(self.session_factory, self.settings, daily=daily)
            self._last_counters = now
            if daily:
                self._last_daily = now
        return done

    def run_forever(self) -> None:
        while not self._stop.is_set():
            done = self.run_once()
            if any(done.values()):
                logger.info("background jobs ran", extra={"jobs": done})
            self._stop.wait(self.interval)

    def start(self) -> JobsRunner:
        self.thread = threading.Thread(target=self.run_forever, name="background-jobs", daemon=True)
        self.thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
