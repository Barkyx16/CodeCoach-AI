"""drill attempts: communication drill history

Revision ID: 99be925bf8d1
Revises: 1bbae318ce1d
Create Date: 2026-11-03 08:22:01.943108

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "99be925bf8d1"
down_revision: str | Sequence[str] | None = "1bbae318ce1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "drill_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("drill_id", sa.String(length=32), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("spoken_seconds", sa.Integer(), nullable=True),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column(
            "feedback",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_drill_client_request"),
    )
    op.create_index(op.f("ix_drill_attempts_user_id"), "drill_attempts", ["user_id"], unique=False)
    op.create_index("ix_drill_user_drill", "drill_attempts", ["user_id", "drill_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_drill_user_drill", table_name="drill_attempts")
    op.drop_index(op.f("ix_drill_attempts_user_id"), table_name="drill_attempts")
    op.drop_table("drill_attempts")
