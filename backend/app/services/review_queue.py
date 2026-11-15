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

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.questions import get_question
from app.errors import AppError, NotFoundError
from app.models import InterviewTurn, PracticeAnswer, PracticeSession, ReviewItem, User
from app.schemas.review import ReviewAdd, ReviewQueue, ReviewQueueItem
from app.services.disputes import OVERALL, Dispute, Disputes, count_words, covering, note, overall

LADDER = (1, 3, 7, 14, 30)
MAX_ACTIVE = 100


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _day(dt: datetime) -> str:
    return f"{dt:%b} {dt.day}"


def _point(criterion: str | None) -> str | None:
    """The point an item is saved for; the whole feedback ("Overall", or nothing) is no one point."""
    text = " ".join((criterion or "").split())
    return None if not text or text == OVERALL else text


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
                    criterion=_point(body.criterion),
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

    def _sync(self, rows: list[ReviewItem], history: dict[tuple[str, str], list[Answer]]) -> None:
        """The stored ladder: every answer since the item was last scheduled moves it, in order, by the
        score rule, whatever was disputed. What's shown is worked out from it, or recounted from the
        history when a dispute applies (``ladder``), so the stored steps never need rewriting."""
        changed = False
        for row in rows:
            since = _aware(row.scheduled_at)
            for a in history.get((row.track, row.question_id), []):
                if a.at <= since:
                    continue
                row.step = _next_step(row.step, a.score)
                row.reviews += 1
                row.last_score = a.score
                row.scheduled_at = a.at
                row.due_at = a.at + timedelta(days=LADDER[row.step])
                row.snoozed = False
                since = a.at
                changed = True
        if changed:
            self.db.commit()

    def _why(self, ladder: Ladder, due: bool) -> str:
        interval = LADDER[ladder.step]
        if ladder.reviews == 0:
            base = f"Saved {_day(ladder.created_at)}; the first review comes {LADDER[0]} day later."
        elif ladder.last_score is not None and ladder.last_score < 70:
            base = (
                f"Last answered {_day(ladder.scheduled_at)} scoring {ladder.last_score}/100 (below 70), "
                f"so it comes back after {interval} day{'s' if interval != 1 else ''}."
            )
        elif ladder.last_score is not None and ladder.last_score >= 85:
            base = (
                f"Last answered {_day(ladder.scheduled_at)} scoring {ladder.last_score}/100, so the gap grew "
                f"to {interval} days."
            )
        else:
            base = (
                f"Last answered {_day(ladder.scheduled_at)} scoring {ladder.last_score}/100, so it stays at "
                f"{interval} day{'s' if interval != 1 else ''} until you reach 85."
            )
        if ladder.snoozed:
            base += f" Snoozed until {_day(ladder.due_at)}."
        return ("Due now. " if due else f"Due {_day(ladder.due_at)}. ") + base

    # --- reading: one pass for the queue, the schedule, Today (it reads the queue) and the export ---

    def _history(self, user: User, rows: list[ReviewItem]) -> dict[tuple[str, str], list[Answer]]:
        """Every answer to the questions these items are for, oldest first, in one query: this
        account's only (the query names it; on PostgreSQL row-level security holds it too)."""
        keys = {(r.track, r.question_id) for r in rows}
        if not keys:
            return {}
        out: dict[tuple[str, str], list[Answer]] = {}
        for aid, track, qid, score, at in self.db.execute(_answers_to(user.id, {q for _, q in keys})):
            if (track, qid) in keys:
                out.setdefault((track, qid), []).append(Answer(aid, score, _aware(at)))
        return out

    def _saved_from(self, user: User, rows: list[ReviewItem]) -> dict[str, str]:
        """For each item saved from an interview: the answer in that interview it was saved from."""
        sessions = {r.session_id for r in rows if r.session_id}
        if not sessions:
            return {}
        latest: dict[tuple[str, str, str], tuple[datetime, str]] = {}
        for sid, aid, track, qid, at in self.db.execute(
            select(
                InterviewTurn.session_id,
                PracticeAnswer.id,
                PracticeAnswer.track,
                PracticeAnswer.question_id,
                PracticeAnswer.created_at,
            )
            .join(InterviewTurn, InterviewTurn.answer_id == PracticeAnswer.id)
            .where(InterviewTurn.session_id.in_(sorted(sessions)), PracticeAnswer.user_id == user.id)
        ):
            key = (sid, track, qid)
            if key not in latest or _aware(at) > latest[key][0]:
                latest[key] = (_aware(at), aid)
        return {
            r.id: latest[(r.session_id, r.track, r.question_id)][1]
            for r in rows
            if r.session_id and (r.session_id, r.track, r.question_id) in latest
        }

    def _state(self, user: User) -> list[QueueRead]:
        rows = list(
            self.db.scalars(
                select(ReviewItem).where(ReviewItem.user_id == user.id, ReviewItem.removed.is_(False))
            ).all()
        )
        history = self._history(user, rows)
        self._sync(rows, history)
        disputes = Disputes(self.db, user.id).active() if rows else {}
        saved_from = self._saved_from(user, rows) if disputes else {}
        out: list[QueueRead] = []
        for row in rows:
            answers = history.get((row.track, row.question_id), [])
            withheld, dispute = reasons(row, answers, saved_from.get(row.id), disputes)
            out.append(QueueRead(row, ladder(row, answers, disputes), withheld, dispute))
        return sorted(out, key=lambda r: r.ladder.due_at)

    def ladders(self, user: User) -> list[QueueRead]:
        """Each active item as it's shown: its ladder (recounted when a dispute applies), whether it's
        held back, and the dispute to name. The schedule, the export and the queue all read this."""
        return self._state(user)

    def queue(self, user: User) -> ReviewQueue:
        now = _now()
        due: list[ReviewQueueItem] = []
        upcoming: list[ReviewQueueItem] = []
        disputed: list[ReviewQueueItem] = []
        for read in self._state(user):
            row, lad, dispute = read.row, read.ladder, read.dispute
            q = get_question(row.track, row.question_id)
            is_due = lad.due_at <= now
            why = self._why(lad, is_due)
            if read.withheld and dispute is not None:
                what = (
                    "an interview answer whose feedback you disputed"
                    if dispute.criterion == OVERALL
                    else f"an interview answer, for “{row.criterion}”, and you disputed that point"
                )
                why = (
                    f"Not scheduled: you saved it from {what} {dispute.when}, and that's the only reason it's here. "
                    "Count that feedback again to put it back, or answer it any time."
                )
            elif dispute is not None:
                which = (
                    "feedback you disputed"
                    if dispute.criterion == OVERALL
                    else f"your dispute of “{row.criterion}”"
                )
                why += (
                    f" One reason it's here is {which} {dispute.when}; it's scheduled for its other reasons."
                )
            recounted = lad.recount_note(now) if not read.withheld else None
            if recounted:
                why += " " + recounted
            item = ReviewQueueItem(
                id=row.id,
                track=row.track,
                career_title=CATALOG[row.track].title if row.track in CATALOG else row.track,
                question_id=row.question_id,
                title=q.title if q else "A question that's no longer in the library",
                href=f"/careers/{row.track}/questions/{row.question_id}",
                due_at=lad.due_at,
                due=is_due,
                why=why,
                interval_days=LADDER[lad.step],
                last_score=lad.last_score,
                reviews=lad.reviews,
                snoozed=lad.snoozed,
                dispute=note(dispute),
                criterion=row.criterion,
                recounted=recounted,
            )
            if read.withheld:
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


# --- the rules, as plain functions of an item and its history ---------------------------------------


def _answers_to(user_id: str, question_ids: set[str]) -> Select:
    """This account's answers to these questions, oldest first (only the columns the ladder reads)."""
    return (
        select(
            PracticeAnswer.id,
            PracticeAnswer.track,
            PracticeAnswer.question_id,
            PracticeAnswer.score,
            PracticeAnswer.created_at,
        )
        .where(PracticeAnswer.user_id == user_id, PracticeAnswer.question_id.in_(sorted(question_ids)))
        .order_by(PracticeAnswer.created_at, PracticeAnswer.id)
    )


class Answer(NamedTuple):
    id: str
    score: int
    at: datetime


def _next_step(step: int, score: int) -> int:
    if score >= 85:
        return min(step + 1, len(LADDER) - 1)
    if score < 70:
        return 0
    return step


def held(row: ReviewItem, disputes: dict[tuple[str, str], Dispute], answer_id: str | None) -> Dispute | None:
    """The dispute that keeps this answer's score out of this item, or None: a dispute of the whole
    feedback, or, for an item saved for one point, a dispute of that point (it counts like a dispute
    of the whole feedback, for that item only)."""
    if not answer_id:
        return None
    if row.criterion:
        return covering(disputes, answer_id, row.criterion)
    return overall(disputes, answer_id)


def reasons(
    row: ReviewItem, answers: list[Answer], saved_from: str | None, disputes: dict[tuple[str, str], Dispute]
) -> tuple[bool, Dispute | None]:
    """(withheld: every reason it's here is disputed feedback, the dispute to name or None). It's
    here because you saved it (from an interview's answer, or on its own) and for each answer since."""
    if not disputes:
        return False, None
    saved_dispute = held(row, disputes, saved_from)
    created = _aware(row.created_at)
    since = [held(row, disputes, a.id) for a in answers if a.at > created and a.id != saved_from]
    if saved_dispute is not None and all(d is not None for d in since):
        return True, saved_dispute
    return False, saved_dispute or next((d for d in since if d is not None), None)


@dataclass(frozen=True)
class Ladder:
    step: int
    reviews: int
    last_score: int | None
    scheduled_at: datetime
    due_at: datetime
    snoozed: bool
    created_at: datetime
    # Recounted because a dispute applies to an answer since it was saved: the disputes left out, and
    # the ladder as it stood counting them (what it would show without the recount).
    left_out: tuple[Dispute, ...] = ()
    counted_due_at: datetime | None = None
    counted_step: int | None = None

    def recount_note(self, now: datetime) -> str | None:
        """What changed, when a recount moved it: never earlier (or later) without saying why."""
        if not self.left_out or self.counted_due_at is None:
            return None
        was, is_ = _when(self.counted_due_at, now), _when(self.due_at, now)
        if was == is_:
            return None
        n = len(self.left_out)
        points = sorted({d.criterion for d in self.left_out if d.criterion != OVERALL})
        what = f"{count_words(n)} earlier score{'s' if n != 1 else ''} {'was' if n == 1 else 'were'} disputed"
        if points:
            what += f" (on “{points[0]}”, the point it was saved for)"
        if is_.startswith("in ") and was.startswith("in "):
            return f"Recounted: {what}, so it's due {is_}, not {was.removeprefix('in ').split(' ')[0]}."
        return f"Recounted: {what}, so it's due {is_}, not {was}."


def _when(at: datetime, now: datetime) -> str:
    days = math.ceil((at - now).total_seconds() / 86400)
    if days <= 0:
        return "now"
    return f"in {days} day{'s' if days != 1 else ''}"


def ladder(row: ReviewItem, answers: list[Answer], disputes: dict[tuple[str, str], Dispute]) -> Ladder:
    """The ladder an item shows. With no dispute on any answer since it was saved, it's the stored
    one (every answer counted, in order). Otherwise it's recounted from the item's answers since it
    was saved, oldest first, leaving out each one whose score is disputed for this item: the same
    rule whenever the answer was counted or the dispute made, so an item counted before this rule
    existed comes out the same as one counted after. A snooze still holds: the recount never brings
    it back before the date you snoozed it to. Withdrawing the dispute shows the stored ladder again."""
    created = _aware(row.created_at)
    stored = Ladder(
        step=row.step,
        reviews=row.reviews,
        last_score=row.last_score,
        scheduled_at=_aware(row.scheduled_at),
        due_at=_aware(row.due_at),
        snoozed=row.snoozed,
        created_at=created,
    )
    if not disputes:
        return stored
    since = [a for a in answers if a.at > created]
    left_out = tuple(d for a in since if (d := held(row, disputes, a.id)) is not None)
    if not left_out:
        return stored
    step, reviews, last, at = 0, 0, None, created
    for a in since:
        if held(row, disputes, a.id) is not None:
            continue
        step, reviews, last, at = _next_step(step, a.score), reviews + 1, a.score, a.at
    due = at + timedelta(days=LADDER[step])
    if row.snoozed:
        due = max(due, stored.due_at)
    return Ladder(
        step=step,
        reviews=reviews,
        last_score=last,
        scheduled_at=at,
        due_at=due,
        snoozed=row.snoozed and due == stored.due_at,
        created_at=created,
        left_out=left_out,
        counted_due_at=stored.due_at,
        counted_step=stored.step,
    )


@dataclass(frozen=True)
class QueueRead:
    row: ReviewItem
    ladder: Ladder
    withheld: bool
    dispute: Dispute | None
