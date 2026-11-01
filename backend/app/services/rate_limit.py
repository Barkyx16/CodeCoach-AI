"""A small in-memory sliding-window rate limiter.

Good enough for a single API process (login/register brute-force protection). With several
API replicas this should move to Redis so the limit is shared; the interface stays the same.
AI usage limits are NOT done here: they are enforced from the database (ai_interactions) so
they survive restarts and are exact per user.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


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
