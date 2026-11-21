"""AI coaching and stories: a request key, so a request sent again isn't charged or saved twice

Revision ID: 9a0b1c2d3e4f
Revises: 8d9e0f1a2b3c
Create Date: 2026-11-08

A hint or code review whose response was lost (a dropped connection, a timeout) used to be asked
again from scratch when the learner pressed the button again: a second provider call and a second
use of the daily budget. A new story whose response was lost was created twice. `client_request_id`,
unique per user, lets the repeat get the first answer or story back. Existing rows keep NULL, which
the unique constraints allow many of. No data changes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a0b1c2d3e4f"
down_revision: str | Sequence[str] | None = "8d9e0f1a2b3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_interactions") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.create_unique_constraint("uq_ai_interaction_request", ["user_id", "client_request_id"])
    with op.batch_alter_table("experience_entries") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.create_unique_constraint("uq_story_client_request", ["user_id", "client_request_id"])


def downgrade() -> None:
    with op.batch_alter_table("experience_entries") as batch:
        batch.drop_constraint("uq_story_client_request", type_="unique")
        batch.drop_column("client_request_id")
    with op.batch_alter_table("ai_interactions") as batch:
        batch.drop_constraint("uq_ai_interaction_request", type_="unique")
        batch.drop_column("client_request_id")
