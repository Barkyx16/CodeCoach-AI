"""Shared fixtures.

By default tests use a throwaway SQLite file per test (fast, zero setup). Set
TEST_DATABASE_URL to a PostgreSQL URL to run the exact same suite against Postgres
(CI does both).
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text

from app.config import Settings
from app.db.session import Base
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
# A role that may create databases (CI: the service's superuser). With it, each PostgreSQL test's
# database is recreated from one made once per session (see _seeded_postgres_template).
TEST_DATABASE_ADMIN_URL = os.environ.get("TEST_DATABASE_ADMIN_URL")
# The suite drops every table in that database before each test. Refuse one that isn't plainly a
# test database, so a development, staging or production URL pasted here by mistake stays intact.
if TEST_DATABASE_URL and "test" not in (make_url(TEST_DATABASE_URL).database or ""):
    raise pytest.UsageError(
        "TEST_DATABASE_URL must name a database with 'test' in its name: the suite empties it"
    )


def _ensure_test_database() -> None:
    """With an admin URL each test's database is recreated (dropped, then copied from the
    session's template); a run stopped between the two leaves none. Make it again, empty."""
    if not (TEST_DATABASE_URL and TEST_DATABASE_ADMIN_URL):
        return
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(TEST_DATABASE_ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            exists = c.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            ).first()
            if not exists:
                c.execute(
                    text(f"CREATE DATABASE {_quoted(url.database or '')} OWNER {_quoted(url.username or '')}")
                )
    finally:
        admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _test_database_has_no_migration_state() -> None:
    """The suite makes its tables with create_all, and the readiness tests read the schema state
    from there ("unmanaged"). An alembic_version table left in the shared test database (a
    migration run pointed at it, or a readiness test killed before its cleanup) would read as
    "readiness is broken". Stop with the actual reason instead; the suite doesn't drop tables it
    didn't make. Migration checks use databases of their own (scripts/check_migrations.py)."""
    if not TEST_DATABASE_URL:
        return
    from sqlalchemy import inspect

    _ensure_test_database()
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as c:
            leftover = inspect(c).has_table("alembic_version")
    finally:
        engine.dispose()
    if leftover:
        pytest.exit(
            f"{make_url(TEST_DATABASE_URL).database} has an alembic_version table: migration state left by "
            "a migration run pointed at the test database, or an interrupted readiness test. Drop it "
            "(DROP TABLE alembic_version) or use another test database; run migration checks with "
            "scripts/check_migrations.py, which makes its own.",
            returncode=4,
        )


@pytest.fixture(autouse=True)
def _fresh_content_state() -> Iterator[None]:
    """Corrections and retirements are cached per process; never let one test's leak into the next."""
    from app.content import state as content_state

    content_state.invalidate()
    yield
    content_state.invalidate()


def _release_fastapi_caches() -> None:
    """FastAPI keeps module-level caches keyed by endpoint function (fastapi.dependencies.models:
    whether a dependency is a generator, a coroutine...). `create_app` defines its `/metrics`
    endpoint inside itself, so each cached entry holds that app, and with it the app's engine,
    caches and every object it made: thousands of test apps stayed alive (docs/CI.md, "Suite time
    and memory"). Production builds one app per process, so this is the suite's, not the app's.
    Clearing them after a test only drops classifications FastAPI recomputes on the next call."""
    from fastapi.dependencies import models

    for value in vars(models).values():
        clear = getattr(value, "cache_clear", None)
        if callable(clear):
            clear()


@pytest.fixture(autouse=True)
def _release_finished_apps() -> Iterator[None]:
    yield
    _release_fastapi_caches()


@pytest.fixture
def disposable_engine() -> Iterator[Callable[..., Engine]]:
    """An engine a test makes for itself (a database file of its own, or one to hand to a
    command), disposed when the test ends: an engine that's never disposed keeps its pooled
    connections open for the rest of the run (docs/CI.md, "Suite time and memory")."""
    made: list[Engine] = []

    def _make(url: str, **kwargs) -> Engine:
        engine = create_engine(url, **kwargs)
        made.append(engine)
        return engine

    yield _make
    for engine in made:
        engine.dispose()


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@pytest.fixture(scope="session")
def _seeded_postgres_template() -> Iterator[str | None]:
    """PostgreSQL: one database made by the app's own startup (its tables, the row-level security
    policies, the seeded problem bank), as the app's role, once per session; each test's database is
    then the test database recreated from it (CREATE DATABASE ... TEMPLATE), so every test starts
    from exactly that state, whatever the test before it wrote, changed or left connected
    (docs/CI.md, "The PostgreSQL suite's set-up"). Without an admin URL, each test drops the
    tables and the app makes them again, as before."""
    if not (TEST_DATABASE_URL and TEST_DATABASE_ADMIN_URL):
        yield None
        return
    url = make_url(TEST_DATABASE_URL)
    # Named for this session's process: a pytest run inside a test (tests/test_suite_measure.py
    # runs one with this conftest) makes and drops its own, never this one.
    prefix = f"{url.database}_template_"
    template = f"{prefix}{os.getpid()}"
    admin = create_engine(TEST_DATABASE_ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            # One left by a session that was killed before it could drop its own.
            for (name,) in c.execute(
                text("SELECT datname FROM pg_database WHERE starts_with(datname, :p)"), {"p": prefix}
            ):
                pid = name.removeprefix(prefix)
                if pid.isdigit() and not _alive(int(pid)):
                    c.execute(text(f"DROP DATABASE IF EXISTS {_quoted(name)} WITH (FORCE)"))
            c.execute(text(f"DROP DATABASE IF EXISTS {_quoted(template)} WITH (FORCE)"))
            c.execute(text(f"CREATE DATABASE {_quoted(template)} OWNER {_quoted(url.username or '')}"))
        settings = Settings(
            environment="test",
            database_url=url.set(database=template).render_as_string(hide_password=False),
            secret_key="test-secret-key-that-is-long-enough-0123456789",
            ai_provider="offline",
            background_jobs_in_api=False,
            _env_file=None,
        )
        with TestClient(create_app(settings)):
            pass
        with admin.connect() as c:
            # Nothing may connect to it again: a template can only be copied while unused.
            c.execute(text(f"ALTER DATABASE {_quoted(template)} WITH ALLOW_CONNECTIONS false"))
        yield template
    finally:
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {_quoted(template)} WITH (FORCE)"))
        admin.dispose()


def _restore_postgres(template: str) -> None:
    """The test database, recreated from the session's template: the same tables, policies, grants
    and seeded rows, and nothing any earlier test left (connections still open to it are closed)."""
    url = make_url(TEST_DATABASE_URL or "")
    admin = create_engine(TEST_DATABASE_ADMIN_URL or "", isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {_quoted(url.database or '')} WITH (FORCE)"))
            c.execute(
                text(
                    f"CREATE DATABASE {_quoted(url.database or '')} TEMPLATE {_quoted(template)} "
                    f"OWNER {_quoted(url.username or '')}"
                )
            )
    finally:
        admin.dispose()


@pytest.fixture
def database_url(tmp_path, _seeded_postgres_template) -> Iterator[str]:
    if TEST_DATABASE_URL:
        if _seeded_postgres_template:
            _restore_postgres(_seeded_postgres_template)
        else:
            engine = create_engine(TEST_DATABASE_URL)
            Base.metadata.drop_all(engine)
            engine.dispose()
        yield TEST_DATABASE_URL
    else:
        yield f"sqlite:///{tmp_path / 'test.db'}"


# A production configuration that passes every startup guard (synthetic values only). Tests of
# one guard start from this and change one thing.
PRODUCTION_BASE: dict = {
    "environment": "production",
    "secret_key": "Zq7vR2mK9pX4tL8wN3cJ6hB1yF5dG0sA-uE_iO2kM7nQ",
    "database_url": "postgresql+psycopg://app:Tq83-unique-db-password@db.internal:5432/codecoach",
    "cors_origins": ["https://app.example"],
    "email_backend": "smtp",
    "smtp_host": "smtp.example.com",
    "app_base_url": "https://app.example",
    "email_from": "CodeCoach AI <no-reply@app.example>",
    "metrics_token": "metrics-synthetic-scrape-token-0123456789abcdef",
}


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
            # The jobs thread is tested on its own (test_background_jobs.py); here it would only
            # add timing noise. Emails still get their first attempt right after the response.
            background_jobs_in_api=False,
            _env_file=None,
        )
        base.update(overrides)
        return Settings(**base)

    return _make


@pytest.fixture(scope="session")
def _seeded_sqlite_template(tmp_path_factory) -> str | None:
    """One SQLite database made by the app's own startup (tables, row-level security where it
    applies, the seeded problem bank), once per session. A test's own database starts as a copy of
    it, and the app then runs its whole startup on that copy as before: every test still has a
    database of its own, it's only made 0.5 s faster (docs/CI.md, "Suite time and memory").
    PostgreSQL runs keep making theirs from scratch."""
    if TEST_DATABASE_URL:
        return None
    path = tmp_path_factory.mktemp("seeded-template") / "seeded.db"
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{path}",
        secret_key="test-secret-key-that-is-long-enough-0123456789",
        ai_provider="offline",
        background_jobs_in_api=False,
        _env_file=None,
    )
    with TestClient(create_app(settings)):
        pass
    return str(path)


@pytest.fixture
def make_client(
    make_settings, database_url, _seeded_sqlite_template, _seeded_postgres_template
) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(**overrides) -> TestClient:
        settings = make_settings(**overrides)
        # PostgreSQL, the test database just recreated from the session's template, the app making
        # its tables: the template is what that startup made (on the same models, seed and
        # policies), so running it again would change nothing and cost about a second per test.
        # A test that sets auto_migrate, or uses another database, is left as it asked.
        if (
            _seeded_postgres_template
            and "auto_migrate" not in overrides
            and settings.auto_migrate
            and settings.database_url == database_url
        ):
            settings = make_settings(**overrides, auto_migrate=False)
        # The test's own SQLite file, not made yet, with the app making its tables: start from the
        # seeded copy. Any other database (made by the test, overridden, PostgreSQL) is left alone.
        own = database_url.removeprefix("sqlite:///")
        if (
            _seeded_sqlite_template
            and settings.auto_migrate
            and settings.database_url == database_url
            and not os.path.exists(own)
        ):
            shutil.copyfile(_seeded_sqlite_template, own)
        app = create_app(settings)
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
    career_track: str | None = None,
) -> dict:
    body = {"email": email, "password": password, "display_name": display_name}
    if career_track:
        body["career_track"] = career_track
    r = client.post("/api/v1/auth/register", json=body)
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
        c.app.state.execution_health.probe = lambda: True  # the fake runner is "up"
        runner = FakeRunner(script)
        worker = JudgeWorker(c.app.state.session_factory, runner, c.app.state.settings)
        headers = auth_headers(register(c))
        return c, runner, worker, headers

    return _make
