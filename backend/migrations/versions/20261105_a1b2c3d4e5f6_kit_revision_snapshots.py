"""interview kits: a revision for conflict-safe saves, and what each save was made against

Revision ID: a1b2c3d4e5f6
Revises: c4d5e6f7a8b9
Create Date: 2026-11-05 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Additive: existing kits get revision 0 and no snapshots (NULL), so nothing is
    claimed about what they were saved against; no row's content is rewritten."""
    with op.batch_alter_table("interview_kits") as batch:
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("event_when", sa.String(length=80), nullable=True))
        batch.add_column(
            sa.Column(
                "story_revisions",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Downgrade schema. Drops the revision and snapshots (that information is lost; every kit's
    content stays). After a downgrade a stale tab can overwrite a newer kit again."""
    with op.batch_alter_table("interview_kits") as batch:
        batch.drop_column("story_revisions")
        batch.drop_column("event_when")
        batch.drop_column("revision")
