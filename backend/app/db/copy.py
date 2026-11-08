"""Optional: copy a development database (usually backend/codecoach.db, SQLite) into a freshly
migrated PostgreSQL database. Nothing runs this automatically; `python -m app.cli copy-database`
does, and only writes with --apply.

A SQLite file can't simply be loaded into PostgreSQL: the types, the migration ledger and the
sequences differ. So this reads every row through this version's models and inserts it on the
target, in one transaction that is rolled back unless every table's row count matches.

Refuses, before writing anything, when:
- the source has a table or column this version doesn't know, or lacks one it needs (start this
  version of the app on the source once: it adds missing columns; then retry);
- the target isn't migrated to this version's head (`alembic upgrade head`), or already has rows
  in any table (seed it after copying, not before);
- source and target are the same database.

Never touches the source. Skips short-lived security and delivery state (sign-in sessions,
emailed codes and links, queued emails, rate-limit counters): people sign in again on the new
server, and nothing old is emailed from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Integer, Table, func, inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table)
from app.db.session import Base

SKIPPED = {
    "refresh_tokens": "sign-in sessions: people sign in again",
    "password_reset_tokens": "emailed reset links",
    "email_verification_tokens": "emailed codes and links (a new one can be sent)",
    "email_jobs": "queued emails: nothing old is sent from the new server",
    "rate_limit_counters": "rate-limit counters",
}
_IGNORED_SOURCE_TABLES = {"alembic_version", "sqlite_sequence"}
BATCH = 500


@dataclass
class CopyPlan:
    counts: dict[str, int] = field(default_factory=dict)  # table -> rows to copy
    skipped: dict[str, int] = field(default_factory=dict)  # table -> rows left behind
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _tables() -> list[Table]:
    return list(Base.metadata.sorted_tables)


def plan(source: Engine, target: Engine) -> CopyPlan:
    from app.api.routes.health import schema_state

    result = CopyPlan()
    if source.url.render_as_string(hide_password=False) == target.url.render_as_string(hide_password=False):
        result.problems.append("the source and the target are the same database")
        return result

    src = inspect(source)
    known = {t.name for t in _tables()}
    for name in sorted(set(src.get_table_names()) - known - _IGNORED_SOURCE_TABLES):
        result.problems.append(
            f"source table {name} is unknown to this version: copy with the version that made it"
        )
    for table in _tables():
        if not src.has_table(table.name):
            result.problems.append(
                f"source has no table {table.name}: start this version of the app on it once, then retry"
            )
            continue
        columns = {c["name"] for c in src.get_columns(table.name)}
        if missing := sorted(set(table.c.keys()) - columns):
            result.problems.append(
                f"source table {table.name} lacks {', '.join(missing)}: start this version of the app on it once"
            )
        if extra := sorted(columns - set(table.c.keys())):
            result.problems.append(
                f"source table {table.name} has columns this version doesn't know: {', '.join(extra)}"
            )
    if result.problems:
        return result

    with Session(bind=target) as db:
        state = schema_state(db)
    if state != "current":
        result.problems.append(f"the target's schema is {state}: run `alembic upgrade head` on it first")
        return result
    with target.connect() as conn:
        for table in _tables():
            rows = conn.execute(select(func.count()).select_from(table)).scalar_one()
            if rows:
                result.problems.append(
                    f"the target isn't empty ({table.name} has {rows} rows): copy only into a freshly "
                    "migrated, unseeded database"
                )
                break
    with source.connect() as conn:
        for table in _tables():
            rows = conn.execute(select(func.count()).select_from(table)).scalar_one()
            (result.skipped if table.name in SKIPPED else result.counts)[table.name] = rows
    return result


def _self_references(table: Table) -> list[str]:
    return [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]


def _parents_first(table: Table, rows: list[dict]) -> list[dict]:
    """Rows of a table that points at itself (an answer revising an earlier one), ordered so each
    row comes after the one it points to."""
    columns = _self_references(table)
    if not columns:
        return rows
    [pk] = [c.name for c in table.primary_key.columns]
    pending, placed, ordered = list(rows), set(), []
    while pending:
        ready = [r for r in pending if all(r[c] is None or r[c] in placed for c in columns)]
        if not ready:
            raise ValueError(f"{table.name}: rows refer to each other in a cycle or to missing rows")
        for row in ready:
            placed.add(row[pk])
            ordered.append(row)
        ready_ids = {id(r) for r in ready}
        pending = [r for r in pending if id(r) not in ready_ids]
    return ordered


def _reset_sequences(conn: Connection) -> None:
    """Copied rows keep their ids; PostgreSQL's sequences must then continue after the largest."""
    if conn.dialect.name != "postgresql":
        return
    quote = conn.dialect.identifier_preparer.quote
    for table in _tables():
        columns = list(table.primary_key.columns)
        if len(columns) != 1 or not isinstance(columns[0].type, Integer):
            continue
        column = columns[0].name
        sequence = conn.execute(
            text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": table.name, "c": column}
        ).scalar_one()
        if sequence is None:
            continue
        conn.execute(
            text(
                f"SELECT setval(:s, coalesce(max({quote(column)}), 1), max({quote(column)}) IS NOT NULL) "
                f"FROM {quote(table.name)}"
            ),
            {"s": sequence},
        )


def copy(source: Engine, target: Engine) -> dict[str, int]:
    """Copy every table but the skipped ones, in one transaction. Re-checks the plan first."""
    checked = plan(source, target)
    if not checked.ok:
        raise ValueError("; ".join(checked.problems))
    copied: dict[str, int] = {}
    with source.connect() as src, target.begin() as dst:
        for table in _tables():
            if table.name in SKIPPED:
                continue
            rows = [dict(r._mapping) for r in src.execute(select(table))]
            rows = _parents_first(table, rows)
            for start in range(0, len(rows), BATCH):
                dst.execute(table.insert(), rows[start : start + BATCH])
            copied[table.name] = len(rows)
        _reset_sequences(dst)
        for table in _tables():
            if table.name in SKIPPED:
                continue
            landed = dst.execute(select(func.count()).select_from(table)).scalar_one()
            if landed != checked.counts[table.name]:
                raise RuntimeError(  # rolls the whole copy back
                    f"{table.name}: {landed} rows arrived of {checked.counts[table.name]}; nothing was kept"
                )
    return copied
