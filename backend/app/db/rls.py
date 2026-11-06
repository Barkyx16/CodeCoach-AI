"""Row-level security (PostgreSQL): the database itself keeps each learner's rows to that learner.

The application already checks ownership in every query (docs/SECURITY.md). This is the second
line: on the tables below, PostgreSQL only shows and accepts rows whose `user_id` matches the
`codecoach.user_id` setting of the current transaction. A request authenticated as a user sets it
(api/deps.py → `bind_user`), so a query that forgot its owner filter finds nothing of anyone
else's, and a write can't put a row under another user.

Fail-open by design, for work done for nobody in particular: a transaction that hasn't set
`codecoach.user_id` (the judge worker, housekeeping, the CLI, migrations, sign-in before the user is
known) sees every row, as before. Only authenticated requests are narrowed.

Not effective for a role that bypasses RLS (a superuser, or BYPASSRLS): `rls_status` reports
that, and startup logs a warning. FORCE is set so the table owner (what the app usually connects
as) is subject to it. SQLite has no RLS: everything here is a no-op there.

Not covered, deliberately: `submissions`/`execution_results` (the judge's queue depth and stall
checks count across learners inside a learner's request); the sign-in tokens (looked up by token
before the user is known); `shares`/`share_feedback` (read by the recipient); content triage tables
(admin); and child tables without a `user_id` column (reached through a covered parent).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

logger = logging.getLogger("codecoach.rls")

SETTING = "codecoach.user_id"
POLICY = "codecoach_owner_only"

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

# Unset, or set to '' (what a transaction-local setting reads as after its transaction ended on a
# pooled connection), means "no user context": see the module docstring.
_CONDITION = (
    f"coalesce(current_setting('{SETTING}', true), '') = '' OR user_id = current_setting('{SETTING}', true)"
)


def enable_statements(table: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS {POLICY} ON {table}",
        f"CREATE POLICY {POLICY} ON {table} USING ({_CONDITION}) WITH CHECK ({_CONDITION})",
    ]


def disable_statements(table: str) -> list[str]:
    return [
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
    if session.in_transaction():
        conn = session.connection()
        if conn.dialect.name == "postgresql":
            _set(conn, user_id)


def _set(conn: Connection, user_id: str) -> None:
    # Transaction-local (is_local = true): it ends with the transaction, so a pooled connection
    # never carries one request's user into the next.
    conn.execute(text("SELECT set_config(:name, :value, true)"), {"name": SETTING, "value": user_id})


@event.listens_for(Session, "after_begin")
def _narrow_each_transaction(session: Session, _transaction: Any, connection: Connection) -> None:
    user_id = session.info.get("rls_user_id")
    if user_id and connection.dialect.name == "postgresql":
        _set(connection, user_id)


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


def warn_if_not_enforced(engine: Engine) -> None:
    try:
        status = rls_status(engine)
    except Exception:  # pragma: no cover - a startup diagnostic must never stop startup
        logger.warning("row-level security status could not be read", exc_info=True)
        return
    if not status.get("supported"):
        return
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
