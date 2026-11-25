"""progress event dedupe key

An "opened" event is recorded at most once per user, problem and day. That used to be a
check-then-insert, which two concurrent requests could both pass. A nullable key with a unique
index makes it atomic. Existing rows keep a NULL key (NULLs never collide), so recorded history is
unchanged and the upgrade can't fail on old duplicates.

Revision ID: 7b3e5a1c2d40
Revises: 4f1d2c8e9a10
Create Date: 2026-11-02 22:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7b3e5a1c2d40"
down_revision: str | Sequence[str] | None = "4f1d2c8e9a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("progress_events", sa.Column("dedupe_key", sa.String(length=80), nullable=True))
    op.create_index("uq_progress_user_dedupe", "progress_events", ["user_id", "dedupe_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_progress_user_dedupe", table_name="progress_events")
    op.drop_column("progress_events", "dedupe_key")
