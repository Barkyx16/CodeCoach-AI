"""interviews: one in progress per user, and one turn per position, enforced by the database

Revision ID: 8d9e0f1a2b3c
Revises: 4e5f6a7b8c9d
Create Date: 2026-11-08

"One interview in progress per user" was a read followed by an insert. Two Starts at once (two
tabs, a double click, a retried request) could both pass the read and make two interviews. Turns
were numbered len(turns), so two answers at once (two tabs on the same question) could both be
stored. Two constraints make those impossible, whatever the request timing:
- `uq_one_live_interview`: a partial unique index on practice_sessions(user_id) for status
  'in_progress' and the interview modes ('interview', 'questions'). Practice sessions are
  untouched by it.
- `uq_interview_turn_seq`: unique (session_id, seq) on interview_turns.

Existing data is made consistent first, and nothing is deleted:
- Turns that share a position in one interview are renumbered in their stored order (seq, then
  id).
- Where a user has more than one interview in progress, the most recently started one stays in
  progress. The others are closed as abandoned, with no evaluation, as if stopped at that moment.
  Completed, expired and abandoned interviews are not touched.

Downgrade drops the two constraints. It doesn't reopen anything.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "8d9e0f1a2b3c"
down_revision: str | Sequence[str] | None = "4e5f6a7b8c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE = "status = 'in_progress' AND mode IN ('interview', 'questions')"


def upgrade() -> None:
    bind = op.get_bind()
    sessions = bind.execute(
        sa.text("SELECT session_id FROM interview_turns GROUP BY session_id, seq HAVING count(*) > 1")
    ).scalars()
    for session_id in sorted(set(sessions)):
        ids = bind.execute(
            sa.text("SELECT id FROM interview_turns WHERE session_id = :s ORDER BY seq, id"),
            {"s": session_id},
        ).scalars()
        for position, turn_id in enumerate(list(ids)):
            bind.execute(
                sa.text("UPDATE interview_turns SET seq = :p WHERE id = :i"), {"p": position, "i": turn_id}
            )

    users = bind.execute(
        sa.text(f"SELECT user_id FROM practice_sessions WHERE {LIVE} GROUP BY user_id HAVING count(*) > 1")
    ).scalars()
    now = datetime.now(UTC)
    for user_id in list(users):
        live = list(
            bind.execute(
                sa.text(
                    f"SELECT id FROM practice_sessions WHERE user_id = :u AND {LIVE} ORDER BY started_at DESC, id"
                ),
                {"u": user_id},
            ).scalars()
        )
        for older in live[1:]:
            bind.execute(
                sa.text(
                    "UPDATE practice_sessions SET status = 'abandoned', ended_at = :t WHERE id = :i"
                ).bindparams(
                    sa.bindparam("t", type_=sa.DateTime(timezone=True))  # stored like every other timestamp
                ),
                {"t": now, "i": older},
            )

    with op.batch_alter_table("interview_turns") as batch:
        batch.create_unique_constraint("uq_interview_turn_seq", ["session_id", "seq"])
    op.create_index(
        "uq_one_live_interview",
        "practice_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(LIVE),
        sqlite_where=sa.text(LIVE),
    )


def downgrade() -> None:
    op.drop_index("uq_one_live_interview", table_name="practice_sessions")
    with op.batch_alter_table("interview_turns") as batch:
        batch.drop_constraint("uq_interview_turn_seq", type_="unique")
