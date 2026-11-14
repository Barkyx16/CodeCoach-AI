"""Disputed feedback (Volume 12, prompt 7; docs/DISPUTES.md).

A dispute is an "I disagree" flag on one point of an answer's feedback (or on the feedback overall)
that the learner hasn't reinstated. While it stands, that point doesn't shape automatic
recommendations; the feedback, the score and any judge verdict stay exactly as they were. This
module is the one place that says which disputes stand and how to word them.

"Unclear" flags aren't disputes, and a content report about a question is a separate flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcceptedAction, AnswerFlag, InterviewTurn, PlanItem, PracticeAnswer
from app.schemas.disputes import DisputeNote

OVERALL = "Overall"


@dataclass(frozen=True)
class Dispute:
    flag_id: int
    answer_id: str
    criterion: str
    track: str
    question_id: str
    disputed_at: datetime | None  # None: from before the date was recorded

    @property
    def href(self) -> str:
        return f"/careers/{self.track}/questions/{self.question_id}?answer={self.answer_id}"

    @property
    def when(self) -> str:
        if self.disputed_at is None:
            return "(the date wasn't recorded)"
        day = self.disputed_at.astimezone(UTC)  # the UTC calendar day, as the flag panel shows it
        return f"on {day.day} {day:%B}"

    @property
    def what(self) -> str:
        return "that feedback" if self.criterion == OVERALL else f"“{self.criterion}”"


def is_active(f: AnswerFlag) -> bool:
    return f.kind == "disagree" and f.reinstated_at is None


class Disputes:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def active(self, track: str | None = None) -> dict[tuple[str, str], Dispute]:
        """Every standing dispute of this account (optionally one career's), by (answer, criterion)."""
        stmt = (
            select(AnswerFlag, PracticeAnswer.track, PracticeAnswer.question_id)
            .join(PracticeAnswer, PracticeAnswer.id == AnswerFlag.answer_id)
            .where(
                AnswerFlag.user_id == self.user_id,
                PracticeAnswer.user_id == self.user_id,
                AnswerFlag.kind == "disagree",
                AnswerFlag.reinstated_at.is_(None),
            )
        )
        if track is not None:
            stmt = stmt.where(PracticeAnswer.track == track)
        out = {}
        for f, t, q in self.db.execute(stmt):
            out[(f.answer_id, f.criterion)] = Dispute(f.id, f.answer_id, f.criterion, t, q, f.disputed_at)
        return out


def covering(disputes: dict[tuple[str, str], Dispute], answer_id: str, criterion: str) -> Dispute | None:
    """The dispute that covers one point of one answer: on that point, or on the feedback overall."""
    return disputes.get((answer_id, criterion)) or disputes.get((answer_id, OVERALL))


def first_disputed(disputes: dict[tuple[str, str], Dispute], derived: list[dict] | None) -> Dispute | None:
    """For something derived from these (answer, criterion) pairs: the first standing dispute among
    them, or None. Derivation not recorded (None) can't be labelled: it isn't guessed."""
    for d in derived or []:
        hit = covering(disputes, str(d.get("answer_id")), str(d.get("criterion")))
        if hit is not None:
            return hit
    return None


def note(d: Dispute | None) -> DisputeNote | None:
    if d is None:
        return None
    what = "" if d.criterion == OVERALL else f": {d.what}"
    return DisputeNote(
        text=f"Based on feedback you disputed {d.when}{what}.",
        href=d.href,
        answer_id=d.answer_id,
        criterion=d.criterion,
    )


def for_plan_item(disputes: dict[tuple[str, str], Dispute], item: PlanItem) -> Dispute | None:
    return first_disputed(disputes, item.derived_from)


def for_action(db: Session, disputes: dict[tuple[str, str], Dispute], row: AcceptedAction) -> Dispute | None:
    """An accepted improvement came from one feedback point missing across an interview's answers
    (its key "point:<label>"): disputed when that point (or that feedback overall) is disputed on any
    of the interview's answers. Other improvements ("answer the questions you didn't get to") come
    from no feedback point."""
    key = row.source_key or ""
    if not disputes or not key.startswith("point:"):
        return None
    label = key[len("point:") :]
    answer_ids = db.scalars(
        select(InterviewTurn.answer_id).where(
            InterviewTurn.session_id == row.source_id, InterviewTurn.answer_id.is_not(None)
        )
    ).all()
    for aid in answer_ids:
        hit = covering(disputes, str(aid), label)
        if hit is not None:
            return hit
    return None
