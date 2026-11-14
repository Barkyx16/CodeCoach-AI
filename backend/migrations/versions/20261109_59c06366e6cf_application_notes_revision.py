"""applications: a revision for the private notes

Revision ID: 59c06366e6cf
Revises: 7045bdb6a532
Create Date: 2026-11-09

An application's private notes were last-write-wins: two devices editing them from the same start
silently kept only the later save (Volume 8, prompt 5; docs/PERSISTENCE.md). `notes_revision`
counts the notes' own saves; a notes change must name the revision it started from, and a stale
one is refused with the saved notes to compare. Other fields (stage, dates, next action) don't
touch it, so they never conflict with the notes.

Every existing row keeps its notes unchanged and starts at revision 1. Downgrade drops the column
(notes go back to last write wins).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "59c06366e6cf"
down_revision: str | Sequence[str] | None = "7045bdb6a532"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("notes_revision", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("notes_revision")
