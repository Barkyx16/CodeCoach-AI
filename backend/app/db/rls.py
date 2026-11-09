"""Row-level security (PostgreSQL): the database itself keeps each learner's rows to that learner.

The application already checks ownership in every query (docs/SECURITY.md). This is the second
line: on the tables below, PostgreSQL only shows and accepts rows whose `user_id` matches the
`codecoach.user_id` setting of the current transaction. A request authenticated as a user sets it
(api/deps.py → `bind_user`), so a query that forgot its owner filter finds nothing of anyone
else's, and a write can't put a row under another user.

Who sees what is decided per transaction by two settings, both transaction-local so a pooled
connection never carries them into the next use:
- `codecoach.user_id`: once set, only that learner's rows, whatever the scope.
- `codecoach.scope`, when no user is set:
  - `request` (every API request, api/deps.get_db): **nothing**. A request that hasn't
    authenticated, or a route that forgot to, sees no learner's rows and can't write any.
  - `worker` (the judge worker and the jobs thread): **nothing**, unless it binds the one user
    whose work it's doing (the judge does, to record a solved problem).
  - `maintenance` (one named, reviewed step at a time, `maintenance()`): every learner's rows,
    **read-only**. Today only the guest clean-up, which reads each guest's latest activity time.
  - unset (operator commands, migrations, tests' own sessions): every row. Those run with the
    owner's or an operator's credentials, deliberately, not from a request.

Not effective for a role that bypasses RLS (a superuser, or BYPASSRLS): `rls_status` reports
that, and startup logs a warning. FORCE is set so the table owner (what development connects as)
is subject to it too. An owner could still turn it off, so production connects as an app role that
owns nothing (db/roles.py, docs/STORAGE.md). SQLite has no RLS: everything here is a no-op there.

Not covered, deliberately: `submissions`/`execution_results` (the judge's queue depth and stall
checks count across learners inside a learner's request); the sign-in tokens (looked up by token
before the user is known); `shares`/`share_feedback` (read by the recipient); content triage tables
(admin); `update_receipts` (no content, only ids, revision numbers and a digest; purged across
learners by housekeeping, which runs in the worker scope; every lookup filters by user); and child
tables without a `user_id` column (reached through a covered parent).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

logger = logging.getLogger("codecoach.rls")

SETTING = "codecoach.user_id"
SCOPE_SETTING = "codecoach.scope"
POLICY = "codecoach_owner_only"
MAINTENANCE_POLICY = "codecoach_maintenance_read"
REQUEST, WORKER, MAINTENANCE = "request", "worker", "maintenance"
SCOPES = (REQUEST, WORKER, MAINTENANCE)

# Every table here has a `user_id` column holding the owner's id. Migration 248721f0fcb1 enables
# RLS on exactly this list; tests check the two agree.
PROTECTED_TABLES: tuple[str, ...] = (
    "ai_interactions",
    "answer_evaluations",
    "answer_flags",
    "answer_self_reviews",
    "applications",
    "bookmarks",
    "drill_attempts",
    "experience_entries",
    "import_batches",
    "imported_records",
    "interview_kits",
    "interview_reflections",
    "interview_retries",
    "learn_events",
    "notes",
    "practice_answers",
    "practice_collections",
    "practice_goals",
    "practice_plans",
    "practice_sessions",
    "progress_events",
    "reflection_actions",
    "review_items",
    "role_targets",
    "scenario_attempts",
    "schedule_entries",
    "schedule_settings",
    "user_onboarding",
    "whiteboard_attempts",
    "whiteboard_drafts",
)

# Unset, or '' (what a transaction-local setting reads as on a pooled connection after its
# transaction ended), means "not set". Migration 7c1d2e3f4a5b installs exactly these.
_NO_USER = f"coalesce(current_setting('{SETTING}', true), '') = ''"
_SCOPE = f"coalesce(current_setting('{SCOPE_SETTING}', true), '')"
_CONDITION = (
    f"user_id = current_setting('{SETTING}', true) "
    f"OR ({_NO_USER} AND {_SCOPE} NOT IN ('{REQUEST}', '{WORKER}', '{MAINTENANCE}'))"
)
_MAINTENANCE_CONDITION = f"{_NO_USER} AND {_SCOPE} = '{MAINTENANCE}'"


def enable_statements(table: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS {POLICY} ON {table}",
        f"CREATE POLICY {POLICY} ON {table} USING ({_CONDITION}) WITH CHECK ({_CONDITION})",
        f"DROP POLICY IF EXISTS {MAINTENANCE_POLICY} ON {table}",
        f"CREATE POLICY {MAINTENANCE_POLICY} ON {table} FOR SELECT USING ({_MAINTENANCE_CONDITION})",
    ]


def disable_statements(table: str) -> list[str]:
    return [
        f"DROP POLICY IF EXISTS {MAINTENANCE_POLICY} ON {table}",
        f"DROP POLICY IF EXISTS {POLICY} ON {table}",
        f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY",
    ]


def apply(conn: Connection, tables: tuple[str, ...] = PROTECTED_TABLES) -> None:
    """Enable the policies (idempotent). Used by the migration and by the development
    `create_all` start-up, so a local PostgreSQL database gets them too."""
    if conn.dialect.name != "postgresql":
        return
    existing = set(
        conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")).scalars()
    )
    for table in tables:
        if table in existing:
            for statement in enable_statements(table):
                conn.execute(text(statement))


def bind_user(session: Session, user_id: str) -> None:
    """Narrow this session to one user's rows from now on (every transaction it starts). If a
    transaction is already open, it's narrowed at once."""
    session.info["rls_user_id"] = user_id
    _apply_now(session)


def set_scope(session: Session, scope: str) -> Session:
    """Declare what this session is for (see the module docstring). Applies to every transaction
    it starts, and at once to an open one. Returns the session."""
    if scope not in SCOPES:
        raise ValueError(f"unknown row-level security scope {scope!r}")
    session.info["rls_scope"] = scope
    _apply_now(session)
    return session


def scoped(factory: Callable[[], Session], scope: str) -> Callable[[], Session]:
    """A session factory whose sessions all start in `scope` (the worker's, the jobs thread's)."""
    if scope not in SCOPES:
        raise ValueError(f"unknown row-level security scope {scope!r}")

    def make() -> Session:
        return set_scope(factory(), scope)

    return make


@contextmanager
def maintenance(session: Session, reason: str) -> Iterator[Session]:
    """Read every learner's rows (never write them) for one named step, then go back to the
    session's scope. Logged with its reason, so each use stays visible and reviewable."""
    previous = session.info.get("rls_scope")
    logger.info("row-level security: maintenance read for %s", reason)
    session.info["rls_scope"] = MAINTENANCE
    _apply_now(session)
    try:
        yield session
    finally:
        if previous is None:
            session.info.pop("rls_scope", None)
        else:
            session.info["rls_scope"] = previous
        _apply_now(session)


def _apply_now(session: Session) -> None:
    if session.in_transaction():
        conn = session.connection()
        if conn.dialect.name == "postgresql":
            _set(conn, session.info)


def _set(conn: Connection, info: dict) -> None:
    # Transaction-local (is_local = true): it ends with the transaction, so a pooled connection
    # never carries one request's user or scope into the next.
    conn.execute(
        text("SELECT set_config(:u, :uv, true), set_config(:s, :sv, true)"),
        {
            "u": SETTING,
            "uv": info.get("rls_user_id") or "",
            "s": SCOPE_SETTING,
            "sv": info.get("rls_scope") or "",
        },
    )


@event.listens_for(Session, "after_begin")
def _narrow_each_transaction(session: Session, _transaction: Any, connection: Connection) -> None:
    if (
        session.info.get("rls_user_id") or session.info.get("rls_scope")
    ) and connection.dialect.name == "postgresql":
        _set(connection, session.info)


def rls_status(engine: Engine) -> dict[str, Any]:
    """What's in force: whether the connected role bypasses RLS, and which protected tables
    have it enabled, forced and with the policy. Empty on SQLite."""
    if engine.dialect.name != "postgresql":
        return {"supported": False}
    with engine.connect() as conn:
        role = conn.execute(
            text("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        rows = conn.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                "EXISTS (SELECT 1 FROM pg_policies p WHERE p.tablename = c.relname AND p.policyname = :policy) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = current_schema() AND c.relkind = 'r'"
            ),
            {"policy": POLICY},
        ).all()
    by_table = {name: (enabled, forced, has_policy) for name, enabled, forced, has_policy in rows}
    missing = [t for t in PROTECTED_TABLES if t in by_table and not all(by_table[t])]
    return {
        "supported": True,
        "role": role.rolname,
        "role_bypasses_rls": bool(role.rolsuper or role.rolbypassrls),
        "protected": [t for t in PROTECTED_TABLES if t in by_table and all(by_table[t])],
        "missing": missing,
    }


def warn_if_not_enforced(engine: Engine, production: bool = False) -> None:
    from app.db.roles import engine_role_report

    try:
        status = rls_status(engine)
        report = engine_role_report(engine)
    except Exception:  # pragma: no cover - a startup diagnostic must never stop startup
        logger.warning("row-level security status could not be read", exc_info=True)
        return
    if not status.get("supported"):
        return
    if report and report["owns_tables"] and not status["role_bypasses_rls"]:
        # Development connects as the owner (one role is simpler); production should not.
        logger.log(
            logging.WARNING if production else logging.INFO,
            "database role %s owns %s tables: it could turn row-level security off. In production "
            "connect the API as an app role that owns nothing (docs/STORAGE.md)",
            status["role"],
            report["owns_tables"],
        )
    if status["role_bypasses_rls"]:
        logger.warning(
            "row-level security is NOT enforced: database role %s is a superuser or has BYPASSRLS; "
            "connect as an ordinary role (docs/SECURITY.md)",
            status["role"],
        )
    elif status["missing"]:
        logger.warning(
            "row-level security is missing on: %s (run `alembic upgrade head`)", ", ".join(status["missing"])
        )
