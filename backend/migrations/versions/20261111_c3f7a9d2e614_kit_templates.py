"""kit templates: personal templates of interview-kit checklist items and questions

Revision ID: c3f7a9d2e614
Revises: b8e4c2a7d915
Create Date: 2026-11-11

Volume 11, prompt 7 (docs/TEMPLATES.md). `kit_templates` holds a learner's own templates: a name,
the checklist items and questions to ask chosen from a kit (text, and a question's group; never
whether an item was done, links, notes or anything about the interview), a revision for
conflict-checked edits, and the key of the create that made it (a lost reply sent again makes one,
not two). Cascades with the account; under row-level security on PostgreSQL with the policies
7c1d2e3f4a5b installs (app/db/rls.py lists it under this revision). Downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3f7a9d2e614"
down_revision: str | Sequence[str] | None = "b8e4c2a7d915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here (not imported) so this migration means the same thing forever; tests check they match
# what the app installs on a development database.
TABLES = ("kit_templates",)
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
    op.create_table(
        "kit_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("checklist", _json(), nullable=False),
        sa.Column("questions", _json(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_kit_template_client_request"),
    )
    op.create_index("ix_kit_templates_user_id", "kit_templates", ["user_id"])
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
    op.drop_index("ix_kit_templates_user_id", table_name="kit_templates")
    op.drop_table("kit_templates")
