"""Durable storage. Saved work survives a killed and restarted API process. Production connects
as an ordinary app role that owns nothing: deploy/postgres-init makes it and grant-app-role gives it
row access. An older schema upgrades in place, and a failed migration changes nothing, which
readiness reports. The optional development-database copy refuses anything it can't do safely.
Synthetic data only.

The PostgreSQL rehearsals need TEST_DATABASE_ADMIN_URL: a role that can create databases and roles
(CI's service superuser, or a local admin role). They create disposable `codecoach_rehearsal_*`
databases and roles and drop them afterwards. Nothing else is touched."""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import MetaData, Table, create_engine, inspect, make_url, text
from sqlalchemy.exc import DBAPIError

from app.config import Settings
from app.db import copy as dbcopy
from app.db import rls
from app.db.roles import apply_grants, check_identifier, grant_statements
from app.db.session import Base
from app.main import create_app
from tests.conftest import PRODUCTION_BASE

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
ADMIN_URL = os.environ.get("TEST_DATABASE_ADMIN_URL")
PREVIOUS = "b165a5a80342"  # the revision before this code's head
PASSWORD = "CorrectHorse42"
# Nothing listens on port 1: every connection is refused at once.
UNREACHABLE = "postgresql+psycopg://127.0.0.1:1/none?connect_timeout=1"

needs_admin = pytest.mark.skipif(
    not ADMIN_URL, reason="needs TEST_DATABASE_ADMIN_URL (creates disposable databases and roles)"
)


# --- the real server, as its own process --------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    """uvicorn in a child process, so a restart is a real one: new interpreter, engine and pool."""

    def __init__(self, database_url: str, tmp_path: Path, **env: str) -> None:
        self.base = f"http://127.0.0.1:{_free_port()}"
        self.env = {
            **os.environ,
            "DATABASE_URL": database_url,
            "ENVIRONMENT": "development",
            "EMAIL_BACKEND": "file",
            "EMAIL_FILE_DIR": str(tmp_path / "mail"),
            "BACKGROUND_JOBS_IN_API": "false",
            **env,
        }
        self.proc: subprocess.Popen | None = None

    def start(self) -> Api:
        port = self.base.rsplit(":", 1)[1]
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", port],
            cwd=BACKEND,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(self.proc.stdout.read().decode()[-3000:])  # type: ignore[union-attr]
            try:
                if httpx.get(self.base + "/health/ready", timeout=1).status_code == 200:
                    return self
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        self.kill()
        raise AssertionError("the API didn't become ready")

    def kill(self) -> None:
        """SIGKILL: no shutdown hooks, no flush. A crash, or a container killed by its host."""
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGKILL)
            self.proc.wait(10)


def save_work(base: str, email: str) -> str:
    with httpx.Client(base_url=base) as c:
        r = c.post(
            "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Ada"}
        )
        assert r.status_code == 201, r.text
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        note = c.post("/api/v1/me/notes", headers=h, json={"title": "Restart survival", "body": "still here"})
        assert note.status_code == 201, note.text
        return note.json()["id"]


def notes_after_signing_in(base: str, email: str) -> list[str]:
    with httpx.Client(base_url=base) as c:
        r = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return [n["id"] for n in c.get("/api/v1/me/notes", headers=h).json()["items"]]


def test_saved_work_survives_a_killed_and_restarted_api(database_url, tmp_path):
    first = Api(database_url, tmp_path).start()
    try:
        note_id = save_work(first.base, "restart@example.com")
    finally:
        first.kill()
    second = Api(database_url, tmp_path).start()
    try:
        assert note_id in notes_after_signing_in(second.base, "restart@example.com")
    finally:
        second.kill()


# --- production refuses what wouldn't persist ---------------------------------------------------


def test_production_refuses_sqlite():
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(**{**PRODUCTION_BASE, "database_url": "sqlite:///./codecoach.db"}, _env_file=None)


def test_routine_startup_never_deletes_data():
    """dev.sh, both compose files and the image start-up: no volume removal, no dropped tables or
    databases, no deleted database files. Rehearsal scripts clean up only their own resources."""
    files = [
        REPO / "dev.sh",
        REPO / "docker-compose.yml",
        REPO / "deploy" / "docker-compose.production.yml",
        REPO / "deploy" / "postgres-init" / "10-roles.sh",
        BACKEND / "Dockerfile",
    ]
    forbidden = [
        "down -v",
        "volume rm",
        "volume prune",
        "drop_all",
        "DROP DATABASE",
        "DROP TABLE",
        "DROP SCHEMA",
    ]
    for path in files:
        for line in path.read_text().splitlines():
            line = line.split(" #")[0]  # comments may warn about them
            if line.lstrip().startswith("#"):
                continue
            for word in forbidden:
                assert word not in line, f"{path.name} runs {word!r}: {line.strip()}"
            if "rm " in line:
                assert not any(x in line for x in (".db", "pgdata", "postgres", "sqlite")), (
                    f"{path.name} may delete a database: {line.strip()}"
                )


# --- roles ----------------------------------------------------------------------------------------


def test_role_names_are_plain_identifiers():
    assert check_identifier("codecoach_app") == "codecoach_app"
    for bad in ["CodeCoach", "app; DROP TABLE users", 'app"', "", "1app", "a" * 64]:
        with pytest.raises(ValueError):
            check_identifier(bad)
    statements = grant_statements("codecoach_app")
    assert any("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE alembic_version" in s for s in statements)
    assert not any(word in " ".join(statements) for word in ("OWNER", "ALL PRIVILEGES", "BYPASSRLS"))


@pytest.fixture
def rehearsal():
    """A disposable database plus owner and app roles, made by the real init script."""
    if shutil.which("psql") is None:
        pytest.skip("needs the psql command (the init script uses it)")
    suffix = secrets.token_hex(4)
    admin_url = make_url(ADMIN_URL)
    r = SimpleNamespace(
        db=f"codecoach_rehearsal_{suffix}",
        owner=f"codecoach_rehearsal_owner_{suffix}",
        app=f"codecoach_rehearsal_app_{suffix}",
        owner_pw=secrets.token_hex(16),
        app_pw=secrets.token_hex(16),
    )
    r.url = lambda user, pw: admin_url.set(
        drivername="postgresql+psycopg", username=user, password=pw, database=r.db
    ).render_as_string(hide_password=False)
    r.admin = admin_url.set(drivername="postgresql+psycopg", database=r.db).render_as_string(
        hide_password=False
    )
    r.owner_url, r.app_url = r.url(r.owner, r.owner_pw), r.url(r.app, r.app_pw)

    def init_roles() -> None:
        env = {
            **os.environ,
            "PGHOST": admin_url.host or "localhost",
            "PGPORT": str(admin_url.port or 5432),
            "PGPASSWORD": admin_url.password or "",
            "POSTGRES_USER": admin_url.username or "",
            "POSTGRES_DB": r.db,
            "CODECOACH_OWNER_ROLE": r.owner,
            "CODECOACH_APP_ROLE": r.app,
            "CODECOACH_OWNER_PASSWORD": r.owner_pw,
            "CODECOACH_APP_PASSWORD": r.app_pw,
        }
        done = subprocess.run(
            ["sh", str(REPO / "deploy" / "postgres-init" / "10-roles.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        assert done.returncode == 0, done.stderr

    r.init_roles = init_roles
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"CREATE DATABASE {r.db}"))
    try:
        yield r
    finally:
        with admin.connect() as c:
            c.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d"), {"d": r.db}
            )
            c.execute(text(f"DROP DATABASE IF EXISTS {r.db}"))
            for role in (r.owner, r.app):
                c.execute(text(f"DROP ROLE IF EXISTS {role}"))
        admin.dispose()


def run(args: list[str], database_url: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": database_url, "ENVIRONMENT": "development"}
    done = subprocess.run([sys.executable, "-m", *args], cwd=BACKEND, env=env, capture_output=True, text=True)
    if check:
        assert done.returncode == 0, done.stdout + done.stderr
    return done


def _denied(engine, statement: str) -> bool:
    try:
        with engine.begin() as c:
            c.execute(text(statement))
    except DBAPIError as exc:
        return "permission denied" in str(exc.orig) or "must be owner" in str(exc.orig)
    return False


@needs_admin
def test_the_api_runs_as_an_app_role_that_owns_nothing_and_its_data_survives_restarts(rehearsal, tmp_path):
    rehearsal.init_roles()
    run(["alembic", "upgrade", "head"], rehearsal.owner_url)
    run(["app.cli", "seed"], rehearsal.owner_url)
    run(["app.cli", "grant-app-role", rehearsal.app], rehearsal.owner_url)

    app_engine = create_engine(rehearsal.app_url)
    try:
        # What the API's role can't do, though it can read and write rows.
        assert _denied(app_engine, "ALTER TABLE notes DISABLE ROW LEVEL SECURITY")
        assert _denied(app_engine, "DROP TABLE notes")
        assert _denied(app_engine, "CREATE TABLE intruder (id int)")
        assert _denied(app_engine, "UPDATE alembic_version SET version_num = 'x'")
        assert _denied(app_engine, f"ALTER ROLE {rehearsal.app} BYPASSRLS")
        with app_engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM problems")).scalar_one() > 0
    finally:
        app_engine.dispose()

    # check-rls --strict: the owner fails it (it owns the tables), the app role passes.
    owner_check = run(["app.cli", "check-rls", "--strict"], rehearsal.owner_url, check=False)
    assert owner_check.returncode == 1 and "owns" in owner_check.stdout
    app_check = run(["app.cli", "check-rls", "--strict"], rehearsal.app_url)
    assert "Row-level security is enforced." in app_check.stdout and "least-privilege" in app_check.stdout

    # Granting is refused to a superuser and when connected as the app role itself.
    with create_engine(rehearsal.owner_url).begin() as c, pytest.raises(ValueError, match="superuser"):
        apply_grants(c, make_url(ADMIN_URL).username)
    refused = run(["app.cli", "grant-app-role", rehearsal.app], rehearsal.app_url, check=False)
    assert refused.returncode == 1 and "owner" in refused.stdout

    # The API as the app role (no AUTO_MIGRATE: it couldn't create tables, and shouldn't).
    first = Api(rehearsal.app_url, tmp_path, AUTO_MIGRATE="false").start()
    try:
        note_id = save_work(first.base, "roles@example.com")
    finally:
        first.kill()
    second = Api(rehearsal.app_url, tmp_path, AUTO_MIGRATE="false").start()
    try:
        assert note_id in notes_after_signing_in(second.base, "roles@example.com")
    finally:
        second.kill()


@needs_admin
def test_startup_warns_in_production_when_the_api_connects_as_the_owner(rehearsal, caplog):
    rehearsal.init_roles()
    run(["alembic", "upgrade", "head"], rehearsal.owner_url)
    run(["app.cli", "grant-app-role", rehearsal.app], rehearsal.owner_url)
    for url, expected in ((rehearsal.owner_url, True), (rehearsal.app_url, False)):
        engine = create_engine(url)
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="codecoach.rls"):
            rls.warn_if_not_enforced(engine, production=True)
        engine.dispose()
        warned = [r for r in caplog.records if r.levelno == logging.WARNING and "owns" in r.getMessage()]
        assert bool(warned) is expected


# --- upgrades, failed migrations, readiness ---------------------------------------------------------


def _filler(column) -> object:
    t = column.type
    if getattr(t, "enums", None):
        return t.enums[0]
    try:
        kind = t.python_type
    except NotImplementedError:
        return "x"
    return {str: "x", bool: False, int: 0, float: 0.0, datetime: datetime.now(UTC), dict: {}, list: []}.get(
        kind, "x"
    )


def insert_minimal(conn, table_name: str, **given) -> None:
    """A row holding only what the schema at this revision requires (it may be older than the
    models, so the ORM can't be used)."""
    table = Table(table_name, MetaData(), autoload_with=conn)
    row = dict(given)
    for column in table.columns:
        if (
            column.name in row
            or column.nullable
            or column.server_default is not None
            or column.autoincrement is True
        ):
            continue
        row[column.name] = _filler(column)
    conn.execute(table.insert().values(**row))


def alembic(url: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(["alembic", *args], url, check=check)


def readiness(make_settings, url: str) -> tuple[int, dict]:
    with TestClient(create_app(make_settings(database_url=url, auto_migrate=False))) as client:
        r = client.get("/health/ready")
        return r.status_code, r.json()


@needs_admin
def test_an_older_schema_upgrades_in_place_and_a_failed_migration_changes_nothing(rehearsal, make_settings):
    url = rehearsal.admin
    alembic(url, "upgrade", PREVIOUS)
    engine = create_engine(url)
    with engine.begin() as c:
        insert_minimal(c, "users", id="u-old", email="old@example.com", is_guest=False)
        insert_minimal(c, "notes", id="n-old", user_id="u-old", title="Written before the upgrade")
    assert readiness(make_settings, url) == (
        503,
        {"status": "unavailable", "checks": {"database": "ok", "schema": "behind"}},
    )

    # A migration that can't apply (someone added one of its columns by hand): PostgreSQL rolls
    # the whole upgrade back, so the schema and every row are as they were.
    with engine.begin() as c:
        c.execute(text("ALTER TABLE users ADD COLUMN pending_email varchar(10)"))
    failed = alembic(url, "upgrade", "head", check=False)
    assert failed.returncode != 0 and "pending_email" in failed.stderr
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
        assert c.execute(text("SELECT email FROM users WHERE id = 'u-old'")).scalar_one() == "old@example.com"
        assert "pending_email_at" not in {col["name"] for col in inspect(c).get_columns("users")}
    assert readiness(make_settings, url)[0] == 503  # still behind: not ready, rather than broken

    with engine.begin() as c:
        c.execute(text("ALTER TABLE users DROP COLUMN pending_email"))
    alembic(url, "upgrade", "head")
    assert readiness(make_settings, url) == (
        200,
        {"status": "ok", "checks": {"database": "ok", "schema": "current"}},
    )
    with engine.connect() as c:
        row = c.execute(text("SELECT email, pending_email FROM users WHERE id = 'u-old'")).one()
        assert tuple(row) == ("old@example.com", None)
        assert (
            c.execute(text("SELECT title FROM notes WHERE id = 'n-old'")).scalar_one()
            == "Written before the upgrade"
        )
    engine.dispose()


def test_readiness_is_503_while_the_database_is_unreachable_and_200_once_it_answers(
    make_settings, database_url
):
    unreachable = UNREACHABLE
    with TestClient(create_app(make_settings(database_url=unreachable, auto_migrate=False))) as client:
        r = client.get("/health/ready")
        assert (r.status_code, r.json()["checks"]) == (503, {"database": "fail"})
        assert client.get("/health").status_code == 200  # alive, just not ready
    with TestClient(create_app(make_settings(database_url=database_url))) as client:
        assert client.get("/health/ready").status_code == 200


# --- the optional development-database copy ------------------------------------------------------


def dev_database(make_settings, path: Path) -> str:
    """A development SQLite database with real work in it, made through the API."""
    url = f"sqlite:///{path}"
    with TestClient(create_app(make_settings(database_url=url))) as c:
        for email in ("ada@example.com", "grace@example.com"):
            r = c.post(
                "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": None}
            )
            h = {"Authorization": f"Bearer {r.json()['access_token']}"}
            assert c.post("/api/v1/me/notes", headers=h, json={"title": f"{email}'s note"}).status_code == 201
    return url


def migrated_sqlite(path: Path) -> str:
    """An empty SQLite target at this code's head (the PostgreSQL case is tested below)."""
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    heads = {h for h in __import__("app.api.routes.health", fromlist=["_revisions"])._revisions()[0]}
    with engine.begin() as c:
        c.execute(text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)"))
        for head in heads:
            c.execute(text("INSERT INTO alembic_version VALUES (:v)"), {"v": head})
    engine.dispose()
    return url


def signed_in_notes(make_settings, url: str, email: str) -> list[str]:
    with TestClient(create_app(make_settings(database_url=url, auto_migrate=False))) as c:
        r = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return [n["title"] for n in c.get("/api/v1/me/notes", headers=h).json()["items"]]


def test_copy_moves_accounts_and_work_and_refuses_what_it_cant_do_safely(make_settings, tmp_path):
    source_url = dev_database(make_settings, tmp_path / "dev.db")
    source = create_engine(source_url)

    unmigrated = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    assert any("alembic upgrade head" in p for p in dbcopy.plan(source, unmigrated).problems)

    target_url = migrated_sqlite(tmp_path / "target.db")
    target = create_engine(target_url)
    checked = dbcopy.plan(source, target)
    assert checked.ok, checked.problems
    assert checked.counts["users"] == 2 and checked.counts["notes"] == 2 and checked.counts["problems"] > 0
    assert checked.skipped["refresh_tokens"] >= 2  # sessions stay behind: people sign in again

    copied = dbcopy.copy(source, target)
    assert copied == {k: v for k, v in checked.counts.items()}
    with target.connect() as c:
        assert c.execute(text("SELECT count(*) FROM refresh_tokens")).scalar_one() == 0
    assert signed_in_notes(make_settings, target_url, "grace@example.com") == ["grace@example.com's note"]

    # Never twice into the same database, and never into one already holding rows.
    assert any("isn't empty" in p for p in dbcopy.plan(source, target).problems)
    with pytest.raises(ValueError, match="isn't empty"):
        dbcopy.copy(source, target)
    assert dbcopy.plan(source, source).problems == ["the source and the target are the same database"]

    # A source this version doesn't fully understand is refused, not guessed at.
    with source.begin() as c:
        c.execute(text("CREATE TABLE mystery (x int)"))
        c.execute(text("ALTER TABLE notes DROP COLUMN reflection"))
    problems = dbcopy.plan(source, create_engine(migrated_sqlite(tmp_path / "fresh.db"))).problems
    assert any("mystery" in p for p in problems) and any("lacks reflection" in p for p in problems)
    source.dispose()
    target.dispose()


def test_rows_that_point_at_each_other_are_copied_parents_first():
    table = Base.metadata.tables["practice_answers"]
    rows = [
        {"id": "c", "revises_answer_id": "b"},
        {"id": "b", "revises_answer_id": "a"},
        {"id": "a", "revises_answer_id": None},
    ]
    assert [r["id"] for r in dbcopy._parents_first(table, rows)] == ["a", "b", "c"]
    with pytest.raises(ValueError, match="cycle"):
        dbcopy._parents_first(
            table, [{"id": "x", "revises_answer_id": "y"}, {"id": "y", "revises_answer_id": "x"}]
        )


def test_the_copy_command_is_a_dry_run_unless_asked(make_settings, tmp_path):
    source_url = dev_database(make_settings, tmp_path / "dev.db")
    target_url = migrated_sqlite(tmp_path / "target.db")
    dry = run(["app.cli", "copy-database", "--from", source_url], target_url)
    assert "Dry run: nothing was written" in dry.stdout and "copy       2  users" in dry.stdout
    with create_engine(target_url).connect() as c:
        assert c.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
    done = run(["app.cli", "copy-database", "--from", source_url, "--apply"], target_url)
    assert "every table's count matched" in done.stdout
    again = run(["app.cli", "copy-database", "--from", source_url, "--apply"], target_url, check=False)
    assert again.returncode == 1 and "isn't empty" in again.stdout


@needs_admin
def test_copy_from_sqlite_into_a_migrated_postgresql_database(rehearsal, make_settings, tmp_path):
    source_url = dev_database(make_settings, tmp_path / "dev.db")
    alembic(rehearsal.admin, "upgrade", "head")
    source, target = create_engine(source_url), create_engine(rehearsal.admin)
    copied = dbcopy.copy(source, target)
    assert copied["users"] == 2
    with target.connect() as c:
        largest = c.execute(text("SELECT max(id) FROM problems")).scalar_one()
        # Sequences continue after the copied ids, so the next new problem can't collide.
        assert (
            c.execute(text("SELECT nextval(pg_get_serial_sequence('problems', 'id'))")).scalar_one() > largest
        )
    assert signed_in_notes(make_settings, rehearsal.admin, "ada@example.com") == ["ada@example.com's note"]
    source.dispose()
    target.dispose()


def test_requests_while_the_database_is_unreachable_get_a_retryable_503(make_settings):
    unreachable = UNREACHABLE
    with TestClient(create_app(make_settings(database_url=unreachable, auto_migrate=False))) as client:
        r = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
        assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
        assert r.headers["Retry-After"] == "5"
        assert "127.0.0.1" not in r.text and "none" not in r.text  # no connection details


def test_only_retryable_database_errors_become_a_503():
    import sqlite3

    import psycopg
    from sqlalchemy.exc import OperationalError

    from app.errors import _retryable

    def op(orig: BaseException) -> OperationalError:
        return OperationalError("SELECT 1", {}, orig)

    assert _retryable(op(psycopg.OperationalError("connection refused")))  # before any SQL ran
    assert _retryable(op(psycopg.errors.QueryCanceled("canceling statement due to statement timeout")))
    assert _retryable(op(psycopg.errors.AdminShutdown("terminating connection")))
    assert _retryable(op(psycopg.errors.DeadlockDetected("deadlock detected")))
    assert _retryable(op(sqlite3.OperationalError("database is locked")))
    assert not _retryable(op(sqlite3.OperationalError("no such table: notes")))  # a bug: 500
    assert not _retryable(op(Exception("disk I/O error")))
