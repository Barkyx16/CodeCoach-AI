"""offer rehearsals: practising an offer conversation against a fictional fact card

Revision ID: f2c8a6d4b913
Revises: e7b3c1d9a842
Create Date: 2026-11-09

Volume 10, prompt 8 (docs/OFFER_REHEARSAL.md). `offer_rehearsals` holds each rehearsal: a snapshot
of the fictional fact card, the goals the learner wrote, the turns (typed or spoken, and the
counterpart's authored replies), the phase reached and the debrief. Cascades with the account;
under row-level security on PostgreSQL with the policies 7c1d2e3f4a5b installs (app/db/rls.py lists
it under this revision). The cases are code (app/offers). Downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2c8a6d4b913"
down_revision: str | Sequence[str] | None = "e7b3c1d9a842"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("offer_rehearsals",)
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
        "offer_rehearsals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", _json(), nullable=False),
        sa.Column("goals", _json(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("phase", sa.String(length=12), nullable=False),
        sa.Column("turns", _json(), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("debrief", _json(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_offer_rehearsals_user_id", "offer_rehearsals", ["user_id"])
    op.create_index("ix_offer_rehearsal_user_case", "offer_rehearsals", ["user_id", "case_id"])
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
    op.drop_index("ix_offer_rehearsal_user_case", table_name="offer_rehearsals")
    op.drop_index("ix_offer_rehearsals_user_id", table_name="offer_rehearsals")
    op.drop_table("offer_rehearsals")
