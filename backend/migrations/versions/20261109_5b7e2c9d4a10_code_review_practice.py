"""code-review practice: the learner's review drafts and the reviews they send

Revision ID: 5b7e2c9d4a10
Revises: 3d1f0c2b9a77
Create Date: 2026-11-09

Volume 10, prompt 3 (docs/CODE_REVIEW_PRACTICE.md). `code_review_drafts` holds a review in
progress per learner and exercise, saved against a revision like the other long-form editors, with
the exercise version its line numbers were written against and whether the authored review has
been seen. `code_review_attempts` holds each review sent for comparison, with a snapshot of the
code and the authored review it was compared with, so a corrected exercise never rewrites it.
Both cascade with the account and are under row-level security on PostgreSQL, with the same
policies 7c1d2e3f4a5b installs (app/db/rls.py lists them under this revision). The exercises
themselves are files (app/seed/reviews), not rows. Downgrade drops both tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5b7e2c9d4a10"
down_revision: str | Sequence[str] | None = "3d1f0c2b9a77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("code_review_attempts", "code_review_drafts")
POLICY = "codecoach_owner_only"
MAINTENANCE_POLICY = "codecoach_maintenance_read"
_NO_USER = "coalesce(current_setting('codecoach.user_id', true), '') = ''"
_SCOPE = "coalesce(current_setting('codecoach.scope', true), '')"
CONDITION = (
    "user_id = current_setting('codecoach.user_id', true) "
    f"OR ({_NO_USER} AND {_SCOPE} NOT IN ('request', 'worker', 'maintenance'))"
)
MAINTENANCE_CONDITION = f"{_NO_USER} AND {_SCOPE} = 'maintenance'"


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _owner() -> sa.Column:
    return sa.Column(
        "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "code_review_drafts",
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("exercise_slug", sa.String(length=64), primary_key=True),
        sa.Column("exercise_version", sa.Integer(), nullable=False),
        sa.Column("findings", _json(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("revealed_version", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "code_review_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _owner(),
        sa.Column("exercise_slug", sa.String(length=64), nullable=False),
        sa.Column("exercise_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", _json(), nullable=False),
        sa.Column("findings", _json(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("feedback", _json(), nullable=False),
        sa.Column("after_reveal", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_code_review_attempts_user_id", "code_review_attempts", ["user_id"])
    op.create_index("ix_code_review_user_exercise", "code_review_attempts", ["user_id", "exercise_slug"])
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"CREATE POLICY {POLICY} ON {table} USING ({CONDITION}) WITH CHECK ({CONDITION})"))
        op.execute(
            sa.text(
                f"CREATE POLICY {MAINTENANCE_POLICY} ON {table} FOR SELECT USING ({MAINTENANCE_CONDITION})"
            )
        )


def downgrade() -> None:
    op.drop_index("ix_code_review_user_exercise", table_name="code_review_attempts")
    op.drop_index("ix_code_review_attempts_user_id", table_name="code_review_attempts")
    op.drop_table("code_review_attempts")
    op.drop_table("code_review_drafts")
