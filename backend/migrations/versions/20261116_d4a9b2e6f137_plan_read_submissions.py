"""plan versions record the submissions an update read

Revision ID: d4a9b2e6f137
Revises: c3f8a1d5e926
Create Date: 2026-11-16

Volume 16, prompt 7 (docs/PLAN_UPDATES.md). Adds `practice_plans.read_submissions`: the judged
submissions, by id, that the "Update my plan" which made a version read as new evidence. Every
version from before stays null, which reads as it did ("not made by an update that recorded this");
no row is rewritten. The table is already owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4a9b2e6f137"
down_revision: str | Sequence[str] | None = "c3f8a1d5e926"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_plans",
        sa.Column(
            "read_submissions", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("practice_plans", "read_submissions")
