"""work samples: learners' drafts and the artifacts they send for feedback

Revision ID: c4a9e2f71b35
Revises: 8e4b1d7c2f60
Create Date: 2026-11-09

Volume 10, prompt 5 (docs/WORK_SAMPLES.md). `work_sample_drafts` holds a work sample in progress
per learner and brief, saved against a revision. `work_sample_attempts` holds each artifact sent for
feedback, with a snapshot of the brief it was written against and the checks' feedback; a revision is
a new row naming the one it revises. Both cascade with the account and are under row-level security
on PostgreSQL, with the policies 7c1d2e3f4a5b installs (app/db/rls.py lists them under this
revision). The briefs are files (app/seed/worksamples). Downgrade drops both tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4a9e2f71b35"
down_revision: str | Sequence[str] | None = "8e4b1d7c2f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("work_sample_attempts", "work_sample_drafts")
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
        "work_sample_drafts",
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("brief_id", sa.String(length=64), primary_key=True),
        sa.Column("sections", _json(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "work_sample_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("brief_id", sa.String(length=64), nullable=False),
        sa.Column("brief_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", _json(), nullable=False),
        sa.Column("sections", _json(), nullable=False),
        sa.Column("feedback", _json(), nullable=False),
        sa.Column("revision_of", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_work_sample_attempts_user_id", "work_sample_attempts", ["user_id"])
    op.create_index("ix_work_sample_user_brief", "work_sample_attempts", ["user_id", "brief_id"])
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
    op.drop_index("ix_work_sample_user_brief", table_name="work_sample_attempts")
    op.drop_index("ix_work_sample_attempts_user_id", table_name="work_sample_attempts")
    op.drop_table("work_sample_attempts")
    op.drop_table("work_sample_drafts")
