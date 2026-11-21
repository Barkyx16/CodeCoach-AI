"""follow-up answers: an answer to a reviewed follow-up question names the answer it follows

Revision ID: f7d1b3e5a209
Revises: e5c9a2b7d103
Create Date: 2026-11-14

Volume 12, prompt 4 (docs/FOLLOW_UPS.md). Adds `practice_answers.follows_up_answer_id` (nullable,
indexed, ON DELETE SET NULL): the learner's own earlier answer to the related question that this
answer was offered after. Both answers keep their own record and score. Existing answers stay
unlinked; nothing is inferred for them. The table's row-level security covers the column.
Downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7d1b3e5a209"
down_revision: str | Sequence[str] | None = "e5c9a2b7d103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("practice_answers") as batch:
        batch.add_column(sa.Column("follows_up_answer_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_practice_answers_follows_up_answer_id", ["follows_up_answer_id"])
        batch.create_foreign_key(
            "fk_answer_follows_up", "practice_answers", ["follows_up_answer_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("practice_answers") as batch:
        batch.drop_constraint("fk_answer_follows_up", type_="foreignkey")
        batch.drop_index("ix_practice_answers_follows_up_answer_id")
        batch.drop_column("follows_up_answer_id")
