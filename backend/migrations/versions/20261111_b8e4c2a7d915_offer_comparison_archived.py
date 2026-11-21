"""offer comparison archived: a comparison can leave the active list without being deleted

Revision ID: b8e4c2a7d915
Revises: a5d3e9c1b7f2
Create Date: 2026-11-11

Volume 11, prompt 4 (docs/ARCHIVE.md). Adds `offer_comparisons.archived` (not null, server default
false), the same presentation flag notes, stories, applications and target roles already have:
an archived comparison leaves the default list and "Continue your work", keeps its id, revision,
document and links, and comes back unchanged when restored. Existing rows stay active. The table's
row-level security policies cover the new column as they cover the rest. Downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e4c2a7d915"
down_revision: str | Sequence[str] | None = "a5d3e9c1b7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "offer_comparisons",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("offer_comparisons", "archived")
