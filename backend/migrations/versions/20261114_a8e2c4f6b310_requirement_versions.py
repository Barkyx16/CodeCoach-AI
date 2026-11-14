"""requirement versions: a job target's requirements keep their identity and history

Revision ID: a8e2c4f6b310
Revises: f7d1b3e5a209
Create Date: 2026-11-14

Volume 12, prompt 5 (docs/REQUIREMENT_VERSIONS.md). Adds `target_requirements.version` (not null,
default 1) and `role_targets.requirements_revision` (not null, default 1: the requirement set's
revision, checked when it's saved), `experience_entries.requirement_versions` (nullable JSON: the
version of each requirement a story was linked to; absent for links made before, which say
"version not recorded"), `accepted_actions.requirement_reuse` (nullable JSON: an accepted action
deliberately reused for a requirement's newer wording; otherwise its version is the one in effect
when it was accepted, read from the history), and `requirement_versions`, one row per recorded state of a requirement
(added, changed, removed, restored, cosmetic edits not recorded as versions) with its words and the
skills it mapped to then, owned by the user
and under row-level security on PostgreSQL (app/db/rls.py lists it under this revision). Nothing
existing is rewritten. Downgrade drops all five.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8e2c4f6b310"
down_revision: str | Sequence[str] | None = "f7d1b3e5a209"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("requirement_versions",)
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
    op.add_column(
        "target_requirements", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "role_targets", sa.Column("requirements_revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("experience_entries", sa.Column("requirement_versions", _json(), nullable=True))
    op.add_column("accepted_actions", sa.Column("requirement_reuse", _json(), nullable=True))
    op.create_table(
        "requirement_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "target_id",
            sa.String(length=36),
            sa.ForeignKey("role_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("skills", _json(), nullable=True),
        sa.Column("set_revision", sa.Integer(), nullable=False),
        sa.Column("same_as", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_requirement_versions_user_id", "requirement_versions", ["user_id"])
    op.create_index(
        "ix_requirement_versions_requirement", "requirement_versions", ["requirement_id", "version"]
    )
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
    op.drop_index("ix_requirement_versions_requirement", table_name="requirement_versions")
    op.drop_index("ix_requirement_versions_user_id", table_name="requirement_versions")
    op.drop_table("requirement_versions")
    with op.batch_alter_table("accepted_actions") as batch:
        batch.drop_column("requirement_reuse")
    with op.batch_alter_table("experience_entries") as batch:
        batch.drop_column("requirement_versions")
    with op.batch_alter_table("role_targets") as batch:
        batch.drop_column("requirements_revision")
    with op.batch_alter_table("target_requirements") as batch:
        batch.drop_column("version")
