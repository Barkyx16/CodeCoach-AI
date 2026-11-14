"""source reviews: when linked evidence's story changed, and what the learner decided

Revision ID: c1d4e6a8b532
Revises: b9f3d5e7a421
Create Date: 2026-11-14

Volume 12, prompt 8 (docs/STORY_FRESHNESS.md). Adds `source_reviews`, one row per deliberate
decision about a changed source behind a piece of preparation (refreshed to a reviewed revision, or
kept as prepared), owner-only under row-level security, deleted with the account; and
`interview_kits.story_snapshots` (nullable JSON: each chosen story as the kit prepared it: its
revision, a digest of its content, title and short version, kept if the story is deleted).
Requirement links keep the story's revision and digest inside `experience_entries.requirement_versions`
(JSON already there). Kits and links from before have none: their freshness is unknown or read
from the story's kept revisions, never guessed. Nothing existing is rewritten; downgrade drops both.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d4e6a8b532"
down_revision: str | Sequence[str] | None = "b9f3d5e7a421"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("source_reviews",)
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


def upgrade() -> None:
    op.add_column("interview_kits", sa.Column("story_snapshots", _json(), nullable=True))
    op.create_table(
        "source_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("holder_kind", sa.String(length=20), nullable=False),
        sa.Column("holder_id", sa.String(length=64), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("from_revision", sa.Integer(), nullable=True),
        sa.Column("to_revision", sa.Integer(), nullable=False),
        sa.Column("to_digest", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "holder_kind", "holder_id", "source_id", "to_revision", "decision", name="uq_source_review"
        ),
    )
    op.create_index("ix_source_reviews_user_id", "source_reviews", ["user_id"])
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
    op.drop_index("ix_source_reviews_user_id", table_name="source_reviews")
    op.drop_table("source_reviews")
    with op.batch_alter_table("interview_kits") as batch:
        batch.drop_column("story_snapshots")
