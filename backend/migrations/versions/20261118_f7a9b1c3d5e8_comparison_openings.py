"""comparison openings: a sample-answer lesson's explanation, opened before a reading

Revision ID: f7a9b1c3d5e8
Revises: e6f8a0b2c4d7
Create Date: 2026-11-18

Volume 19, prompt 5 (docs/ATTEMPT_CONDITIONS.md, docs/COMPARE_ANSWERS.md). Adds
`comparison_openings`: the first time a signed-in learner opened a sample-answer lesson's explanation
before sending a reading, at that version of the lesson, with the request key it was sent with. Every
reading sent after it at that version says "Solution revealed" with this time. Owner-only under
row-level security, deleted with the account. Nothing earlier is filled in: before this, only the
reading recorded that the explanation had been opened, and those readings keep their words.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a9b1c3d5e8"
down_revision: str | Sequence[str] | None = "e6f8a0b2c4d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("comparison_openings",)
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
        "comparison_openings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("lesson_id", sa.String(length=64), nullable=False),
        sa.Column("lesson_version", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "lesson_id", "lesson_version", name="uq_comparison_opening"),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_comparison_opening_request"),
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
    op.drop_table("comparison_openings")
