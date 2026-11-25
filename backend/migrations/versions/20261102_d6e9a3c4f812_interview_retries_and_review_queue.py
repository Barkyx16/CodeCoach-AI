"""interview retries and review queue

New tables only: retries of single interview questions (originals untouched) and questions saved
for spaced review. Everything cascades with the user.

Revision ID: d6e9a3c4f812
Revises: b4d81f2e6a73
Create Date: 2026-11-02 22:51:41.145224

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6e9a3c4f812"
down_revision: str | Sequence[str] | None = "b4d81f2e6a73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_retries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("original_answer_id", sa.String(length=36), nullable=True),
        sa.Column("retry_answer_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["original_answer_id"], ["practice_answers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["retry_answer_id"], ["practice_answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["practice_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_retries_session_id"), "interview_retries", ["session_id"], unique=False
    )
    op.create_index(op.f("ix_interview_retries_user_id"), "interview_retries", ["user_id"], unique=False)
    op.create_table(
        "review_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_score", sa.Integer(), nullable=True),
        sa.Column("reviews", sa.Integer(), nullable=False),
        sa.Column("snoozed", sa.Boolean(), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["practice_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_user_due", "review_items", ["user_id", "due_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_review_user_due", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index(op.f("ix_interview_retries_user_id"), table_name="interview_retries")
    op.drop_index(op.f("ix_interview_retries_session_id"), table_name="interview_retries")
    op.drop_table("interview_retries")
