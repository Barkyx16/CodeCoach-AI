"""submission follow-up: a submission made from a reviewed follow-up offer names the one it followed

Revision ID: b7e1f3a5c924
Revises: a9d2c4e6f813
Create Date: 2026-11-15

Volume 14, prompt 10 (docs/FOLLOW_UPS.md, "Coding problems"). After a judged submission of a
problem passes, a reviewed related problem may be offered; a submission made from that offer
records the passed submission it followed (`submissions.follows_up_submission_id`, set once when
it's made, only to the learner's own passed submission of a problem with a reviewed pair to this
one). Its verdict stays its own: nothing combines the two. A new nullable column: every existing
submission follows up nothing. If the followed submission goes (with its account), the link is
cleared. Downgrade drops the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e1f3a5c924"
down_revision: str | Sequence[str] | None = "a9d2c4e6f813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.add_column(sa.Column("follows_up_submission_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_submissions_follows_up", "submissions", ["follows_up_submission_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_submissions_follows_up_submission_id", ["follows_up_submission_id"])


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_index("ix_submissions_follows_up_submission_id")
        batch.drop_constraint("fk_submissions_follows_up", type_="foreignkey")
        batch.drop_column("follows_up_submission_id")
