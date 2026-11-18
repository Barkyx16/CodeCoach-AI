"""review items keep when they were removed

Revision ID: d5e7a9c1f3b4
Revises: c3d5f7a9e182
Create Date: 2026-11-18

Volume 19, prompt 2 (docs/DISPUTES.md, "Removed recently"). Adds `review_items.removed_at`: when a
question was taken out of the review queue, so the queue can list recent removals to put back after a
reload. Every item removed before this stays null ("date not recorded"); no row is rewritten. The
table is already owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e7a9c1f3b4"
down_revision: str | Sequence[str] | None = "c3d5f7a9e182"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_items", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("review_items") as batch:
        batch.drop_column("removed_at")
