"""debugging exercises: a problem kind, its lab material, and what each attempt started from

Revision ID: 3d1f0c2b9a77
Revises: fa8c2d7ff836
Create Date: 2026-11-09

Volume 10, prompt 2. `problems.kind` is "problem" (write a solution) or "debug" (fix a
deliberately faulty starter, seeded from app/seed/debugging); existing rows become "problem".
`problems.lab` holds a debugging exercise's authored material. On `submissions`,
`starting_code` and `lab_version` record the faulty code and the exercise version an attempt
started from, so a later correction doesn't rewrite it; they stay empty for ordinary problems.
Downgrade drops the four columns (debugging exercises then read as ordinary problems whose
starter is faulty, and attempts lose what they started from).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3d1f0c2b9a77"
down_revision: str | Sequence[str] | None = "fa8c2d7ff836"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("problems") as batch:
        batch.add_column(sa.Column("kind", sa.String(length=16), nullable=False, server_default="problem"))
        batch.add_column(
            sa.Column(
                "lab",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            )
        )
        batch.create_index("ix_problems_kind", ["kind"])
    with op.batch_alter_table("submissions") as batch:
        batch.add_column(sa.Column("starting_code", sa.Text(), nullable=True))
        batch.add_column(sa.Column("lab_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_column("lab_version")
        batch.drop_column("starting_code")
    with op.batch_alter_table("problems") as batch:
        batch.drop_index("ix_problems_kind")
        batch.drop_column("lab")
        batch.drop_column("kind")
