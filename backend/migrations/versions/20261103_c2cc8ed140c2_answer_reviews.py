"""answer reviews: self-reviews, flags and later evaluations

Revision ID: c2cc8ed140c2
Revises: 99be925bf8d1
Create Date: 2026-11-03 08:41:58.902447

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2cc8ed140c2"
down_revision: str | Sequence[str] | None = "99be925bf8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "answer_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("rubric_version", sa.String(length=16), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "feedback",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["practice_answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_answer_evaluations_answer_id"), "answer_evaluations", ["answer_id"], unique=False
    )
    op.create_index(op.f("ix_answer_evaluations_user_id"), "answer_evaluations", ["user_id"], unique=False)
    op.create_table(
        "answer_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("criterion", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["practice_answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_id", "criterion", name="uq_answer_flag"),
    )
    op.create_index(op.f("ix_answer_flags_answer_id"), "answer_flags", ["answer_id"], unique=False)
    op.create_index(op.f("ix_answer_flags_user_id"), "answer_flags", ["user_id"], unique=False)
    op.create_table(
        "answer_self_reviews",
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("went_well", sa.Text(), nullable=False),
        sa.Column("improve", sa.Text(), nullable=False),
        sa.Column(
            "ratings",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.Column("before_feedback", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["practice_answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("answer_id"),
    )
    op.create_index(op.f("ix_answer_self_reviews_user_id"), "answer_self_reviews", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_answer_self_reviews_user_id"), table_name="answer_self_reviews")
    op.drop_table("answer_self_reviews")
    op.drop_index(op.f("ix_answer_flags_user_id"), table_name="answer_flags")
    op.drop_index(op.f("ix_answer_flags_answer_id"), table_name="answer_flags")
    op.drop_table("answer_flags")
    op.drop_index(op.f("ix_answer_evaluations_user_id"), table_name="answer_evaluations")
    op.drop_index(op.f("ix_answer_evaluations_answer_id"), table_name="answer_evaluations")
    op.drop_table("answer_evaluations")
