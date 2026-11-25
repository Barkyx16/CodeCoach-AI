"""comparison openings say how the explanation was seen: opened, or shown with a result

Revision ID: a8c0e2f4b6d9
Revises: f7a9b1c3d5e8
Create Date: 2026-11-18

Volume 20, prompt 3 (docs/ATTEMPT_CONDITIONS.md, docs/COMPARE_ANSWERS.md). Adds
`comparison_openings.source`: "opened" (the learner opened the explanation on its own, as every row
before this was) or "with_result" (it was shown with a reading's own result, at that reading's time).
Every existing row is "opened" by the server default; no row is rewritten otherwise. The table is
already owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c0e2f4b6d9"
down_revision: str | Sequence[str] | None = "f7a9b1c3d5e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "comparison_openings",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="opened"),
    )


def downgrade() -> None:
    with op.batch_alter_table("comparison_openings") as batch:
        batch.drop_column("source")
