"""note source reviews: a note's "Mark reviewed" is recorded like a story decision

Revision ID: e3a7c9b5d118
Revises: d2e5f7a9c643
Create Date: 2026-11-15

Volume 13, prompt 6 (docs/STORY_FRESHNESS.md, "Notes"). A note captured from a question, a lesson
or a coding problem says when that source has a newer version; the learner's "Mark reviewed" is a
row in `source_reviews` (holder_kind "note", decision "reviewed"). A note's source is named by its
library key ("registered-nurse/e-accuracy-0", a lesson id, a problem slug), longer than a story id,
so `source_reviews.source_id` widens from 36 to 160 characters (the length notes and
content_versions use). Widening a varchar keeps every row as it is; nothing else changes.
Downgrade narrows it back, which refuses if a note review is longer than 36 characters.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3a7c9b5d118"
down_revision: str | Sequence[str] | None = "d2e5f7a9c643"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("source_reviews") as batch:
        batch.alter_column("source_id", existing_type=sa.String(length=36), type_=sa.String(length=160))


def downgrade() -> None:
    with op.batch_alter_table("source_reviews") as batch:
        batch.alter_column("source_id", existing_type=sa.String(length=160), type_=sa.String(length=36))
