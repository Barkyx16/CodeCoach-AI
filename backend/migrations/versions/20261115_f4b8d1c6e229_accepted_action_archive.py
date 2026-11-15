"""accepted action archive: an accepted improvement can be put down and picked up again

Revision ID: f4b8d1c6e229
Revises: e3a7c9b5d118
Create Date: 2026-11-15

Volume 14, prompt 5 (docs/ACCEPTED_ACTIONS.md, "Archive and delete"). An accepted improvement
can be archived: kept, with its occurrences and marks of done, but off the plan, the schedule and
Today until it's unarchived. `accepted_actions.archived_at` records when (null: not archived).
A new nullable column: every existing action is unarchived, as before. Downgrade drops it, which
unarchives every action (nothing else is lost).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4b8d1c6e229"
down_revision: str | Sequence[str] | None = "e3a7c9b5d118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("accepted_actions") as batch:
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accepted_actions") as batch:
        batch.drop_column("archived_at")
