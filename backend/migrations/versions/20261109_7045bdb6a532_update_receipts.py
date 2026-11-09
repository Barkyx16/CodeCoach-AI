"""update receipts: evidence that a keyed update was accepted

Revision ID: 7045bdb6a532
Revises: 06088140741a
Create Date: 2026-11-09

A revision-checked save (a story, note, kit, whiteboard draft or reflection) whose reply was lost
used to meet its own new revision when the page sent it again, and read as "changed elsewhere"
(Volume 8, prompt 3). `update_receipts` records, in the same transaction as the update, which
entity it changed, the revision it started from and the one it produced, and a digest of the
update (services/request_keys.py), under the request key the page sent. A retry finds it and is
told its save went through. No content is kept. Rows are purged after UPDATE_RECEIPT_DAYS by the
housekeeping job; an expired receipt means a retry is treated as a new save.

Not under row-level security (db/rls.py says why: no content, and housekeeping purges it across
learners from the worker scope); every lookup filters by user. Downgrade drops the table (retries of
lost updates go back to reading as conflicts).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7045bdb6a532"
down_revision: str | Sequence[str] | None = "06088140741a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "update_receipts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("entity", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("accepted_revision", sa.Integer(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_update_receipt_request"),
    )
    op.create_index("ix_update_receipts_user_id", "update_receipts", ["user_id"])
    op.create_index("ix_update_receipt_created", "update_receipts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_update_receipt_created", table_name="update_receipts")
    op.drop_index("ix_update_receipts_user_id", table_name="update_receipts")
    op.drop_table("update_receipts")
