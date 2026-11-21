"""practice answers: request keys (at most one saved answer per owner and key) and revision links

Revision ID: c4d5e6f7a8b9
Revises: b7c1d2e3f4a5
Create Date: 2026-11-04 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b7c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Additive and nullable: existing answers get no key, no fingerprint and no
    revision link (none is made up for them); no row is rewritten."""
    with op.batch_alter_table("practice_answers") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_fingerprint", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("revises_answer_id", sa.String(length=36), nullable=True))
        batch.create_unique_constraint("uq_practice_answer_client_request", ["user_id", "client_request_id"])
        batch.create_foreign_key(
            "fk_answer_revises", "practice_answers", ["revises_answer_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_practice_answers_revises_answer_id", ["revises_answer_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema. Drops the keys, fingerprints and revision links (that information is lost;
    every answer, its text, score and feedback stay). After a downgrade a resend of a request made
    before it can save a second answer: see docs/RELEASE_READINESS.md."""
    with op.batch_alter_table("practice_answers") as batch:
        batch.drop_index("ix_practice_answers_revises_answer_id")
        batch.drop_constraint("fk_answer_revises", type_="foreignkey")
        batch.drop_constraint("uq_practice_answer_client_request", type_="unique")
        batch.drop_column("revises_answer_id")
        batch.drop_column("request_fingerprint")
        batch.drop_column("client_request_id")
