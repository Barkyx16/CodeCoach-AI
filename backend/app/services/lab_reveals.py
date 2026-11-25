"""A debugging exercise's explanation and reference repair, recorded when the learner opens it
(Volume 16, prompt 2; docs/ATTEMPT_CONDITIONS.md, "Debugging exercises").

Opening it is "Solution revealed" for the next attempt at that exercise's version, by the rule every
format uses: help belongs to the first attempt after it. So one row is enough until the learner's
next attempt; asking again before then adds nothing, which also keeps the table bounded.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LabReveal, Problem, Submission, User


def record_reveal(db: Session, user: User, problem: Problem) -> LabReveal:
    """The opening of this exercise's explanation that the next attempt will list: an existing one
    since the learner's last attempt at it (at this version), or a new one now."""
    version = int((problem.lab or {})["version"])
    last = db.scalar(
        select(func.max(Submission.created_at)).where(
            Submission.user_id == user.id, Submission.problem_id == problem.id
        )
    )
    since = select(LabReveal).where(
        LabReveal.user_id == user.id,
        LabReveal.problem_id == problem.id,
        LabReveal.lab_version == version,
    )
    if last is not None:
        since = since.where(LabReveal.created_at > last)
    found = db.scalar(since.order_by(LabReveal.created_at).limit(1))
    if found is not None:
        return found
    row = LabReveal(user_id=user.id, problem_id=problem.id, lab_version=version, created_at=datetime.now(UTC))
    db.add(row)
    db.commit()
    return row


def export(db: Session, user: User) -> list[dict]:
    """Every recorded opening, for the data export: the exercise, its version then, and when."""
    rows = db.execute(
        select(LabReveal, Problem.slug)
        .join(Problem, Problem.id == LabReveal.problem_id)
        .where(LabReveal.user_id == user.id)
        .order_by(LabReveal.created_at)
    ).all()
    return [
        {"id": r.id, "exercise": slug, "lab_version": r.lab_version, "at": r.created_at.isoformat()}
        for r, slug in rows
    ]
