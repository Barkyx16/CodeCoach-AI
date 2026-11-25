"""schedule entries: an optional anchor, for interview preparation kept relative to its interview

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Additive and nullable: every existing entry stays a fixed time (NULL); no
    binding is guessed for old entries and no row is rewritten."""
    with op.batch_alter_table("schedule_entries") as batch:
        batch.add_column(sa.Column("anchor_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema. Drops the anchors: entries that were kept relative to their interview become
    fixed times (their times stay exactly as they are)."""
    with op.batch_alter_table("schedule_entries") as batch:
        batch.drop_column("anchor_at")
