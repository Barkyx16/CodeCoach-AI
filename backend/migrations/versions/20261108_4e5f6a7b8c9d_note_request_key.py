"""notes: a request key, so a create sent twice makes one note

Revision ID: 4e5f6a7b8c9d
Revises: 7c1d2e3f4a5b
Create Date: 2026-11-08

The notebook autosaves. If a create's response is lost (a dropped connection, a tab closed
mid-request), the next save used to create the note again. `client_request_id`, unique per user,
makes the repeat return the note the first one made. Existing notes keep NULL, which the unique
constraint allows many of. No data changes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4e5f6a7b8c9d"
down_revision: str | Sequence[str] | None = "7c1d2e3f4a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notes") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.create_unique_constraint("uq_note_client_request", ["user_id", "client_request_id"])


def downgrade() -> None:
    with op.batch_alter_table("notes") as batch:
        batch.drop_constraint("uq_note_client_request", type_="unique")
        batch.drop_column("client_request_id")
