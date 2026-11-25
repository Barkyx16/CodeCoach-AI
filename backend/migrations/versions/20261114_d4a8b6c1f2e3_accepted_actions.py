"""accepted actions: one improvement the learner chose, shared by the plan, schedule and kit

Revision ID: d4a8b6c1f2e3
Revises: c3f7a9d2e614
Create Date: 2026-11-14

Volume 12, prompt 1 (docs/ACCEPTED_ACTIONS.md). `accepted_actions` holds each improvement a learner
accepted from feedback: where it came from (an interview review's improvement, unique per account
so accepting again finds the same row), its title and notes, the practice it points at, whether it
repeats weekly, when a one-off was done, and a revision for conflict-checked edits. Its occurrences
are schedule entries of kind "accepted_action"; `schedule_entries.completed_at` (new, nullable,
NULL for every existing row) records when the learner said an occurrence was done. Cascades with
the account; under row-level security on PostgreSQL with the policies 7c1d2e3f4a5b installs
(app/db/rls.py lists it under this revision). Downgrade drops both.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4a8b6c1f2e3"
down_revision: str | Sequence[str] | None = "c3f7a9d2e614"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("accepted_actions",)
POLICY = "codecoach_owner_only"
MAINTENANCE_POLICY = "codecoach_maintenance_read"
_NO_USER = "coalesce(current_setting('codecoach.user_id', true), '') = ''"
_SCOPE = "coalesce(current_setting('codecoach.scope', true), '')"
CONDITION = (
    "user_id = current_setting('codecoach.user_id', true) "
    f"OR ({_NO_USER} AND {_SCOPE} NOT IN ('request', 'worker', 'maintenance'))"
)
MAINTENANCE_CONDITION = f"{_NO_USER} AND {_SCOPE} = 'maintenance'"


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "accepted_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("source_key", sa.String(length=200), nullable=False),
        sa.Column("source", _json(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("practice_href", sa.String(length=300), nullable=True),
        sa.Column("recurrence", sa.String(length=8), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "source_kind", "source_id", "source_key", name="uq_accepted_action_source"
        ),
    )
    op.create_index("ix_accepted_actions_user_id", "accepted_actions", ["user_id"])
    op.add_column("schedule_entries", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"CREATE POLICY {POLICY} ON {table} USING ({CONDITION}) WITH CHECK ({CONDITION})"))
        op.execute(
            sa.text(
                f"CREATE POLICY {MAINTENANCE_POLICY} ON {table} FOR SELECT USING ({MAINTENANCE_CONDITION})"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("schedule_entries") as batch:
        batch.drop_column("completed_at")
    op.drop_index("ix_accepted_actions_user_id", table_name="accepted_actions")
    op.drop_table("accepted_actions")
