"""test design runs: learners' cases run against a reference and authored faulty versions

Revision ID: 8e4b1d7c2f60
Revises: 5b7e2c9d4a10
Create Date: 2026-11-09

Volume 10, prompt 4 (docs/TEST_DESIGN.md). `test_design_runs` holds each set of cases a learner
sends: the cases, the exercise version, a status like a submission's (queued, running, done,
not_run without a judge, failed), and the report read off the sandbox's outputs. Queued and
claimed by the judge worker like submissions, so, like `submissions`, it isn't under row-level
security (the worker reads queued runs across learners); every request-side lookup filters by user.
Cascades with the account. The exercises are files (app/seed/testdesign). Downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8e4b1d7c2f60"
down_revision: str | Sequence[str] | None = "5b7e2c9d4a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "test_design_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("exercise_slug", sa.String(length=64), nullable=False),
        sa.Column("exercise_version", sa.Integer(), nullable=False),
        sa.Column("cases", _json(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_detail", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("judge_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report", _json(), nullable=True),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_test_design_client_request"),
    )
    op.create_index("ix_test_design_runs_user_id", "test_design_runs", ["user_id"])
    op.create_index("ix_test_design_user_exercise", "test_design_runs", ["user_id", "exercise_slug"])
    op.create_index("ix_test_design_status", "test_design_runs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_test_design_status", table_name="test_design_runs")
    op.drop_index("ix_test_design_user_exercise", table_name="test_design_runs")
    op.drop_index("ix_test_design_runs_user_id", table_name="test_design_runs")
    op.drop_table("test_design_runs")
