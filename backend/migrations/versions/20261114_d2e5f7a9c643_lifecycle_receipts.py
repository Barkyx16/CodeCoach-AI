"""lifecycle receipts: what a delete or an archive did, so a retry reports it instead of acting twice

Revision ID: d2e5f7a9c643
Revises: c1d4e6a8b532
Create Date: 2026-11-14

Volume 12, prompt 9 (docs/LIFECYCLE.md). Adds `lifecycle_receipts`: one row per keyed lifecycle
action (deleting an application, archiving a note) with what it did by kind and id (no titles or
text), so the same request sent again after a lost reply is answered with the earlier outcome; and
the create key of each deleted application, so a late retry of that create doesn't make it again.
Deleted with the account, purged by housekeeping after a week. Outside row-level security, like
`update_receipts`: no content, purged across learners by housekeeping, and every lookup filters by
user. Nothing existing changes; downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e5f7a9c643"
down_revision: str | Sequence[str] | None = "c1d4e6a8b532"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "lifecycle_receipts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("client_request_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("impact", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_lifecycle_receipt"),
    )
    op.create_index("ix_lifecycle_receipts_user_id", "lifecycle_receipts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_lifecycle_receipts_user_id", table_name="lifecycle_receipts")
    op.drop_table("lifecycle_receipts")
