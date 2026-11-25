"""bookmarks and collections

New tables only: private bookmarks, practice collections and their ordered items. Everything
cascades with the user.

Revision ID: e1a7c5b9d204
Revises: d6e9a3c4f812
Create Date: 2026-11-02 23:27:37.268514

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a7c5b9d204"
down_revision: str | Sequence[str] | None = "d6e9a3c4f812"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("item_type", sa.String(length=12), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_type", "track", "ref_id", name="uq_bookmark"),
    )
    op.create_index(op.f("ix_bookmarks_user_id"), "bookmarks", ["user_id"], unique=False)
    op.create_table(
        "practice_collections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("queue_position", sa.Integer(), nullable=False),
        sa.Column("queue_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_practice_collections_user_id"), "practice_collections", ["user_id"], unique=False
    )
    op.create_table(
        "collection_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("collection_id", sa.String(length=36), nullable=False),
        sa.Column("item_type", sa.String(length=12), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queue_done_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["collection_id"], ["practice_collections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "item_type", "track", "ref_id", name="uq_collection_item"),
    )
    op.create_index(
        op.f("ix_collection_items_collection_id"), "collection_items", ["collection_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_collection_items_collection_id"), table_name="collection_items")
    op.drop_table("collection_items")
    op.drop_index(op.f("ix_practice_collections_user_id"), table_name="practice_collections")
    op.drop_table("practice_collections")
    op.drop_index(op.f("ix_bookmarks_user_id"), table_name="bookmarks")
    op.drop_table("bookmarks")
