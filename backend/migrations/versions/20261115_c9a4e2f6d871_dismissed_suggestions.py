"""dismissed suggestions: "not now" kept with the account, on every device, and undoable

Revision ID: c9a4e2f6d871
Revises: b7e1f3a5c924
Create Date: 2026-11-15

Volume 15, prompt 2 (docs/FOLLOW_UPS.md, "Not now"). Adds `dismissed_suggestions`: one row per
suggestion a learner dismissed (its key, kind, the page it was offered on, when), owner-only under
row-level security, deleted with the account, unique per account and key. A follow-up coding
problem's dismissal was kept in `user_onboarding.dismissed` as "problem-follow-up:<from>><to>";
those move here (dismissed when the onboarding row was last updated) and leave that list, which
keeps only the introduction's banners. Downgrade moves them back and drops the table.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "c9a4e2f6d871"
down_revision: str | Sequence[str] | None = "b7e1f3a5c924"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("dismissed_suggestions",)
POLICY = "codecoach_owner_only"
MAINTENANCE_POLICY = "codecoach_maintenance_read"
_NO_USER = "coalesce(current_setting('codecoach.user_id', true), '') = ''"
_SCOPE = "coalesce(current_setting('codecoach.scope', true), '')"
CONDITION = (
    "user_id = current_setting('codecoach.user_id', true) "
    f"OR ({_NO_USER} AND {_SCOPE} NOT IN ('request', 'worker', 'maintenance'))"
)
MAINTENANCE_CONDITION = f"{_NO_USER} AND {_SCOPE} = 'maintenance'"
PREFIX = "problem-follow-up:"

onboarding = sa.table(
    "user_onboarding",
    sa.column("user_id", sa.String),
    sa.column("dismissed", sa.JSON),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
dismissed = sa.table(
    "dismissed_suggestions",
    sa.column("id", sa.String),
    sa.column("user_id", sa.String),
    sa.column("key", sa.String),
    sa.column("kind", sa.String),
    sa.column("offered_on", sa.String),
    sa.column("dismissed_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        "dismissed_suggestions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("offered_on", sa.String(length=200), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "key", name="uq_dismissed_suggestion"),
    )
    op.create_index("ix_dismissed_suggestions_user_id", "dismissed_suggestions", ["user_id"])
    bind = op.get_bind()
    for user_id, keys, updated_at in bind.execute(
        sa.select(onboarding.c.user_id, onboarding.c.dismissed, onboarding.c.updated_at)
    ).all():
        moved = [k for k in (keys or []) if isinstance(k, str) and k.startswith(PREFIX)]
        if not moved:
            continue
        for key in dict.fromkeys(moved):
            from_slug, _, to_slug = key[len(PREFIX) :].partition(">")
            bind.execute(
                dismissed.insert().values(
                    id=str(uuid4()),
                    user_id=user_id,
                    key=key,
                    kind="problem_follow_up",
                    offered_on=f"/problems/{from_slug}",
                    dismissed_at=updated_at or datetime.now(UTC),
                )
            )
        bind.execute(
            onboarding.update()
            .where(onboarding.c.user_id == user_id)
            .values(dismissed=[k for k in keys if k not in moved])
        )
    if bind.dialect.name != "postgresql":
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
    bind = op.get_bind()
    back: dict[str, list[str]] = {}
    for user_id, key in bind.execute(
        sa.select(dismissed.c.user_id, dismissed.c.key).where(dismissed.c.kind == "problem_follow_up")
    ).all():
        back.setdefault(user_id, []).append(key)
    for user_id, keys in back.items():
        row = bind.execute(sa.select(onboarding.c.dismissed).where(onboarding.c.user_id == user_id)).first()
        if row is not None:
            bind.execute(
                onboarding.update()
                .where(onboarding.c.user_id == user_id)
                .values(dismissed=[*(row[0] or []), *[k for k in keys if k not in (row[0] or [])]])
            )
    if bind.dialect.name == "postgresql":
        for table in TABLES:
            op.execute(sa.text(f"DROP POLICY IF EXISTS {MAINTENANCE_POLICY} ON {table}"))
            op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY} ON {table}"))
    op.drop_index("ix_dismissed_suggestions_user_id", table_name="dismissed_suggestions")
    op.drop_table("dismissed_suggestions")
