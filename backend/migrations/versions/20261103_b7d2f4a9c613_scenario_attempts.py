"""scenario attempts

One new table: learners' runs through branching scenarios (version, mode, current node, the
recorded steps and ending). Cascades with the user.

Revision ID: b7d2f4a9c613
Revises: a5c9e2f7d318
Create Date: 2026-11-03 00:55:55.078903

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7d2f4a9c613"
down_revision: str | Sequence[str] | None = "a5c9e2f7d318"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenario_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("current_node", sa.String(length=64), nullable=False),
        sa.Column(
            "steps",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("ending", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scenario_attempts_scenario_id"), "scenario_attempts", ["scenario_id"], unique=False
    )
    op.create_index(op.f("ix_scenario_attempts_user_id"), "scenario_attempts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scenario_attempts_user_id"), table_name="scenario_attempts")
    op.drop_index(op.f("ix_scenario_attempts_scenario_id"), table_name="scenario_attempts")
    op.drop_table("scenario_attempts")
