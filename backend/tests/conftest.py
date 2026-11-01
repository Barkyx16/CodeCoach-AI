"""Shared fixtures.

By default tests use a throwaway SQLite file per test (fast, zero setup). Set
TEST_DATABASE_URL to a PostgreSQL URL to run the exact same suite against Postgres
(CI does both).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import Settings
from app.db.session import Base
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def database_url(tmp_path) -> Iterator[str]:
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(engine)
        engine.dispose()
        yield TEST_DATABASE_URL
    else:
        yield f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def make_settings(database_url) -> Callable[..., Settings]:
    def _make(**overrides) -> Settings:
        base = dict(
            environment="test",
            database_url=database_url,
            secret_key="test-secret-key-that-is-long-enough-0123456789",
            ai_provider="offline",
            ai_daily_request_limit=50,
            auth_rate_limit_per_minute=1000,
            metrics_enabled=True,
            _env_file=None,
        )
        base.update(overrides)
        return Settings(**base)

    return _make


@pytest.fixture
def make_client(make_settings) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(**overrides) -> TestClient:
        app = create_app(make_settings(**overrides))
        client = TestClient(app)
        client.__enter__()  # runs startup: create tables + seed
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def register(
    client: TestClient,
    email: str = "ada@example.com",
    password: str = "CorrectHorse42",
    display_name: str | None = "Ada",
) -> dict:
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "display_name": display_name}
    )
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(token_response: dict) -> dict:
    return {"Authorization": f"Bearer {token_response['access_token']}"}


@pytest.fixture
def user_headers(client) -> dict:
    return auth_headers(register(client))


@pytest.fixture
def judged(make_client):
    """App with execution enabled + a worker bound to a fake runner (see tests/judge_fakes.py)."""
    from app.worker import JudgeWorker
    from tests.judge_fakes import TOKEN, FakeRunner

    def _make(script, **settings):
        c = make_client(execution_enabled=True, runner_token=TOKEN, **settings)
        runner = FakeRunner(script)
        worker = JudgeWorker(c.app.state.session_factory, runner, c.app.state.settings)
        headers = auth_headers(register(c))
        return c, runner, worker, headers

    return _make
