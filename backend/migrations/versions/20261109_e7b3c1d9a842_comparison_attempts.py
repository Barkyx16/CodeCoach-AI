"""comparison attempts: learners' readings of authored sample answers

Revision ID: e7b3c1d9a842
Revises: c4a9e2f71b35
Create Date: 2026-11-09

Volume 10, prompt 6 (docs/COMPARE_ANSWERS.md). `comparison_attempts` holds each reading a learner
sends: the excerpts they marked with reasons, an optional choice, whether they revealed the
explanation first, a snapshot of the samples and explanation, and the comparison. Cascades with the
account; under row-level security on PostgreSQL with the policies 7c1d2e3f4a5b installs
(app/db/rls.py lists it under this revision). The lessons are files (app/seed/comparisons).
Downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7b3c1d9a842"
down_revision: str | Sequence[str] | None = "c4a9e2f71b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("comparison_attempts",)
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
        "comparison_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("lesson_id", sa.String(length=64), nullable=False),
        sa.Column("lesson_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", _json(), nullable=False),
        sa.Column("selections", _json(), nullable=False),
        sa.Column("choice", sa.String(length=8), nullable=True),
        sa.Column("feedback", _json(), nullable=False),
        sa.Column("revealed_early", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_comparison_attempts_user_id", "comparison_attempts", ["user_id"])
    op.create_index("ix_comparison_user_lesson", "comparison_attempts", ["user_id", "lesson_id"])
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
    op.drop_index("ix_comparison_user_lesson", table_name="comparison_attempts")
    op.drop_index("ix_comparison_attempts_user_id", table_name="comparison_attempts")
    op.drop_table("comparison_attempts")
