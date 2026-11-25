"""question round interviews

Mock interviews made of a career's written questions share the coding interview tables:
practice_sessions gains the career and the picked questions; interview_turns gains the question a
turn asks/answers, the graded answer it saved, and per-turn metadata (typed/voice, skipped,
simulated engagement). Existing rows are untouched: every new column is nullable.

Revision ID: 4f1d2c8e9a10
Revises: bacfc26de5d3
Create Date: 2026-11-02 20:54:08.155574

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4f1d2c8e9a10"
down_revision: str | Sequence[str] | None = "bacfc26de5d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
FK = "fk_interview_turns_answer_id_practice_answers"


def upgrade() -> None:
    with op.batch_alter_table("interview_turns") as batch:
        batch.add_column(sa.Column("question_index", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("answer_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("meta", JSON, nullable=True))
        batch.alter_column("phase", existing_type=sa.VARCHAR(length=32), nullable=True)
        batch.create_foreign_key(FK, "practice_answers", ["answer_id"], ["id"], ondelete="SET NULL")
    with op.batch_alter_table("practice_sessions") as batch:
        batch.add_column(sa.Column("track", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("plan", JSON, nullable=True))


def downgrade() -> None:
    # Question rounds can't exist in the old schema (their turns have no phase). Their graded
    # answers stay in practice_answers; only the round sessions and their turns are removed.
    op.execute("DELETE FROM interview_turns WHERE phase IS NULL")
    op.execute("DELETE FROM practice_sessions WHERE mode = 'questions'")
    with op.batch_alter_table("practice_sessions") as batch:
        batch.drop_column("plan")
        batch.drop_column("track")
    with op.batch_alter_table("interview_turns") as batch:
        batch.drop_constraint(FK, type_="foreignkey")
        batch.alter_column("phase", existing_type=sa.VARCHAR(length=32), nullable=False)
        batch.drop_column("meta")
        batch.drop_column("answer_id")
        batch.drop_column("question_index")
