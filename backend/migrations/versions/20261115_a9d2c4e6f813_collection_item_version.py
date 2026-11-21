"""collection item version: a collection remembers which version of each item it holds

Revision ID: a9d2c4e6f813
Revises: f4b8d1c6e229
Create Date: 2026-11-15

Volume 14, prompt 7 (docs/STORY_FRESHNESS.md, "Saved items and collections"). A saved question or
coding problem says when its source has a newer version that matters since it was saved, by the
same rule as notes. Bookmarks already record `content_version` (questions only, until now);
`collection_items.content_version` records the version of the question or problem when it was
added (null: added before versions were recorded, read as "not known", never as up to date).
A new nullable column: every existing item reads "not known". Downgrade drops it; the reviews
recorded in source_reviews stay, and are read again if the column comes back.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9d2c4e6f813"
down_revision: str | Sequence[str] | None = "f4b8d1c6e229"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("collection_items") as batch:
        batch.add_column(sa.Column("content_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("collection_items") as batch:
        batch.drop_column("content_version")
