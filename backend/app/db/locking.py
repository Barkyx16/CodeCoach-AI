"""Revision checks that hold under concurrency.

The long-form editors (notes, stories, whiteboard drafts, reflections) take the revision the
client started from and refuse a save if the row moved on (409). Comparing in Python isn't enough
on its own: two saves sent at the same moment can both read revision 3, both pass, and the second
silently overwrites the first. `lock_for_update` re-reads the row with SELECT ... FOR UPDATE
(PostgreSQL), so the second save waits for the first to commit, then sees revision 4 and gets its
409. SQLite ignores FOR UPDATE: it allows one writer at a time, and it is only used for local runs
(docs/PERSISTENCE.md).
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def lock_for_update[T](db: Session, row: T) -> T:
    """Re-read `row` under a row lock held until this transaction ends. Returns it."""
    if row is not None:
        db.refresh(row, with_for_update=True)
    return row
