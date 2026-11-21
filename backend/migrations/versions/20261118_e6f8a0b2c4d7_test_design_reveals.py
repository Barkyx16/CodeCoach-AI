"""test design reveals: an exercise's faulty versions, shown because the learner asked

Revision ID: e6f8a0b2c4d7
Revises: d5e7a9c1f3b4
Create Date: 2026-11-18

Volume 19, prompt 3 (docs/ATTEMPT_CONDITIONS.md, docs/TEST_DESIGN.md). Adds `test_design_reveals`:
the first time a learner had a test-design exercise's faulty versions shown, at that version of the
exercise. Every run after it at that version says "Solution revealed", with this time. Owner-only
under row-level security, deleted with the account. Nothing earlier is filled in: before this,
showing them was recorded nowhere, and runs from then say so.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f8a0b2c4d7"
down_revision: str | Sequence[str] | None = "d5e7a9c1f3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("test_design_reveals",)
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
        "test_design_reveals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("exercise_slug", sa.String(length=64), nullable=False),
        sa.Column("exercise_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "exercise_slug", "exercise_version", name="uq_test_design_reveal"),
    )
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
    op.drop_table("test_design_reveals")
