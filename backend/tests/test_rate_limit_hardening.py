"""Rate limiting beyond the basics: every 429 says when to retry (header and body), endpoints that
had no limit now have one, wrong passwords are limited per account as well as per address, the
in-memory limiter and the counter table can't grow without bound, and AI requests can't be
multiplied by concurrency. Synthetic accounts only."""

import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.models import RateLimitCounter
from app.services.ai.base import ProviderError, ProviderResult
from app.services.ai.bounded import BoundedProvider
from app.services.rate_limit import DatabaseRateLimiter, SlidingWindowLimiter, client_key, purge_expired
from tests.conftest import TEST_DATABASE_URL, auth_headers, register

REFRESH_HEADERS = {"X-Requested-With": "codecoach"}


def assert_retry_after(r):
    assert r.status_code == 429, r.text
    seconds = r.json()["error"]["details"]["retry_after_seconds"]
    assert isinstance(seconds, int) and seconds >= 1
    assert r.headers["Retry-After"] == str(seconds)


def test_every_429_carries_a_retry_after_header(make_client):
    c = make_client(auth_rate_limit_per_minute=1)
    assert c.post("/api/v1/auth/guest").status_code in (200, 201)
    assert_retry_after(c.post("/api/v1/auth/guest"))


def test_resending_verification_is_limited_per_address(make_client, monkeypatch):
    from datetime import timedelta

    from app.services import email_verification

    monkeypatch.setattr(email_verification, "RESEND_COOLDOWN", timedelta(0))  # test the per-address limit
    c = make_client(auth_rate_limit_per_minute=2)
    h = auth_headers(register(c, email="resend@example.com"))  # 1 of 2
    assert c.post("/api/v1/auth/verify-email/resend", headers=h).status_code == 202  # 2 of 2
    assert_retry_after(c.post("/api/v1/auth/verify-email/resend", headers=h))


def test_refresh_has_its_own_bucket_and_a_429_keeps_the_cookie(make_client):
    c = make_client(refresh_rate_limit_per_minute=2)
    register(c, email="tabs@example.com")
    for _ in range(2):
        assert c.post("/api/v1/auth/refresh", headers=REFRESH_HEADERS).status_code == 200
    limited = c.post("/api/v1/auth/refresh", headers=REFRESH_HEADERS)
    assert_retry_after(limited)
    assert "set-cookie" not in limited.headers  # the session cookie is left alone
    assert c.cookies.get("cc_refresh")


def login(c, email, password):
    return c.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_wrong_passwords_pause_sign_in_to_that_account_only(make_client):
    c = make_client(login_failures_per_account=3)
    register(c, email="target@example.com")
    register(c, email="bystander@example.com")
    for _ in range(3):
        assert login(c, "target@example.com", "WrongHorse99").status_code == 401
    paused = login(c, "Target@Example.com", "CorrectHorse42")  # even the right password, any case
    assert_retry_after(paused)
    assert paused.json()["error"]["code"] == "account_throttled"
    assert login(c, "bystander@example.com", "CorrectHorse42").status_code == 200
    # An address with no account is limited the same way: a 429 reveals nothing.
    for _ in range(3):
        assert login(c, "nobody@example.com", "WrongHorse99").status_code == 401
    assert login(c, "nobody@example.com", "WrongHorse99").json()["error"]["code"] == "account_throttled"
    # Successful sign-ins aren't counted.
    for _ in range(5):
        assert login(c, "bystander@example.com", "CorrectHorse42").status_code == 200


def test_exports_and_restores_are_limited_per_user(make_client):
    c = make_client(exports_per_hour=2, restores_per_hour=1)
    h = auth_headers(register(c, email="data@example.com"))
    for _ in range(2):
        assert c.get("/api/v1/me/export", headers=h).status_code == 200
    assert_retry_after(c.get("/api/v1/me/export", headers=h, params={"version": 2}))
    backup = c.get("/api/v1/me/export", headers=auth_headers(register(c, email="other@example.com"))).content
    assert c.post("/api/v1/me/restore/preview", headers=h, content=backup).status_code == 200
    assert_retry_after(c.post("/api/v1/me/restore/preview", headers=h, content=backup))


def test_saving_submissions_is_limited_even_when_code_isnt_run(make_client):
    c = make_client(submission_rate_limit_per_minute=2)  # execution is off by default
    h = auth_headers(register(c, email="saver@example.com"))
    body = {"problem_slug": "two-sum", "source_code": "class Solution {}"}
    for _ in range(2):
        assert c.post("/api/v1/submissions", headers=h, json=body).status_code in (200, 201, 202)
    limited = c.post("/api/v1/submissions", headers=h, json=body)
    assert_retry_after(limited)
    assert limited.json()["error"]["details"]["limit_per_minute"] == 2


def test_the_ai_budget_says_when_a_request_frees_up(make_client):
    c = make_client(ai_daily_request_limit=1)
    h = auth_headers(register(c, email="budget@example.com"))
    body = {"problem_slug": "two-sum", "level": 1, "source_code": ""}
    assert c.post("/api/v1/ai/hint", headers=h, json=body).status_code == 200
    r = c.post("/api/v1/ai/hint", headers=h, json={**body, "level": 2})
    assert_retry_after(r)
    assert 23 * 3600 < r.json()["error"]["details"]["retry_after_seconds"] <= 24 * 3600 + 1


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="the per-user AI lock is a PostgreSQL advisory lock")
def test_one_ai_request_per_user_at_a_time(make_client):
    c = make_client()
    data = register(c, email="parallel@example.com")
    h = auth_headers(data)
    user_id = data["user"]["id"]
    body = {"problem_slug": "two-sum", "level": 1, "source_code": ""}
    holder = create_engine(TEST_DATABASE_URL).connect()
    try:
        tx = holder.begin()  # another request of this user, mid-call
        holder.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"codecoach:ai-turn:{user_id}"},
        )
        busy = c.post("/api/v1/ai/hint", headers=h, json=body)
        assert_retry_after(busy)
        assert busy.json()["error"]["code"] == "ai_request_in_progress"
        other = auth_headers(register(c, email="someone-else@example.com"))
        assert c.post("/api/v1/ai/hint", headers=other, json=body).status_code == 200  # others unaffected
        tx.rollback()  # that request finished
    finally:
        holder.close()
    assert c.post("/api/v1/ai/hint", headers=h, json=body).status_code == 200


class SlowProvider:
    name, model = "anthropic", "synthetic"

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def hint(self, ctx):
        self.calls += 1
        self.entered.set()
        # Holds the only slot until the test lets go, however slow the machine (CI run 311: with
        # a 5 s hold, the slot came free before the request got there).
        self.release.wait(60)
        raise ProviderError("synthetic: not a real provider", reason="timeout")


def test_a_full_provider_answers_at_once_with_the_offline_coach(client, user_headers):
    slow = SlowProvider()
    bounded = BoundedProvider(slow, limit=1)
    worker = threading.Thread(target=lambda: pytest.raises(ProviderError, bounded.hint, None))
    worker.start()
    assert slow.entered.wait(5)
    with pytest.raises(ProviderError) as busy:
        bounded.hint(None)
    assert busy.value.reason == "busy" and busy.value.attempts == 0
    client.app.state.ai_provider = bounded  # the API, while the only slot is taken
    r = client.post(
        "/api/v1/ai/hint",
        headers=user_headers,
        json={"problem_slug": "two-sum", "level": 1, "source_code": ""},
    )
    assert r.status_code == 200 and r.json()["provider"] == "offline (fallback)"
    # It didn't wait for the slow call: it never reached the provider (only the worker's call did).
    # A wall-clock bound measured the runner too (21 s on a loaded one, most of it outside the coach).
    assert slow.calls == 1
    slow.release.set()
    worker.join(5)
    ok = BoundedProvider(
        SimpleNamespace(name="x", model="y", hint=lambda ctx: ProviderResult("fine", "x", "y")), 1
    )
    assert ok.hint(None).content == "fine"  # the slot was given back


def test_memory_limiter_forgets_idle_keys_instead_of_growing():
    now = [0.0]
    limiter = SlidingWindowLimiter(5, 60.0, clock=lambda: now[0])
    limiter.MAX_KEYS = 100
    for i in range(100):
        limiter.hit(f"k{i}")
    now[0] = 61.0  # every one of them is idle now
    for i in range(100, 150):
        limiter.hit(f"k{i}")
    assert len(limiter._hits) <= 51
    # Still too many live keys: the oldest half goes, and limiting still works.
    for i in range(150, 400):
        limiter.hit(f"k{i}")
    assert len(limiter._hits) <= 101
    for _ in range(5):
        assert limiter.hit("hot")[0]
    assert limiter.hit("hot")[0] is False


def test_peek_counts_nothing(make_settings):
    now = [1000.0]
    for limiter in (
        SlidingWindowLimiter(2, 60.0, clock=lambda: now[0]),
        _db_limiter(make_settings, 2, lambda: now[0]),
    ):
        for _ in range(5):
            assert limiter.peek("k") == (True, 0.0)
        limiter.hit("k")
        limiter.hit("k")
        assert limiter.peek("k")[0] is False


def _db_limiter(make_settings, limit, clock):
    from app.db.session import Base

    engine = create_engine(make_settings().database_url)
    Base.metadata.create_all(engine, tables=[RateLimitCounter.__table__])
    return DatabaseRateLimiter(sessionmaker(engine), limit, 60, clock=clock)


def test_expired_counters_are_purged_and_live_ones_kept(make_settings):
    now = [10_000.0]
    limiter = _db_limiter(make_settings, 5, lambda: now[0])
    hourly = DatabaseRateLimiter(limiter.session_factory, 5, 3600, clock=lambda: now[0])
    limiter.hit("auth:1.2.3.4")
    hourly.hit("practice:u1")
    with limiter.session_factory() as db:
        db.add(RateLimitCounter(key="legacy", window=1, count=3, expires_at=None))  # pre-column row
        db.commit()
    now[0] += 200  # past the minute window's expiry; the hourly window is still live
    with limiter.session_factory() as db:
        assert purge_expired(db, now[0]) == 2
        db.commit()
        assert db.scalars(select(RateLimitCounter.key)).all() == ["practice:u1"]


@pytest.mark.parametrize(
    ("host", "key"),
    [
        ("203.0.113.9", "203.0.113.9"),
        ("2001:db8:1:2:aaaa::1", "2001:db8:1:2::/64"),
        ("2001:db8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
        ("::ffff:198.51.100.7", "198.51.100.7"),
        ("testclient", "testclient"),
    ],
)
def test_client_keys_group_ipv6_by_64(host, key):
    assert client_key(SimpleNamespace(client=SimpleNamespace(host=host))) == key
