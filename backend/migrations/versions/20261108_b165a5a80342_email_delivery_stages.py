"""email jobs: honest delivery stages and a Message-ID per job

Revision ID: b165a5a80342
Revises: b7abe5833c3c
Create Date: 2026-11-08

"sent" becomes "accepted": all an SMTP send proves is that the mail server took the message, not
that it was delivered. A new "rejected" status (a permanent refusal) needs no schema change. The
message_id column records the Message-ID each job's email went out with, so a provider's logs
and events can be matched to the job. Additive; downgrade restores "sent" and drops the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b165a5a80342"
down_revision: str | Sequence[str] | None = "b7abe5833c3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("email_jobs") as batch:
        batch.add_column(sa.Column("message_id", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_email_jobs_message_id"), "email_jobs", ["message_id"], unique=False)
    op.execute(sa.text("UPDATE email_jobs SET status = 'accepted' WHERE status = 'sent'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE email_jobs SET status = 'sent' WHERE status = 'accepted'"))
    op.execute(sa.text("UPDATE email_jobs SET status = 'failed' WHERE status = 'rejected'"))
    op.drop_index(op.f("ix_email_jobs_message_id"), table_name="email_jobs")
    with op.batch_alter_table("email_jobs") as batch:
        batch.drop_column("message_id")
