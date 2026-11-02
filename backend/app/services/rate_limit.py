"""Rate limiting for brute-force-sensitive endpoints (sign-in, registration, password reset).

DatabaseRateLimiter (default) keeps counters in the database, so the limit is shared by every
API replica and survives restarts. It uses the "sliding window counter" algorithm: two fixed
windows, with the previous one weighted by how much of it still overlaps the last minute. That
is one atomic upsert per attempt and avoids the burst a plain fixed window allows at its edge.

SlidingWindowLimiter keeps exact timestamps in memory: fine for one process (or tests).

AI usage limits are NOT done here: they are enforced from the database (ai_interactions) so they
are exact per user.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from sqlalchemy import delete, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import RateLimitCounter


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_s: float = 60.0, clock=time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, float]:
        """Record an attempt. Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(0.0, self.window_s - (now - q[0]))
            q.append(now)
            if len(self._hits) > 10_000:  # bound memory under key-spraying
                for k in [k for k, v in self._hits.items() if not v][:5_000]:
                    del self._hits[k]
            return True, 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class DatabaseRateLimiter:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        limit: int,
        window_s: int = 60,
        clock: Callable[[], float] = time.time,  # wall clock: replicas must agree on windows
    ):
        self.session_factory = session_factory
        self.limit = limit
        self.window_s = window_s
        self._clock = clock

    def hit(self, key: str) -> tuple[bool, float]:
        """Record an attempt. Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        window = int(now // self.window_s)
        elapsed = now - window * self.window_s
        with self.session_factory() as db:
            current = self._increment(db, key, window)
            previous = (
                db.scalar(
                    select(RateLimitCounter.count).where(
                        RateLimitCounter.key == key, RateLimitCounter.window == window - 1
                    )
                )
                or 0
            )
            # Old windows for this key are never needed again.
            db.execute(
                delete(RateLimitCounter).where(
                    RateLimitCounter.key == key, RateLimitCounter.window < window - 1
                )
            )
            db.commit()
        estimate = previous * (1 - elapsed / self.window_s) + current
        if estimate <= self.limit:
            return True, 0.0
        # Rejected attempts still count, so hammering keeps the door shut.
        return False, round(self.window_s - elapsed, 1)

    @staticmethod
    def _increment(db: Session, key: str, window: int) -> int:
        """Atomic upsert: concurrent requests on any replica can't lose counts."""
        dialect = db.get_bind().dialect.name
        insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
        upsert = (
            insert(RateLimitCounter)
            .values(key=key, window=window, count=1)
            .on_conflict_do_update(
                index_elements=[RateLimitCounter.key, RateLimitCounter.window],
                set_={"count": RateLimitCounter.count + 1},
            )
            .returning(RateLimitCounter.count)
        )
        return int(db.execute(upsert).scalar_one())
