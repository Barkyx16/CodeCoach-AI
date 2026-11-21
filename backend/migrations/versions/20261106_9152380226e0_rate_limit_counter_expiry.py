"""rate limit counters: expiry, so housekeeping can purge rows no limiter reads again

Revision ID: 9152380226e0
Revises: b2c3d4e5f6a7
Create Date: 2026-11-06

Additive: one nullable column and its index. Rows written before it stay null and are purged by
the next housekeeping run (at worst one window's count is forgotten once). Downgrade drops both.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9152380226e0"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rate_limit_counters") as batch:
        batch.add_column(sa.Column("expires_at", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_rate_limit_counters_expires_at"), "rate_limit_counters", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rate_limit_counters_expires_at"), table_name="rate_limit_counters")
    with op.batch_alter_table("rate_limit_counters") as batch:
        batch.drop_column("expires_at")
