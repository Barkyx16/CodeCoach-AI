"""collections can be duplicated

Revision ID: e5b1c7d9a248
Revises: d4a9b2e6f137
Create Date: 2026-11-16

Volume 16, prompt 8 (docs/BULK_ACTIONS.md, "Duplicate a collection"). Adds two nullable columns to
`practice_collections`: `copied_from_id`, the collection a copy was made from (no foreign key: the
original can be deleted and the copy stays), and `client_request_id`, unique per account, so a
retried "Duplicate" returns the copy it made instead of making another. Existing collections keep
both null; no row is rewritten. The table is already owner-only under row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b1c7d9a248"
down_revision: str | Sequence[str] | None = "d4a9b2e6f137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("practice_collections", sa.Column("copied_from_id", sa.String(length=36), nullable=True))
    op.add_column("practice_collections", sa.Column("client_request_id", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_collection_request", "practice_collections", ["user_id", "client_request_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_collection_request", "practice_collections", type_="unique")
    op.drop_column("practice_collections", "client_request_id")
    op.drop_column("practice_collections", "copied_from_id")
