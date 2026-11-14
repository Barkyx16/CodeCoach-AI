"""Who the application connects as, and the grants that let an ordinary role run it.

Two roles in production (docs/STORAGE.md):
- the **owner** (e.g. `codecoach_owner`) owns the schema and tables. Only migrations, the seed and
  `grant-app-role` connect as it, from a one-shot job; the API never holds its password.
- the **app** role (e.g. `codecoach_app`) is what the API and the worker use: it can read and write
  rows but owns nothing, so it can't ALTER a table, turn row-level security off, or drop anything.
  Not a superuser and no BYPASSRLS, so the RLS policies apply to it.

`grant_statements` is what the owner runs after each migration (idempotent). `role_report` is
what `check-rls` prints: the connected role's attributes and whether it owns any table.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]{0,62}")


def check_identifier(name: str) -> str:
    """A role name we'll put into SQL: lowercase letters, digits and underscores only, so it never
    needs quoting and can't carry anything else."""
    if not _IDENTIFIER.fullmatch(name):
        raise ValueError("a role name must be lowercase letters, digits and underscores (at most 63)")
    return name


def grant_statements(app_role: str) -> list[str]:
    """Row access for the app role on everything in the current schema, and nothing more.
    The migration ledger stays read-only to it (readiness reads it; only migrations write it).
    Default privileges cover tables a later migration creates before this runs again."""
    role = check_identifier(app_role)
    return [
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
        f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE alembic_version FROM {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {role}",
    ]


def apply_grants(conn: Connection, app_role: str) -> None:
    """Run as the owner, after `alembic upgrade head`. Refuses to grant to the role it's connected
    as (that would be the owner granting itself) or to a role that bypasses RLS."""
    role = check_identifier(app_role)
    me = conn.execute(text("SELECT current_user")).scalar_one()
    if me == role:
        raise ValueError("connect as the table owner (the migration role) to grant to the app role")
    found = conn.execute(
        text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role}
    ).one_or_none()
    if found is None:
        raise ValueError(f"role {role} doesn't exist: create it first (deploy/postgres-init)")
    if found.rolsuper or found.rolbypassrls:
        raise ValueError(f"role {role} is a superuser or has BYPASSRLS: row-level security wouldn't apply")
    for statement in grant_statements(role):
        conn.execute(text(statement))


def role_report(conn: Connection) -> dict[str, Any]:
    """The connected role, as PostgreSQL sees it. Names and counts only, never a password."""
    role = conn.execute(
        text(
            "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
            "FROM pg_roles WHERE rolname = current_user"
        )
    ).one()
    owned = conn.execute(
        text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relkind IN ('r', 'p') "
            "AND pg_get_userbyid(c.relowner) = current_user"
        )
    ).scalar_one()
    can_create = conn.execute(text("SELECT has_schema_privilege(current_schema(), 'CREATE')")).scalar_one()
    return {
        "role": role.rolname,
        "superuser": bool(role.rolsuper),
        "bypass_rls": bool(role.rolbypassrls),
        "can_create_roles": bool(role.rolcreaterole),
        "can_create_databases": bool(role.rolcreatedb),
        "owns_tables": int(owned),
        "can_create_in_schema": bool(can_create),
    }


def least_privilege_problems(report: dict[str, Any]) -> list[str]:
    """What keeps a connected role from being the ordinary app role production wants."""
    problems = []
    if report["superuser"] or report["bypass_rls"]:
        problems.append("is a superuser or has BYPASSRLS, so row-level security doesn't apply to it")
    if report["owns_tables"]:
        problems.append(
            f"owns {report['owns_tables']} table(s), so it could alter them or turn row-level security off"
        )
    if report["can_create_in_schema"]:
        problems.append("can create objects in the schema")
    if report["can_create_roles"]:
        problems.append("can create roles")
    return problems


def engine_role_report(engine: Engine) -> dict[str, Any] | None:
    if engine.dialect.name != "postgresql":
        return None
    with engine.connect() as conn:
        return role_report(conn)
