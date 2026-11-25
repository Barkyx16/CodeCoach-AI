"""submissions: the trace id of the request that queued each one

Revision ID: b7c1d2e3f4a5
Revises: 9fa5ab598fa5
Create Date: 2026-11-03 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "9fa5ab598fa5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Nullable, no default: existing rows simply have no trace."""
    with op.batch_alter_table("submissions") as batch:
        batch.add_column(sa.Column("trace_id", sa.String(length=32), nullable=True))


def downgrade() -> None:
    """Downgrade schema. Drops only the trace id; no submission data is lost."""
    with op.batch_alter_table("submissions") as batch:
        batch.drop_column("trace_id")
