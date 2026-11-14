"""Offering a reviewed follow-up question (Volume 12, prompt 4; docs/FOLLOW_UPS.md).

Only this account's answers decide what it's offered. A follow-up is offered after the documented
threshold of answers to the question that were long enough to score, only when a reviewed
relationship exists, never for a retired question, and within the career unless the relationship
says otherwise. Exposure is described conservatively: "Not previously attempted in this app",
never "new to you". A follow-up answered is its own answer with its own score, linked to the answer
it followed; scores are never merged or averaged.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers.answers import _evidence_level
from app.careers.eligibility import feedback_eligibility
from app.careers.followups import THRESHOLD, follow_ups_from, follow_ups_to
from app.careers.questions import get_question, is_retired
from app.errors import AppError, NotFoundError
from app.models import PracticeAnswer, User
from app.schemas.followups import FollowUpAnswered, FollowUpOut, FollowUpQuestion
from app.services.conditions import Conditions

NOT_ATTEMPTED = "Not previously attempted in this app"


def exposure(attempts: int) -> str:
    if attempts == 0:
        return NOT_ATTEMPTED
    return f"Answered {attempts} time{'' if attempts == 1 else 's'} before in this app"


class FollowUps:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _answers(self, track: str, question_id: str) -> list[PracticeAnswer]:
        return list(
            self.db.scalars(
                select(PracticeAnswer)
                .where(
                    PracticeAnswer.user_id == self.user.id,
                    PracticeAnswer.track == track,
                    PracticeAnswer.question_id == question_id,
                )
                .order_by(PracticeAnswer.created_at)
            )
        )

    def offer(self, track: str, question_id: str) -> FollowUpOut:
        mine = self._answers(track, question_id)
        scored = sum(1 for a in mine if feedback_eligibility(a.feedback) == "scored")
        rels = follow_ups_from(track, question_id)
        offers: list[FollowUpQuestion] = []
        for r in rels:
            q = get_question(r.target_track, r.to_id)
            if q is None or is_retired(r.target_track, r.to_id):
                continue  # retired (or gone): not offered
            attempts = len(self._answers(r.target_track, r.to_id))
            offers.append(
                FollowUpQuestion(
                    track=r.target_track,
                    question_id=q.id,
                    title=q.title,
                    version=q.version,
                    objective=r.objective,
                    difference=r.difference,
                    exposure=exposure(attempts),
                    attempts=attempts,
                )
            )
        answered = self._answered(mine)
        if not offers:
            status, message = "none", "No reviewed related question is linked to this one yet."
            offers = []
        elif scored < THRESHOLD:
            status = "not_yet"
            message = (
                f"After {THRESHOLD} answers to this question that are long enough to score, a related "
                "question may be offered here."
            )
            offers = []
        else:
            status = "offered"
            message = (
                "An optional, different question about the same thing, to see whether what you practised "
                "carries over. Your answers here stay as they are."
            )
        return FollowUpOut(
            status=status,
            message=message,
            threshold=THRESHOLD,
            scored_answers=scored,
            offers=offers,
            answered=answered,
        )

    def _answered(self, mine: list[PracticeAnswer]) -> list[FollowUpAnswered]:
        if not mine:
            return []
        rows = list(
            self.db.scalars(
                select(PracticeAnswer)
                .where(
                    PracticeAnswer.user_id == self.user.id,
                    PracticeAnswer.follows_up_answer_id.in_([a.id for a in mine]),
                )
                .order_by(PracticeAnswer.created_at)
            )
        )
        found = Conditions(self.db, self.user).for_answers(rows)
        out = []
        for a in rows:
            q = get_question(a.track, a.question_id)
            out.append(
                FollowUpAnswered(
                    answer_id=a.id,
                    track=a.track,
                    question_id=a.question_id,
                    title=q.title if q else "A question that's no longer in the library",
                    score=a.score,
                    rating=(a.feedback or {}).get("rating", ""),
                    evidence_level=_evidence_level(a.feedback),
                    content_version=a.content_version or 1,
                    created_at=a.created_at,
                    follows_up_answer_id=a.follows_up_answer_id or "",
                    conditions=found.get(a.id),
                )
            )
        return out

    def check_link(self, track: str, question_id: str, parent_id: str | None) -> str | None:
        """The answer a follow-up names: this account's own, to a question with a reviewed
        relationship to this one. Another account's answer is 404, like one that doesn't exist."""
        if parent_id is None:
            return None
        parent = self.db.get(PracticeAnswer, parent_id)
        if parent is None or parent.user_id != self.user.id:
            raise NotFoundError("That earlier answer wasn't found.")
        if not any(
            r.track == parent.track and r.from_id == parent.question_id
            for r in follow_ups_to(track, question_id)
        ):
            raise AppError(
                "That earlier answer isn't to a question this one follows up.", code="not_a_follow_up"
            )
        return parent.id
