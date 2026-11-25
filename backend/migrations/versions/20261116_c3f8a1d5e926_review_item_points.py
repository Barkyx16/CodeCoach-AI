"""review items saved for several points

Revision ID: c3f8a1d5e926
Revises: b2e6d4a8c157
Create Date: 2026-11-16

Volume 16, prompt 5 (docs/DISPUTES.md, "The review queue"). Adds `review_items.points`: every
feedback point an item was saved for, in the order added. Only the shape changes, not the meaning:
an item from before keeps its one point in `criterion` and `points` stays null, which reads as that
one point (or the whole answer, with none). No row is rewritten. The table is already owner-only
under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3f8a1d5e926"
down_revision: str | Sequence[str] | None = "b2e6d4a8c157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_items",
        sa.Column("points", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_items", "points")
