"""email jobs: a durable outbox for account emails (retried, never lost on restart)

Revision ID: b7abe5833c3c
Revises: 248721f0fcb1
Create Date: 2026-11-06

Additive: one new table. Holds what to send (kind, account, addresses), never links or codes.
Downgrade drops it (pending emails in it are lost; they'd be resent on request).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7abe5833c3c"
down_revision: str | Sequence[str] | None = "248721f0fcb1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_jobs_due", "email_jobs", ["status", "next_attempt_at"], unique=False)
    op.create_index(op.f("ix_email_jobs_user_id"), "email_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_jobs_user_id"), table_name="email_jobs")
    op.drop_index("ix_email_jobs_due", table_name="email_jobs")
    op.drop_table("email_jobs")
