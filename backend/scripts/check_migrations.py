"""Check the migrations on a database this run creates, and only report success when every step
actually succeeded (Volume 8, prompt 9; docs/DATABASE.md "Checking migrations").

    python scripts/check_migrations.py --admin-url postgresql+psycopg://ADMIN@HOST:5432/postgres

1. Creates `codecoach_migcheck_<random>` (owned by the admin URL's role) and nothing else.
2. Upgrades to the previous revision, writes representative records (a user and a note), then
   upgrades to head and checks the records are still there.
3. `alembic check` (the models match the schema), on a fresh connection that reports the
   server version, database and role it is really using.
4. Steps the latest migration down and up again, records intact; then downgrades to base and
   upgrades the whole chain from empty.
5. Drops the database it created, also when a step fails or the run is interrupted.

Each child's exit status is checked directly (no pipelines, no shell). A failing step prints its
last lines with any password in a URL masked, and the run exits 1. "MIGRATIONS-OK" is printed
only at the very end, after every step exited 0. A database name that isn't one this script
makes is refused before anything is changed (exit 2). PostgreSQL only: on SQLite the app makes
its tables with create_all (the migrations alter constraints, which SQLite can't).
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
OWN_NAME = re.compile(r"^codecoach_migcheck_[0-9a-f]{8}$")
TAIL_LINES = 30
MARKER = "MIGRATIONS-OK"


class Refused(Exception):
    """The target isn't a database this run made: nothing was changed."""


class StepFailed(Exception):
    pass


def redact(text: str) -> str:
    """Mask the password in any URL (scheme://user:password@host) and in key=value pairs."""
    text = re.sub(r"(://[^:/@\s]+):[^@\s]*@", r"\1:***@", text)
    return re.sub(r"(?i)(password|passwd|pwd)=\S+", r"\1=***", text)


def assert_disposable(name: str) -> None:
    if not OWN_NAME.match(name or ""):
        raise Refused(
            f"refusing to touch database {name!r}: only codecoach_migcheck_<8 hex> databases made by this script"
        )


@dataclass
class Result:
    returncode: int
    output: str


Runner = Callable[[Sequence[str], dict[str, str]], Result]


def run_child(args: Sequence[str], env: dict[str, str]) -> Result:
    done = subprocess.run(list(args), cwd=BACKEND, env=env, capture_output=True, text=True, check=False)
    return Result(done.returncode, (done.stdout or "") + (done.stderr or ""))


def step(name: str, args: Sequence[str], url: str, runner: Runner, log: Callable[[str], None]) -> str:
    env = {**os.environ, "DATABASE_URL": url, "ENVIRONMENT": "development"}
    started = time.monotonic()
    result = runner(args, env)
    if result.returncode != 0:
        tail = "\n".join(result.output.strip().splitlines()[-TAIL_LINES:])
        log(f"FAIL: {name} exited {result.returncode}\n{redact(tail)}")
        raise StepFailed(name)
    log(f"ok: {name} ({time.monotonic() - started:.1f}s)")
    return result.output


def revisions() -> tuple[str, str]:
    """(head, the revision before it), from this code's own migrations."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    assert head is not None
    previous = script.get_revision(head).down_revision
    assert isinstance(previous, str)
    return head, previous


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
    """A row with only what the schema at this revision requires (it may be older than the models)."""
    from sqlalchemy import MetaData, Table

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


def records_intact(url: str) -> bool:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)  # a fresh connection: nothing cached from before the migration
    try:
        with engine.connect() as c:
            email = c.execute(text("SELECT email FROM users WHERE id = 'u-migcheck'")).scalar()
            title = c.execute(text("SELECT title FROM notes WHERE id = 'n-migcheck'")).scalar()
        return email == "migcheck@example.com" and title == "Written before the upgrade"
    finally:
        engine.dispose()


def describe(url: str) -> str:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as c:
            row = c.execute(
                text("SELECT current_setting('server_version'), current_database(), current_user")
            ).one()
        return f"PostgreSQL {row[0]}, database {row[1]}, role {row[2]}"
    finally:
        engine.dispose()


def check(
    admin_url: str, runner: Runner = run_child, log: Callable[[str], None] = print, name: str | None = None
) -> int:
    from sqlalchemy import create_engine, make_url, text

    name = name or f"codecoach_migcheck_{secrets.token_hex(4)}"
    try:
        assert_disposable(name)
    except Refused as exc:
        log(f"REFUSED: {exc}")
        return 2
    admin = make_url(admin_url)
    if not admin.drivername.startswith("postgresql"):
        log("REFUSED: PostgreSQL only (on SQLite the app makes its tables with create_all)")
        return 2
    target = admin.set(database=name).render_as_string(hide_password=False)
    alembic = [sys.executable, "-m", "alembic"]
    created = False
    server = create_engine(admin.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT")
    try:
        try:
            with server.connect() as c:
                c.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        except Exception as exc:  # noqa: BLE001 - reported, redacted, and the run fails
            log(
                f"FAIL: create the disposable database\n{redact(str(exc).splitlines()[0] if str(exc) else repr(exc))}"
            )
            return 1
        log(f"target: {name} (made by this run; dropped at the end)")
        head, previous = revisions()
        step(
            f"upgrade to the previous revision {previous}",
            [*alembic, "upgrade", previous],
            target,
            runner,
            log,
        )
        engine = create_engine(target)
        try:
            with engine.begin() as c:
                insert_minimal(c, "users", id="u-migcheck", email="migcheck@example.com", is_guest=False)
                insert_minimal(
                    c, "notes", id="n-migcheck", user_id="u-migcheck", title="Written before the upgrade"
                )
        finally:
            engine.dispose()
        log("ok: representative records written (a user and a note)")
        step(f"upgrade to head {head}", [*alembic, "upgrade", "head"], target, runner, log)
        if not records_intact(target):
            log("FAIL: the records written before the upgrade aren't intact")
            return 1
        log(f"ok: records intact; {describe(target)}")
        step("alembic check (models match the schema)", [*alembic, "check"], target, runner, log)
        step("step the latest migration down", [*alembic, "downgrade", previous], target, runner, log)
        step("and up again", [*alembic, "upgrade", "head"], target, runner, log)
        if not records_intact(target):
            log("FAIL: the records aren't intact after stepping the latest migration down and up")
            return 1
        log("ok: records intact after the round trip")
        step("downgrade to base", [*alembic, "downgrade", "base"], target, runner, log)
        step("upgrade the whole chain from empty", [*alembic, "upgrade", "head"], target, runner, log)
    except StepFailed:
        return 1
    except Exception as exc:  # noqa: BLE001 - any other failure fails the run, redacted
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        log(f"FAIL: {type(exc).__name__}: {redact(first)}")
        return 1
    finally:
        if created:
            try:
                assert_disposable(name)
                with server.connect() as c:
                    c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
                log(f"cleanup: dropped {name}")
            except Exception as exc:  # noqa: BLE001 - say so: the operator must remove it
                log(f"WARNING: couldn't drop {name}: {redact(str(exc).splitlines()[0])}")
        server.dispose()
    log(MARKER)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--admin-url",
        default=os.environ.get("MIGRATION_CHECK_ADMIN_URL") or os.environ.get("TEST_DATABASE_ADMIN_URL"),
        help="a role that may create databases; connect to a maintenance database such as postgres",
    )
    args = parser.parse_args(argv)
    if not args.admin_url:
        print("REFUSED: give --admin-url (or MIGRATION_CHECK_ADMIN_URL): this check makes its own database")
        return 2
    return check(args.admin_url)


if __name__ == "__main__":
    sys.exit(main())
