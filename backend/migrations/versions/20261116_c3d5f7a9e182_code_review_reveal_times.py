"""code reviews keep when the authored review was first shown

Revision ID: c3d5f7a9e182
Revises: a8c2e4f6b195
Create Date: 2026-11-16

Volume 18, prompt 9 (docs/ATTEMPT_CONDITIONS.md, "Code reviews, sample-answer comparisons and work
samples"). Adds `code_review_drafts.revealed_at` (when the authored review was first shown at the
draft's revealed version) and `code_review_attempts.revealed_at` (that time, copied onto a review
written after it). A review's "Solution revealed" then carries when it was shown, not the review's
own time. Every row from before stays null (the time was never kept); no row is rewritten. Both
tables are already owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d5f7a9e182"
down_revision: str | Sequence[str] | None = "a8c2e4f6b195"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("code_review_drafts", sa.Column("revealed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("code_review_attempts", sa.Column("revealed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("code_review_attempts") as batch:
        batch.drop_column("revealed_at")
    with op.batch_alter_table("code_review_drafts") as batch:
        batch.drop_column("revealed_at")
