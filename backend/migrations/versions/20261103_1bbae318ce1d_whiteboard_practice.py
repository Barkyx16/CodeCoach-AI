"""whiteboard practice: drafts and frozen attempts

Revision ID: 1bbae318ce1d
Revises: 5f47fa286244
Create Date: 2026-11-03 07:58:25.965048

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1bbae318ce1d"
down_revision: str | Sequence[str] | None = "5f47fa286244"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "whiteboard_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("prompt_id", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column(
            "diagram",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("digest", sa.String(length=32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "feedback",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_whiteboard_attempts_user_id"), "whiteboard_attempts", ["user_id"], unique=False)
    op.create_index(
        "ix_whiteboard_user_prompt", "whiteboard_attempts", ["user_id", "prompt_id"], unique=False
    )
    op.create_table(
        "whiteboard_drafts",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("prompt_id", sa.String(length=64), nullable=False),
        sa.Column(
            "diagram",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "prompt_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("whiteboard_drafts")
    op.drop_index("ix_whiteboard_user_prompt", table_name="whiteboard_attempts")
    op.drop_index(op.f("ix_whiteboard_attempts_user_id"), table_name="whiteboard_attempts")
    op.drop_table("whiteboard_attempts")
