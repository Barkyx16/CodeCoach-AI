"""review items saved for one point: a dispute on that point holds the item

Revision ID: f5b9d3e7a1c4
Revises: e4c8a2d6f913
Create Date: 2026-11-15

Volume 15, prompt 9 (docs/DISPUTES.md, "The review queue"). Adds `review_items.criterion`: the one
feedback point an item was saved for (from a summary's improvement), or null for an item saved for
the whole answer, as every item before this was. A dispute on that point counts like a dispute on
the whole feedback, for that item only. The table is already owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5b9d3e7a1c4"
down_revision: str | Sequence[str] | None = "e4c8a2d6f913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_items", sa.Column("criterion", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("review_items", "criterion")
