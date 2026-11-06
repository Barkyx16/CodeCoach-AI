"""Shared (database-backed) rate limiting: the algorithm, replicas, and concurrency."""

import threading

import pytest
from sqlalchemy import func, select

from app.models import RateLimitCounter
from app.services.rate_limit import DatabaseRateLimiter, SlidingWindowLimiter
from tests.conftest import TEST_DATABASE_URL


class Clock:
    def __init__(self, t: float = 1_000_040.0):  # 1_000_040 % 60 == 20: 20 s into a window
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def factory(client):
    return client.app.state.session_factory


def test_allows_the_limit_then_rejects_with_a_retry_after(factory):
    clock = Clock()
    limiter = DatabaseRateLimiter(factory, limit=3, window_s=60, clock=clock)
    assert [limiter.hit("auth:1.2.3.4")[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = limiter.hit("auth:1.2.3.4")
    assert not allowed and retry_after == 40.0  # until this window ends
    assert limiter.hit("auth:5.6.7.8")[0] is True  # keys are independent


def test_the_previous_window_still_counts_proportionally(factory):
    """No double-burst at a window boundary (the flaw of a plain fixed window)."""
    clock = Clock(1_000_070.0)  # 50 s into a window
    limiter = DatabaseRateLimiter(factory, limit=4, window_s=60, clock=clock)
    for _ in range(4):
        assert limiter.hit("k")[0]
    clock.t = 1_000_100.0  # 20 s into the next window: 2/3 of the previous one still overlaps
    # estimate = 4 * (1 - 20/60) + current  ->  2.67 + 1, + 2 > 4
    assert limiter.hit("k")[0] is True
    assert limiter.hit("k")[0] is False
    clock.t = 1_000_220.0  # well past both windows
    assert limiter.hit("k")[0] is True


def test_old_windows_are_cleaned_up(factory):
    clock = Clock()
    limiter = DatabaseRateLimiter(factory, limit=10, window_s=60, clock=clock)
    for step in range(5):
        clock.t += 60 * step
        limiter.hit("k")
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(RateLimitCounter)) <= 2


def test_two_api_replicas_share_one_limit(make_client):
    """Two app instances on one database: attempts on either count against the same budget."""
    a = make_client(auth_rate_limit_per_minute=3)
    b = make_client(auth_rate_limit_per_minute=3, auto_migrate=False)
    body = {"email": "nobody@example.com", "password": "Wrong-password-1"}
    codes = [c.post("/api/v1/auth/login", json=body).status_code for c in (a, b, a, b)]
    assert codes == [401, 401, 401, 429]


def test_memory_limiter_is_per_process(make_client):
    a = make_client(auth_rate_limit_per_minute=1, rate_limit_backend="memory")
    b = make_client(auth_rate_limit_per_minute=1, rate_limit_backend="memory", auto_migrate=False)
    assert isinstance(a.app.state.auth_limiter, SlidingWindowLimiter)
    body = {"email": "nobody@example.com", "password": "Wrong-password-1"}
    # Each process allows one attempt: exactly why the database backend is the default.
    assert [c.post("/api/v1/auth/login", json=body).status_code for c in (a, b)] == [401, 401]


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="concurrent writers need PostgreSQL")
def test_concurrent_hits_are_never_lost(factory):
    limiter = DatabaseRateLimiter(factory, limit=1_000, window_s=3600, clock=Clock())
    threads = [threading.Thread(target=lambda: [limiter.hit("race") for _ in range(10)]) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with factory() as db:
        total = db.scalar(select(func.sum(RateLimitCounter.count)).where(RateLimitCounter.key == "race"))
    assert total == 80  # the atomic upsert counted every attempt
