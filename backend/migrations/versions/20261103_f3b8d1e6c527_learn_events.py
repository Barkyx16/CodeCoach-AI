"""learn events

One new table: per-user progress events for Learn units (started, read, check attempted, check
passed, practiced), each on a specific unit version. Cascades with the user.

Revision ID: f3b8d1e6c527
Revises: e1a7c5b9d204
Create Date: 2026-11-03 00:01:18.012686

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3b8d1e6c527"
down_revision: str | Sequence[str] | None = "e1a7c5b9d204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learn_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("unit_id", sa.String(length=64), nullable=False),
        sa.Column("unit_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "detail",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_learn_event_dedupe"),
    )
    op.create_index(op.f("ix_learn_events_unit_id"), "learn_events", ["unit_id"], unique=False)
    op.create_index(op.f("ix_learn_events_user_id"), "learn_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learn_events_user_id"), table_name="learn_events")
    op.drop_index(op.f("ix_learn_events_unit_id"), table_name="learn_events")
    op.drop_table("learn_events")
