"""plan versions record the lesson checks an update read

Revision ID: f7a3c5e9b264
Revises: e5b1c7d9a248
Create Date: 2026-11-16

Volume 17, prompt 3 (docs/PLAN_UPDATES.md). Adds `practice_plans.read_lessons`: the lesson checks,
by unit and version, that the "Update my plan" which made a version read as new evidence. Every
version from before stays null, which reads as it did; no row is rewritten. The table is already
owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7a3c5e9b264"
down_revision: str | Sequence[str] | None = "e5b1c7d9a248"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_plans",
        sa.Column("read_lessons", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_plans", "read_lessons")
