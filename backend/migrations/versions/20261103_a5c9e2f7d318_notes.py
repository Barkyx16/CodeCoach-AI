"""notes

One new table: private notebook entries (source reference and snapshot, tags, pin/archive,
a revision counter for conflict detection, and a short undo window). Cascades with the user.

Revision ID: a5c9e2f7d318
Revises: f3b8d1e6c527
Create Date: 2026-11-03 00:26:16.285576

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a5c9e2f7d318"
down_revision: str | Sequence[str] | None = "f3b8d1e6c527"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reflection", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=20), nullable=True),
        sa.Column("source_id", sa.String(length=160), nullable=True),
        sa.Column("source_track", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("source_title", sa.String(length=300), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("excerpt_kind", sa.String(length=8), nullable=True),
        sa.Column(
            "key_points",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notes_user_id"), "notes", ["user_id"], unique=False)
    op.create_index("ix_notes_user_updated", "notes", ["user_id", "updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notes_user_updated", table_name="notes")
    op.drop_index(op.f("ix_notes_user_id"), table_name="notes")
    op.drop_table("notes")
