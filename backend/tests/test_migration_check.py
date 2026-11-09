"""scripts/check_migrations.py reports success only when every step really succeeded, and only
ever touches the database it made (Volume 8, prompt 9; docs/DATABASE.md "Checking migrations").

- A child that exits nonzero while printing plausible output fails the run: no "ok", no marker.
- An unreachable server fails the real top-level command, and the password never appears.
- A real migration failure (PostgreSQL) fails the run, and the disposable database is still dropped.
- A target that isn't one of its own names is refused before anything is changed."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, make_url, text

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "check_migrations.py"
ADMIN_URL = os.environ.get("TEST_DATABASE_ADMIN_URL")
needs_admin = pytest.mark.skipif(
    not ADMIN_URL, reason="needs TEST_DATABASE_ADMIN_URL (creates a disposable database)"
)

spec = importlib.util.spec_from_file_location("check_migrations", SCRIPT)
assert spec and spec.loader
cm = importlib.util.module_from_spec(spec)
sys.modules["check_migrations"] = cm  # its dataclasses look their module up
spec.loader.exec_module(cm)


def maintenance_url() -> str:
    assert ADMIN_URL
    return (
        make_url(ADMIN_URL)
        .set(drivername="postgresql+psycopg", database="postgres")
        .render_as_string(hide_password=False)
    )


def made_by(lines: list[str]) -> str:
    """The disposable database this run says it made."""
    return next(x for x in lines if x.startswith("target: ")).split()[1]


def still_exists(name: str) -> bool:
    engine = create_engine(maintenance_url())
    try:
        with engine.connect() as c:
            return bool(c.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar())
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "name",
    [
        "codecoach",
        "codecoach_test",
        "postgres",
        "codecoach_prod",
        "codecoach_migcheck_",
        "codecoach_migcheck_12345678x",
    ],
)
def test_only_its_own_disposable_names_are_accepted(name):
    with pytest.raises(cm.Refused):
        cm.assert_disposable(name)
    cm.assert_disposable("codecoach_migcheck_0a1b2c3d")


def test_passwords_are_masked_in_what_it_prints():
    out = cm.redact(
        "connection to postgresql+psycopg://admin:Sup3r-secret@db:5432/x failed; password=hunter2 x"
    )
    assert "Sup3r-secret" not in out and "hunter2" not in out and "admin:***@db" in out


def test_a_child_that_fails_while_printing_plausible_output_fails_the_step():
    lines: list[str] = []

    def fake(args, env):
        return cm.Result(1, "INFO  [alembic.runtime.migration] Running upgrade a -> b, done\nOK\n")

    with pytest.raises(cm.StepFailed):
        cm.step(
            "upgrade to head", ["alembic", "upgrade", "head"], "postgresql://u:pw@h/db", fake, lines.append
        )
    assert lines[0].startswith("FAIL: upgrade to head exited 1") and not any(
        x.startswith("ok:") for x in lines
    )


def test_an_unreachable_server_fails_the_real_command_without_a_marker_or_the_password():
    done = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--admin-url",
            "postgresql+psycopg://someone:Unreachable-pw-123@127.0.0.1:1/postgres",
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = done.stdout + done.stderr
    assert done.returncode == 1, out
    assert cm.MARKER not in out and "Unreachable-pw-123" not in out
    assert "FAIL: create the disposable database" in out


def test_no_admin_url_is_refused():
    done = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            k: v
            for k, v in os.environ.items()
            if k not in ("TEST_DATABASE_ADMIN_URL", "MIGRATION_CHECK_ADMIN_URL")
        },
    )
    assert done.returncode == 2 and cm.MARKER not in done.stdout


@needs_admin
def test_a_non_disposable_target_is_refused_and_left_as_it_was():
    test_url = os.environ.get("TEST_DATABASE_URL") or maintenance_url()
    engine = create_engine(test_url)
    try:
        with engine.connect() as c:
            before = sorted(inspect(c).get_table_names())
        lines: list[str] = []
        name = make_url(test_url).database
        assert cm.check(maintenance_url(), log=lines.append, name=name) == 2
        assert lines[0].startswith("REFUSED") and cm.MARKER not in lines
        with engine.connect() as c:
            assert sorted(inspect(c).get_table_names()) == before
    finally:
        engine.dispose()


@needs_admin
def test_a_failing_step_fails_the_run_and_its_database_is_still_dropped():
    lines: list[str] = []
    calls = {"n": 0}

    def fails_on_second_step(args, env):
        calls["n"] += 1
        if calls["n"] == 2:
            return cm.Result(3, "INFO Running upgrade ... (looks fine)\n")
        return cm.run_child(args, env)

    assert cm.check(maintenance_url(), runner=fails_on_second_step, log=lines.append) == 1
    assert any(x.startswith("FAIL: upgrade to head") for x in lines)
    assert cm.MARKER not in lines
    assert any(x.startswith("cleanup: dropped") for x in lines)
    assert not still_exists(made_by(lines))


def _make_what_the_head_migration_adds(conn) -> str:
    """At the previous revision, create one thing the head migration adds (a table, else a column),
    so its real upgrade fails. Found by comparing the models with the database, so it follows
    whichever migration is the head; returns the name to look for in the failure."""
    import app.models  # noqa: F401  (every model registered on Base.metadata)
    from app.db.session import Base

    present = inspect(conn)
    existing = set(present.get_table_names())
    for table in sorted(Base.metadata.tables):
        if table not in existing:
            conn.execute(text(f'CREATE TABLE "{table}" (id varchar(36) PRIMARY KEY)'))
            return table
    for table in sorted(Base.metadata.tables):
        have = {c["name"] for c in present.get_columns(table)}
        for column in Base.metadata.tables[table].columns:
            if column.name not in have:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column.name}" text'))
                return column.name
    raise AssertionError("the head migration adds no table or column: sabotage it some other way")


@needs_admin
def test_a_real_migration_failure_fails_the_run_and_cleans_up():
    """Something the head migration creates already exists, so the real alembic fails."""
    lines: list[str] = []
    sabotaged: dict[str, str] = {}

    def sabotage_then_run(args, env):
        if list(args)[-1] == "head" and not sabotaged:
            engine = create_engine(env["DATABASE_URL"])
            with engine.begin() as c:
                sabotaged["name"] = _make_what_the_head_migration_adds(c)
            engine.dispose()
        return cm.run_child(args, env)

    assert cm.check(maintenance_url(), runner=sabotage_then_run, log=lines.append) == 1
    failed = next(x for x in lines if x.startswith("FAIL:"))
    assert failed.startswith("FAIL: upgrade to head") and sabotaged["name"] in failed, failed
    assert cm.MARKER not in lines and not still_exists(made_by(lines))


@needs_admin
def test_the_real_check_passes_end_to_end():
    lines: list[str] = []
    assert cm.check(maintenance_url(), log=lines.append) == 0
    assert lines[-1] == cm.MARKER and any("records intact after the round trip" in x for x in lines)
    assert not still_exists(made_by(lines))
