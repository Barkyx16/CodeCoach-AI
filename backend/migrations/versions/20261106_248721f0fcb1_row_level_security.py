"""row-level security on learner-owned tables (PostgreSQL)

Revision ID: 248721f0fcb1
Revises: 9152380226e0
Create Date: 2026-11-06

Defence in depth (app/db/rls.py): on each table below, PostgreSQL only shows and accepts rows
whose user_id matches the transaction's `codecoach.user_id` setting, which authenticated requests set.
A transaction that sets nothing (worker, CLI, housekeeping, this migration) sees every row.
FORCE makes it apply to the table owner too. Superusers and BYPASSRLS roles are never subject to
RLS: the app must connect as an ordinary role for this to take effect (docs/SECURITY.md).

No data changes. SQLite: nothing to do. Downgrade removes the policies and turns RLS off.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "248721f0fcb1"
down_revision: str | Sequence[str] | None = "9152380226e0"
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
CONDITION = (
    "coalesce(current_setting('codecoach.user_id', true), '') = '' "
    "OR user_id = current_setting('codecoach.user_id', true)"
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY} ON {table}"))
        op.execute(sa.text(f"CREATE POLICY {POLICY} ON {table} USING ({CONDITION}) WITH CHECK ({CONDITION})"))


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY} ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
