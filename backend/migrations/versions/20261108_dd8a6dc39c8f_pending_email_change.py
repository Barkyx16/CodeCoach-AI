"""users: a pending email change, confirmed by the new address before it takes effect

Revision ID: dd8a6dc39c8f
Revises: b165a5a80342
Create Date: 2026-11-08

Additive: two nullable columns. Until the new address confirms the code sent to it, the account
keeps its current address for sign-in and recovery. Downgrade drops both (pending changes are
forgotten; nobody's address changes).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dd8a6dc39c8f"
down_revision: str | Sequence[str] | None = "b165a5a80342"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("pending_email", sa.String(length=320), nullable=True))
        batch.add_column(sa.Column("pending_email_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("pending_email_at")
        batch.drop_column("pending_email")
