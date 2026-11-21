"""lab reveals: a debugging exercise's explanation and repair, shown because the learner asked

Revision ID: b2e6d4a8c157
Revises: f5b9d3e7a1c4
Create Date: 2026-11-16

Volume 16, prompt 2 (docs/ATTEMPT_CONDITIONS.md, "Debugging exercises"). Adds `lab_reveals`: one
row each time a learner opens a debugging exercise's explanation and reference repair after their
last attempt at it (asking again before the next attempt adds nothing), with the exercise's version
then. The next attempt at that version says "Solution revealed". Owner-only under row-level
security, deleted with the account. Nothing earlier is filled in: before this, opening it was
recorded nowhere, and attempts from then say so.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2e6d4a8c157"
down_revision: str | Sequence[str] | None = "f5b9d3e7a1c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("lab_reveals",)
POLICY = "codecoach_owner_only"
MAINTENANCE_POLICY = "codecoach_maintenance_read"
_NO_USER = "coalesce(current_setting('codecoach.user_id', true), '') = ''"
_SCOPE = "coalesce(current_setting('codecoach.scope', true), '')"
CONDITION = (
    "user_id = current_setting('codecoach.user_id', true) "
    f"OR ({_NO_USER} AND {_SCOPE} NOT IN ('request', 'worker', 'maintenance'))"
)
MAINTENANCE_CONDITION = f"{_NO_USER} AND {_SCOPE} = 'maintenance'"


def upgrade() -> None:
    op.create_table(
        "lab_reveals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("lab_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lab_reveals_user_problem", "lab_reveals", ["user_id", "problem_id", "created_at"])
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
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(sa.text(f"DROP POLICY IF EXISTS {MAINTENANCE_POLICY} ON {table}"))
            op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY} ON {table}"))
    op.drop_index("ix_lab_reveals_user_problem", table_name="lab_reveals")
    op.drop_table("lab_reveals")
