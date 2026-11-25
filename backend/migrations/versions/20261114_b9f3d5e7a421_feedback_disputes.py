"""feedback disputes: when a point was disputed or reinstated, and what plan items were derived from

Revision ID: b9f3d5e7a421
Revises: a8e2c4f6b310
Create Date: 2026-11-14

Volume 12, prompt 7 (docs/DISPUTES.md). Adds `answer_flags.disputed_at` and
`answer_flags.reinstated_at` (nullable: a dispute is an "I disagree" flag not reinstated; flags
saved before this have no recorded date, which is said, not guessed), `plan_items.derived_from`
(nullable JSON: the answers and feedback points an activity was derived from; items saved before
this have none recorded) and `practice_plans.withheld` (nullable JSON: suggestions a version didn't
make because of a dispute, each with its one-line reason). All on tables already under row-level
security. Nothing existing is rewritten; downgrade drops the four columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9f3d5e7a421"
down_revision: str | Sequence[str] | None = "a8e2c4f6b310"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("answer_flags", sa.Column("disputed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("answer_flags", sa.Column("reinstated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plan_items", sa.Column("derived_from", _json(), nullable=True))
    op.add_column("practice_plans", sa.Column("withheld", _json(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("practice_plans") as batch:
        batch.drop_column("withheld")
    with op.batch_alter_table("plan_items") as batch:
        batch.drop_column("derived_from")
    with op.batch_alter_table("answer_flags") as batch:
        batch.drop_column("reinstated_at")
        batch.drop_column("disputed_at")
