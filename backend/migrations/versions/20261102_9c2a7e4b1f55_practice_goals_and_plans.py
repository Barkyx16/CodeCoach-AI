"""practice goals and plans

New tables only (goals per user and career, versioned plans and their items); existing data is
untouched. Everything cascades with the user, so account deletion removes it.

Revision ID: 9c2a7e4b1f55
Revises: 7b3e5a1c2d40
Create Date: 2026-11-02 22:03:54.348239

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9c2a7e4b1f55"
down_revision: str | Sequence[str] | None = "7b3e5a1c2d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practice_goals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("specialty", sa.String(length=120), nullable=True),
        sa.Column("experience", sa.String(length=16), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("weekly_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "focus_areas",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "formats",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("setup_skipped", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "track", name="uq_goal_user_track"),
    )
    op.create_index(op.f("ix_practice_goals_user_id"), "practice_goals", ["user_id"], unique=False)
    op.create_table(
        "practice_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "changes",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "track", "version", name="uq_plan_version"),
    )
    op.create_index(op.f("ix_practice_plans_user_id"), "practice_plans", ["user_id"], unique=False)
    op.create_table(
        "plan_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("skill", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("completion", sa.Text(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column(
            "target",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "evidence",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["practice_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plan_items_plan_id"), "plan_items", ["plan_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_items_plan_id"), table_name="plan_items")
    op.drop_table("plan_items")
    op.drop_index(op.f("ix_practice_plans_user_id"), table_name="practice_plans")
    op.drop_table("practice_plans")
    op.drop_index(op.f("ix_practice_goals_user_id"), table_name="practice_goals")
    op.drop_table("practice_goals")
