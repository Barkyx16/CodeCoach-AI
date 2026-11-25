"""create intents: which account a browser's guest start or registration made

Revision ID: fa8c2d7ff836
Revises: 59c06366e6cf
Create Date: 2026-11-09

A guest start or registration whose reply was lost, sent again, used to make a second guest or
answer "email taken" for the account it had just made (Volume 8, prompt 6). Before such a request
the browser now gets an anchor (an HttpOnly, SameSite=Strict cookie); `create_intents` stores its
hash with the account the request made, in the same transaction, so the same browser's retry
finds it (a registration only with the right password too). Kept an hour, purged daily, deleted on
a deliberate sign-out (or sign-out everywhere). Outside row-level security, like the sign-in tokens: it's looked up before
the user is known. Downgrade drops the table (retries go back to making a new guest).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fa8c2d7ff836"
down_revision: str | Sequence[str] | None = "59c06366e6cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "create_intents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("anchor_hash", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("anchor_hash", "kind", name="uq_create_intent_anchor_kind"),
    )
    op.create_index("ix_create_intents_user_id", "create_intents", ["user_id"])
    op.create_index("ix_create_intents_created_at", "create_intents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_create_intents_created_at", table_name="create_intents")
    op.drop_index("ix_create_intents_user_id", table_name="create_intents")
    op.drop_table("create_intents")
