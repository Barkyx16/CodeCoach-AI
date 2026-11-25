"""listed names: a learner's private list of names replaced wherever text leaves the app

Revision ID: e4c8a2d6f913
Revises: c9a4e2f6d871
Create Date: 2026-11-15

Volume 15, prompt 7 (docs/PRIVACY.md, "Names you listed"). Adds `listed_names`: one row per name a
learner doesn't want anywhere outside the app (an interviewer, a manager, a patient's family). The
practice packet, a shared answer and every coach-context preview replace them; the learner's own
copy never changes. Owner-only under row-level security, deleted with the account, unique per
account and name (any letter case).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4c8a2d6f913"
down_revision: str | Sequence[str] | None = "c9a4e2f6d871"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("listed_names",)
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
        "listed_names",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("folded", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "folded", name="uq_listed_name"),
    )
    op.create_index("ix_listed_names_user_id", "listed_names", ["user_id"])
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
    op.drop_index("ix_listed_names_user_id", table_name="listed_names")
    op.drop_table("listed_names")
