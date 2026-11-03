"""submission client request id

Adds a nullable `client_request_id` to submissions with a unique constraint per user, so a retried
POST returns the existing submission instead of judging twice. Nullable, so existing rows and
populated tables migrate safely.

Revision ID: c3e8a1d5f924
Revises: b7d2f4a9c613
Create Date: 2026-11-03 01:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8a1d5f924"
down_revision: str | Sequence[str] | None = "b7d2f4a9c613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("client_request_id", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_submission_client_request", "submissions", ["user_id", "client_request_id"])


def downgrade() -> None:
    op.drop_constraint("uq_submission_client_request", "submissions", type_="unique")
    op.drop_column("submissions", "client_request_id")
