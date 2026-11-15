"""Spaced review: questions saved to come back to, on a fixed, explainable ladder.

    saved          due after 1 day
    answered again score 85+ -> next step up the ladder (1, 3, 7, 14, 30 days, capped at 30)
                   score 70-84 -> same step again
                   below 70 -> back to 1 day
    snooze         push the due date by 1, 3 or 7 days (doesn't count as a review)

A review counts only when the question is actually answered again (a practice answer recorded
after the item was last scheduled). Nothing is sent: no email, no push; the queue is a page.

Disputed feedback (Volume 14, prompt 9; docs/DISPUTES.md), by the plan's own rule
(app/services/disputes.py): an answer whose feedback you disputed overall doesn't move the ladder
(its score isn't used; counting it again lets the next look use it). An item is here for its
reasons: you saved it (from an interview's answer, or on its own), and each answer since. When every
reason comes from disputed feedback (saved from an interview answer you disputed, and not answered
since except in answers you disputed) it isn't scheduled: it's listed under "You disputed this",
with a way back. An item with any other reason keeps its schedule and says which reason is disputed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.questions import get_question
from app.errors import AppError, NotFoundError
from app.models import InterviewTurn, PracticeAnswer, PracticeSession, ReviewItem, User
from app.schemas.review import ReviewAdd, ReviewQueue, ReviewQueueItem
from app.services.disputes import Dispute, Disputes, note, overall

LADDER = (1, 3, 7, 14, 30)
MAX_ACTIVE = 100


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _day(dt: datetime) -> str:
    return f"{dt:%b} {dt.day}"


class ReviewQueueService:
    def __init__(self, db: Session):
        self.db = db

    def _item(self, user: User, item_id: str) -> ReviewItem:
        row = self.db.get(ReviewItem, item_id)
        if row is None or row.user_id != user.id or row.removed:
            raise NotFoundError("Review item not found")
        return row

    def add(self, user: User, body: ReviewAdd) -> ReviewQueue:
        if body.track not in CATALOG or get_question(body.track, body.question_id) is None:
            raise NotFoundError("Question not found")
        if body.session_id:
            s = self.db.get(PracticeSession, body.session_id)
            if s is None or s.user_id != user.id:
                raise NotFoundError("Interview not found")
        existing = self.db.scalar(
            select(ReviewItem).where(
                ReviewItem.user_id == user.id,
                ReviewItem.track == body.track,
                ReviewItem.question_id == body.question_id,
                ReviewItem.removed.is_(False),
            )
        )
        if existing is None:
            active = (
                self.db.scalar(
                    select(func.count())
                    .select_from(ReviewItem)
                    .where(ReviewItem.user_id == user.id, ReviewItem.removed.is_(False))
                )
                or 0
            )
            if active >= MAX_ACTIVE:
                raise AppError(
                    f"Your review queue holds up to {MAX_ACTIVE} questions. Remove some first.",
                    code="queue_full",
                )
            now = _now()
            self.db.add(
                ReviewItem(
                    user_id=user.id,
                    track=body.track,
                    question_id=body.question_id,
                    session_id=body.session_id,
                    step=0,
                    due_at=now + timedelta(days=LADDER[0]),
                    scheduled_at=now,
                    created_at=now,
                )
            )
            self.db.commit()
        return self.queue(user)

    def snooze(self, user: User, item_id: str, days: int) -> ReviewQueue:
        row = self._item(user, item_id)
        row.due_at = max(_aware(row.due_at), _now()) + timedelta(days=days)
        row.snoozed = True
        self.db.commit()
        return self.queue(user)

    def remove(self, user: User, item_id: str) -> ReviewQueue:
        row = self._item(user, item_id)
        row.removed = True
        self.db.commit()
        return self.queue(user)

    def _sync(self, user: User, rows: list[ReviewItem], disputes: dict[tuple[str, str], Dispute]) -> None:
        changed = False
        for row in rows:
            answers = self.db.scalars(
                select(PracticeAnswer)
                .where(
                    PracticeAnswer.user_id == user.id,
                    PracticeAnswer.track == row.track,
                    PracticeAnswer.question_id == row.question_id,
                    PracticeAnswer.created_at > row.scheduled_at,
                )
                .order_by(PracticeAnswer.created_at.desc())
            ).all()
            # The latest answer whose feedback isn't disputed overall: a disputed score doesn't move
            # the ladder (counted again, the next look uses it).
            answer = next((a for a in answers if overall(disputes, a.id) is None), None)
            if answer is None:
                continue
            if answer.score >= 85:
                row.step = min(row.step + 1, len(LADDER) - 1)
            elif answer.score < 70:
                row.step = 0
            at = _aware(answer.created_at)
            row.reviews += 1
            row.last_score = answer.score
            row.scheduled_at = at
            row.due_at = at + timedelta(days=LADDER[row.step])
            row.snoozed = False
            changed = True
        if changed:
            self.db.commit()

    def _why(self, row: ReviewItem, due: bool) -> str:
        interval = LADDER[row.step]
        if row.reviews == 0:
            base = f"Saved {_day(_aware(row.created_at))}; the first review comes {LADDER[0]} day later."
        elif row.last_score is not None and row.last_score < 70:
            base = (
                f"Last answered {_day(_aware(row.scheduled_at))} scoring {row.last_score}/100 (below 70), "
                f"so it comes back after {interval} day{'s' if interval != 1 else ''}."
            )
        elif row.last_score is not None and row.last_score >= 85:
            base = (
                f"Last answered {_day(_aware(row.scheduled_at))} scoring {row.last_score}/100, so the gap grew "
                f"to {interval} days."
            )
        else:
            base = (
                f"Last answered {_day(_aware(row.scheduled_at))} scoring {row.last_score}/100, so it stays at "
                f"{interval} day{'s' if interval != 1 else ''} until you reach 85."
            )
        if row.snoozed:
            base += f" Snoozed until {_day(_aware(row.due_at))}."
        return ("Due now. " if due else f"Due {_day(_aware(row.due_at))}. ") + base

    def _saved_from(self, user: User, row: ReviewItem) -> str | None:
        """The interview answer this item was saved from, if it was saved from an interview."""
        if not row.session_id:
            return None
        return self.db.scalar(
            select(PracticeAnswer.id)
            .join(InterviewTurn, InterviewTurn.answer_id == PracticeAnswer.id)
            .where(
                InterviewTurn.session_id == row.session_id,
                PracticeAnswer.user_id == user.id,
                PracticeAnswer.track == row.track,
                PracticeAnswer.question_id == row.question_id,
            )
            .order_by(PracticeAnswer.created_at.desc())
            .limit(1)
        )

    def reasons(
        self, user: User, row: ReviewItem, disputes: dict[tuple[str, str], Dispute]
    ) -> tuple[bool, Dispute | None]:
        """(withheld: every reason it's here is disputed feedback, the dispute to name or None)."""
        saved_from = self._saved_from(user, row)
        saved_dispute = overall(disputes, saved_from)
        since = self.db.scalars(
            select(PracticeAnswer.id).where(
                PracticeAnswer.user_id == user.id,
                PracticeAnswer.track == row.track,
                PracticeAnswer.question_id == row.question_id,
                PracticeAnswer.created_at > row.created_at,
                PracticeAnswer.id != (saved_from or ""),
            )
        ).all()
        since_disputes = [overall(disputes, a) for a in since]
        undisputed_since = any(d is None for d in since_disputes)
        if saved_dispute is not None and not undisputed_since:
            return True, saved_dispute
        first = saved_dispute or next((d for d in since_disputes if d is not None), None)
        return False, first

    def withheld_ids(self, user: User) -> set[str]:
        """Items not scheduled because every reason they're here is disputed feedback: the queue's
        own rule, for anything that counts or offers due reviews (the schedule, Today)."""
        disputes = Disputes(self.db, user.id).active()
        if not disputes:
            return set()
        rows = self.db.scalars(
            select(ReviewItem).where(ReviewItem.user_id == user.id, ReviewItem.removed.is_(False))
        ).all()
        return {r.id for r in rows if self.reasons(user, r, disputes)[0]}

    def queue(self, user: User) -> ReviewQueue:
        rows = list(
            self.db.scalars(
                select(ReviewItem)
                .where(ReviewItem.user_id == user.id, ReviewItem.removed.is_(False))
                .order_by(ReviewItem.due_at)
            ).all()
        )
        disputes = Disputes(self.db, user.id).active()
        self._sync(user, rows, disputes)
        now = _now()
        due: list[ReviewQueueItem] = []
        upcoming: list[ReviewQueueItem] = []
        disputed: list[ReviewQueueItem] = []
        for row in sorted(rows, key=lambda r: _aware(r.due_at)):
            q = get_question(row.track, row.question_id)
            is_due = _aware(row.due_at) <= now
            withheld, dispute = self.reasons(user, row, disputes) if disputes else (False, None)
            why = self._why(row, is_due)
            if withheld and dispute is not None:
                why = (
                    f"Not scheduled: you saved it from an interview answer whose feedback you disputed {dispute.when}, "
                    "and that's the only reason it's here. Count that feedback again to put it back, or answer it "
                    "any time."
                )
            elif dispute is not None:
                why += (
                    f" One reason it's here is feedback you disputed {dispute.when}; it's scheduled for its other "
                    "reasons."
                )
            item = ReviewQueueItem(
                id=row.id,
                track=row.track,
                career_title=CATALOG[row.track].title if row.track in CATALOG else row.track,
                question_id=row.question_id,
                title=q.title if q else "A question that's no longer in the library",
                href=f"/careers/{row.track}/questions/{row.question_id}",
                due_at=row.due_at,
                due=is_due,
                why=why,
                interval_days=LADDER[row.step],
                last_score=row.last_score,
                reviews=row.reviews,
                snoozed=row.snoozed,
                dispute=note(dispute),
            )
            if withheld:
                disputed.append(item)
            else:
                (due if is_due else upcoming).append(item)
        return ReviewQueue(
            due=due,
            upcoming=upcoming,
            disputed=disputed,
            ladder_days=list(LADDER),
            note="Answer a due question again to review it. Strong answers (85+) space it out; weaker ones bring it "
            "back sooner. Nothing is emailed or pushed to you.",
        )
