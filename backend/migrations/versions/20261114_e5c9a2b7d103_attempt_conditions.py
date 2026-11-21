"""attempt conditions: the problem version a hint and a submission were made against

Revision ID: e5c9a2b7d103
Revises: d4a8b6c1f2e3
Create Date: 2026-11-14

Volume 12, prompt 3 (docs/ATTEMPT_CONDITIONS.md). Adds `ai_interactions.content_version` and
`submissions.content_version` (both nullable integers): the coding problem's version when a hint
was shown and when an attempt was made, so an attempt's conditions come only from help for the
same problem and version. Rows from before stay null (their version isn't known and is never made
up). Both tables' row-level security policies cover the new columns. Downgrade drops them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5c9a2b7d103"
down_revision: str | Sequence[str] | None = "d4a8b6c1f2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_interactions", sa.Column("content_version", sa.Integer(), nullable=True))
    op.add_column("submissions", sa.Column("content_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_column("content_version")
    with op.batch_alter_table("ai_interactions") as batch:
        batch.drop_column("content_version")
