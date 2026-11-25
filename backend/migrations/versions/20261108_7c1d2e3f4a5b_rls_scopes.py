"""row-level security: requests and the worker see nothing until a user is bound (PostgreSQL)

Revision ID: 7c1d2e3f4a5b
Revises: dd8a6dc39c8f
Create Date: 2026-11-08

Until now a transaction with no `codecoach.user_id` saw every learner's row: right for migrations
and operator commands, too wide for an unauthenticated request or the background worker
(app/db/rls.py). This adds a second transaction-local setting, `codecoach.scope`:
- 'request' or 'worker' with no user: no rows at all;
- 'maintenance' with no user: every row, read-only (a separate SELECT-only policy);
- unset: every row, as before (migrations, operator commands).
A bound user still sees only their own rows, whatever the scope.

Same 30 tables as 248721f0fcb1. No data changes. SQLite: nothing to do. Downgrade restores the
previous policy.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c1d2e3f4a5b"
down_revision: str | Sequence[str] | None = "dd8a6dc39c8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever.
TABLES = (
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
POLICY = "codecoach_owner_only"
MAINTENANCE_POLICY = "codecoach_maintenance_read"
_NO_USER = "coalesce(current_setting('codecoach.user_id', true), '') = ''"
_SCOPE = "coalesce(current_setting('codecoach.scope', true), '')"
CONDITION = (
    "user_id = current_setting('codecoach.user_id', true) "
    f"OR ({_NO_USER} AND {_SCOPE} NOT IN ('request', 'worker', 'maintenance'))"
)
MAINTENANCE_CONDITION = f"{_NO_USER} AND {_SCOPE} = 'maintenance'"
PREVIOUS_CONDITION = (
    "coalesce(current_setting('codecoach.user_id', true), '') = '' "
    "OR user_id = current_setting('codecoach.user_id', true)"
)


def _policy(table: str, condition: str) -> None:
    op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY} ON {table}"))
    op.execute(sa.text(f"CREATE POLICY {POLICY} ON {table} USING ({condition}) WITH CHECK ({condition})"))


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        _policy(table, CONDITION)
        op.execute(sa.text(f"DROP POLICY IF EXISTS {MAINTENANCE_POLICY} ON {table}"))
        op.execute(
            sa.text(
                f"CREATE POLICY {MAINTENANCE_POLICY} ON {table} FOR SELECT USING ({MAINTENANCE_CONDITION})"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS {MAINTENANCE_POLICY} ON {table}"))
        _policy(table, PREVIOUS_CONDITION)
