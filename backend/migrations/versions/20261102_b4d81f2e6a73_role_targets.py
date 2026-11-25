"""role targets

New tables only: saved target roles (with the pasted job description), their reviewable
requirements, and the learner's own experience examples. Everything cascades with the user.

Revision ID: b4d81f2e6a73
Revises: 9c2a7e4b1f55
Create Date: 2026-11-02 22:27:38.630506

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4d81f2e6a73"
down_revision: str | Sequence[str] | None = "9c2a7e4b1f55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_targets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("employer", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("interview_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("extractor", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_role_targets_user_id"), "role_targets", ["user_id"], unique=False)
    op.create_table(
        "experience_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column(
            "requirement_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_id"], ["role_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_experience_entries_target_id"), "experience_entries", ["target_id"], unique=False
    )
    op.create_index(op.f("ix_experience_entries_user_id"), "experience_entries", ["user_id"], unique=False)
    op.create_table(
        "target_requirements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("origin", sa.String(length=12), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column(
            "skills",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("removed", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["target_id"], ["role_targets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_target_requirements_target_id"), "target_requirements", ["target_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_target_requirements_target_id"), table_name="target_requirements")
    op.drop_table("target_requirements")
    op.drop_index(op.f("ix_experience_entries_user_id"), table_name="experience_entries")
    op.drop_index(op.f("ix_experience_entries_target_id"), table_name="experience_entries")
    op.drop_table("experience_entries")
    op.drop_index(op.f("ix_role_targets_user_id"), table_name="role_targets")
    op.drop_table("role_targets")
