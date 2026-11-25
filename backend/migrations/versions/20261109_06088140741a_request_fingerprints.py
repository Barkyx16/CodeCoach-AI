"""Request keys: what each keyed create stood for

Revision ID: 06088140741a
Revises: 9a0b1c2d3e4f
Create Date: 2026-11-09

A request key used to be checked only against part of its request, or not at all, so the same key
sent again with a different input got the old result back as if it were the new one (Volume 8,
prompt 2): a hint or review with other code or another submission; a story, application, event
or schedule entry with other content. `request_fingerprint` records, on the server, a digest of
the validated input the create stood for (services/request_keys.py); a key sent again with a
different input is refused (409 `idempotency_key_reused`). Stories, applications, events and
schedule entries can be edited later, which is why the create's input is kept rather than
compared with the record as it is now.

Nullable, no backfill: rows made before this keep NULL and are matched as before. No data
changes. Downgrade drops the columns (keys keep working, checked as before).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "06088140741a"
down_revision: str | Sequence[str] | None = "9a0b1c2d3e4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("ai_interactions", "experience_entries", "applications", "application_events", "schedule_entries")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("request_fingerprint", sa.String(length=80), nullable=True))


def downgrade() -> None:
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("request_fingerprint")
