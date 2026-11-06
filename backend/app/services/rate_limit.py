"""Rate limiting for brute-force-sensitive endpoints (sign-in, registration, password reset).

DatabaseRateLimiter (default) keeps counters in the database, so the limit is shared by every
API replica and survives restarts. It uses the "sliding window counter" algorithm: two fixed
windows, with the previous one weighted by how much of it still overlaps the last minute. That
is one atomic upsert per attempt and avoids the burst a plain fixed window allows at its edge.

SlidingWindowLimiter keeps exact timestamps in memory: fine for one process (or tests).

AI usage limits are NOT done here: they are enforced from the database (ai_interactions) so they
are exact per user.

Keys that name a client use `client_key(request)`: the client address, with IPv6 grouped by /64
(one household or server gets a whole /64, so per-address keys would be trivially sidestepped).
Old counter rows are deleted by `purge_expired` (housekeeping), not only when the same key comes back.
"""

from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.errors import RateLimitedError
from app.models import RateLimitCounter


def client_key(request: Request) -> str:
    """The client's address for rate-limit keys; IPv6 addresses are grouped by their /64."""
    host = request.client.host if request.client else "unknown"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def enforce(limiter: SlidingWindowLimiter | DatabaseRateLimiter, key: str, message: str) -> None:
    """Count an attempt against `limiter`; a 429 with Retry-After if it's over."""
    allowed, retry_after = limiter.hit(key)
    if not allowed:
        raise RateLimitedError.wait(message, retry_after)


class SlidingWindowLimiter:
    MAX_KEYS = 10_000  # bound memory under key-spraying

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
            if len(self._hits) > self.MAX_KEYS:
                self._evict(now)
            return True, 0.0

    def peek(self, key: str) -> tuple[bool, float]:
        """Would an attempt be allowed now? Counts nothing."""
        now = self._clock()
        with self._lock:
            live = [t for t in self._hits.get(key, ()) if now - t < self.window_s]
            if len(live) >= self.limit:
                return False, max(0.0, self.window_s - (now - live[0]))
            return True, 0.0

    def _evict(self, now: float) -> None:
        # Keys whose newest attempt is older than the window can't limit anything any more. (A
        # key's deque is only trimmed when that key is hit again, so "empty" alone finds nothing.)
        stale = [k for k, q in self._hits.items() if not q or now - q[-1] >= self.window_s]
        for k in stale:
            del self._hits[k]
        if len(self._hits) > self.MAX_KEYS:  # still too many live keys: drop the oldest half
            by_age = sorted(self._hits, key=lambda k: self._hits[k][-1])
            for k in by_age[: len(by_age) // 2]:
                del self._hits[k]

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
        expires = (window + 2) * self.window_s  # read as "previous window" until then
        with self.session_factory() as db:
            current = self._increment(db, key, window, expires)
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

    def peek(self, key: str) -> tuple[bool, float]:
        """Would an attempt be allowed now? Reads only; counts nothing."""
        now = self._clock()
        window = int(now // self.window_s)
        elapsed = now - window * self.window_s
        with self.session_factory() as db:
            rows = dict(
                db.execute(
                    select(RateLimitCounter.window, RateLimitCounter.count).where(
                        RateLimitCounter.key == key, RateLimitCounter.window.in_([window, window - 1])
                    )
                ).all()
            )
        estimate = rows.get(window - 1, 0) * (1 - elapsed / self.window_s) + rows.get(window, 0)
        # The next attempt would add one.
        if estimate + 1 <= self.limit:
            return True, 0.0
        return False, round(self.window_s - elapsed, 1)

    @staticmethod
    def _increment(db: Session, key: str, window: int, expires: int) -> int:
        """Atomic upsert: concurrent requests on any replica can't lose counts."""
        dialect = db.get_bind().dialect.name
        insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
        upsert = (
            insert(RateLimitCounter)
            .values(key=key, window=window, count=1, expires_at=expires)
            .on_conflict_do_update(
                index_elements=[RateLimitCounter.key, RateLimitCounter.window],
                set_={"count": RateLimitCounter.count + 1},
            )
            .returning(RateLimitCounter.count)
        )
        return int(db.execute(upsert).scalar_one())


def purge_expired(db: Session, now: float | None = None) -> int:
    """Delete counter rows no limiter will read again. Rows from before `expires_at` existed are
    deleted too: at worst one window's count is forgotten once. Returns how many were deleted."""
    cutoff = math.floor(time.time() if now is None else now)
    result = db.execute(
        delete(RateLimitCounter).where(
            or_(RateLimitCounter.expires_at < cutoff, RateLimitCounter.expires_at.is_(None))
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)
