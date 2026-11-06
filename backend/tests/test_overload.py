"""Overload: when every database connection is busy, a request is shed quickly with a clear,
retryable 503 instead of queueing for half a minute and failing as a generic 500."""

import time

from sqlalchemy.exc import TimeoutError as PoolTimeout

from tests.conftest import auth_headers, register


def test_a_request_that_cannot_get_a_database_connection_is_shed_with_503(make_client):
    c = make_client(db_pool_timeout_seconds=0.5)
    h = auth_headers(register(c))
    held = []
    try:
        while True:  # take every connection the pool will hand out (size + overflow)
            held.append(c.app.state.engine.connect())
            assert len(held) < 100, "the pool should be bounded"
    except PoolTimeout:
        pass
    try:
        started = time.monotonic()
        r = c.get("/api/v1/me/progress", headers=h)
        waited = time.monotonic() - started
        assert r.status_code == 503, r.text
        assert r.json()["error"]["code"] == "server_busy"
        assert r.headers["retry-after"] == "2"
        assert r.headers["x-request-id"]
        assert waited < 5  # bounded by DB_POOL_TIMEOUT_SECONDS, not SQLAlchemy's default 30 s
    finally:
        for conn in held:
            conn.close()
    assert c.get("/api/v1/me/progress", headers=h).status_code == 200  # recovers on its own


def test_the_wait_is_configurable_and_bounded(make_settings):
    import pytest

    assert make_settings().db_pool_timeout_seconds == 10.0
    with pytest.raises(ValueError):
        make_settings(db_pool_timeout_seconds=0)
    with pytest.raises(ValueError):
        make_settings(db_pool_timeout_seconds=600)
