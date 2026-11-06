"""interview reflections: private debriefs and chosen next steps

Revision ID: 76e9a3e567dc
Revises: c2cc8ed140c2
Create Date: 2026-11-03 09:02:01.331340

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "76e9a3e567dc"
down_revision: str | Sequence[str] | None = "c2cc8ed140c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "interview_reflections",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("role_title", sa.String(length=120), nullable=False),
        sa.Column("employer", sa.String(length=120), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("event_title", sa.String(length=120), nullable=False),
        sa.Column("event_on", sa.Date(), nullable=True),
        sa.Column(
            "questions",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "topics",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("clear", sa.Text(), nullable=False),
        sa.Column("difficult", sa.Text(), nullable=False),
        sa.Column(
            "observations",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("follow_ups", sa.Text(), nullable=False),
        sa.Column(
            "practice",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "story_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column(
            "outcome_history",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["application_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        op.f("ix_interview_reflections_application_id"),
        "interview_reflections",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interview_reflections_user_id"), "interview_reflections", ["user_id"], unique=False
    )
    op.create_table(
        "reflection_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("ref", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("target", sa.String(length=12), nullable=True),
        sa.Column("applied_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["interview_reflections.event_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "key", name="uq_reflection_action_key"),
    )
    op.create_index(op.f("ix_reflection_actions_event_id"), "reflection_actions", ["event_id"], unique=False)
    op.create_index(op.f("ix_reflection_actions_user_id"), "reflection_actions", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_reflection_actions_user_id"), table_name="reflection_actions")
    op.drop_index(op.f("ix_reflection_actions_event_id"), table_name="reflection_actions")
    op.drop_table("reflection_actions")
    op.drop_index(op.f("ix_interview_reflections_user_id"), table_name="interview_reflections")
    op.drop_index(op.f("ix_interview_reflections_application_id"), table_name="interview_reflections")
    op.drop_table("interview_reflections")
