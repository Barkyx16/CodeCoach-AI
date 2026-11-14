"""Spaced review: questions saved to come back to, on a fixed, explainable ladder.

    saved          due after 1 day
    answered again score 85+ -> next step up the ladder (1, 3, 7, 14, 30 days, capped at 30)
                   score 70-84 -> same step again
                   below 70 -> back to 1 day
    snooze         push the due date by 1, 3 or 7 days (doesn't count as a review)

A review counts only when the question is actually answered again (a practice answer recorded
after the item was last scheduled). Nothing is sent: no email, no push; the queue is a page.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.questions import get_question
from app.errors import AppError, NotFoundError
from app.models import PracticeAnswer, PracticeSession, ReviewItem, User
from app.schemas.review import ReviewAdd, ReviewQueue, ReviewQueueItem

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

    def _sync(self, user: User, rows: list[ReviewItem]) -> None:
        changed = False
        for row in rows:
            answer = self.db.scalar(
                select(PracticeAnswer)
                .where(
                    PracticeAnswer.user_id == user.id,
                    PracticeAnswer.track == row.track,
                    PracticeAnswer.question_id == row.question_id,
                    PracticeAnswer.created_at > row.scheduled_at,
                )
                .order_by(PracticeAnswer.created_at.desc())
                .limit(1)
            )
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

    def queue(self, user: User) -> ReviewQueue:
        rows = list(
            self.db.scalars(
                select(ReviewItem)
                .where(ReviewItem.user_id == user.id, ReviewItem.removed.is_(False))
                .order_by(ReviewItem.due_at)
            ).all()
        )
        self._sync(user, rows)
        now = _now()
        due: list[ReviewQueueItem] = []
        upcoming: list[ReviewQueueItem] = []
        for row in sorted(rows, key=lambda r: _aware(r.due_at)):
            q = get_question(row.track, row.question_id)
            is_due = _aware(row.due_at) <= now
            item = ReviewQueueItem(
                id=row.id,
                track=row.track,
                career_title=CATALOG[row.track].title if row.track in CATALOG else row.track,
                question_id=row.question_id,
                title=q.title if q else "A question that's no longer in the library",
                href=f"/careers/{row.track}/questions/{row.question_id}",
                due_at=row.due_at,
                due=is_due,
                why=self._why(row, is_due),
                interval_days=LADDER[row.step],
                last_score=row.last_score,
                reviews=row.reviews,
                snoozed=row.snoozed,
            )
            (due if is_due else upcoming).append(item)
        return ReviewQueue(
            due=due,
            upcoming=upcoming,
            ladder_days=list(LADDER),
            note="Answer a due question again to review it. Strong answers (85+) space it out; weaker ones bring it "
            "back sooner. Nothing is emailed or pushed to you.",
        )
