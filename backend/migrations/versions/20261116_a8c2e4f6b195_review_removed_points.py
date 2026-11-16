"""review items keep the points taken off them, with when

Revision ID: a8c2e4f6b195
Revises: f7a3c5e9b264
Create Date: 2026-11-16

Volume 17, prompt 8 (docs/DISPUTES.md, "Removing a point"). Adds `review_items.removed_points`:
each point taken off an item, with when, so the queue can say why a disputed score on it counts
again. Every item from before stays null (no point was ever recorded as removed); no row is
rewritten. The table is already owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8c2e4f6b195"
down_revision: str | Sequence[str] | None = "f7a3c5e9b264"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_items",
        sa.Column("removed_points", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_items", "removed_points")
