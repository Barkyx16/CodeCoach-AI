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
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.careers import CATALOG
from app.careers.questions import get_question
from app.errors import AppError, ConflictError, NotFoundError
from app.models import InterviewTurn, PracticeAnswer, PracticeSession, ReviewItem, User
from app.schemas.review import RemovedPoint, RemovedReviewItem, ReviewAdd, ReviewQueue, ReviewQueueItem
from app.services.disputes import OVERALL, Dispute, Disputes, count_words, covering, note, overall

LADDER = (1, 3, 7, 14, 30)
MAX_ACTIVE = 100
# Recent removals listed to put back (Volume 19, prompt 2): the last 30 days, at most 20.
REMOVED_DAYS = 30
REMOVED_LIMIT = 20


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


def saved_points(row: ReviewItem) -> list[str]:
    """Every point an item was saved for, in the order added; [] for the whole answer. An item from
    before Volume 16, prompt 5 has its one point in `criterion` and no `points`: read as that point."""
    if row.points is not None:
        return [p for p in row.points if isinstance(p, str) and p]
    return [row.criterion] if row.criterion else []


def removed_points(row: ReviewItem) -> list[tuple[str, datetime]]:
    """Each point taken off an item, with when (Volume 17, prompt 8), oldest first."""
    out: list[tuple[str, datetime]] = []
    for e in row.removed_points or []:
        if not isinstance(e, dict) or not isinstance(e.get("point"), str):
            continue
        try:
            at = datetime.fromisoformat(str(e.get("at")))
        except ValueError:
            continue
        out.append((e["point"], _aware(at)))
    return out


def _quoted(points: list[str]) -> str:
    q = [f"“{p}”" for p in points]
    return q[0] if len(q) == 1 else ", ".join(q[:-1]) + " and " + q[-1]


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
        # Saved again: another point is added to the item (Volume 16, prompt 5); with no point, it's
        # now saved for the whole answer. The same point again changes nothing.
        point = _point(body.criterion)
        have = saved_points(existing)
        said = None
        if not have:
            said = "It's already saved for the whole answer, which covers every point." if point else None
        elif point is None:
            existing.points, existing.criterion = [], None
            said = "It's now saved for the whole answer, not only for " + _quoted(have) + "."
        elif point not in have:
            existing.points = [*have, point]
            existing.criterion = have[0]
            said = f"Added “{point}” to the points it's saved for."
        self.db.commit()
        out = self.queue(user)
        out.saved = said
        return out

    def remove_point(self, user: User, item_id: str, point: str) -> ReviewQueue:
        """Take one point off an item saved for several, keeping the item and the others. Its scores
        disputed only on that point count again."""
        row = self._item(user, item_id)
        have = saved_points(row)
        text = _point(point)
        if text not in have:
            raise NotFoundError("It isn't saved for that point.")
        if len(have) == 1:
            raise ConflictError(
                "It's the only point it's saved for: removing it removes the question from the queue.",
                code="last_point",
            )
        rest = [p for p in have if p != text]
        row.points, row.criterion = rest, rest[0]
        # Kept in its history with when (Volume 17, prompt 8): its ladder and other points are untouched.
        row.removed_points = [*(row.removed_points or []), {"point": text, "at": _now().isoformat()}]
        self.db.commit()
        return self.queue(user)

    def restore(self, user: User, item_id: str) -> ReviewQueue:
        """Undo a removal (Volume 17, prompt 8): the question back as it was, its ladder, points and
        history. Refused once the question was saved again (it's in the queue as another item) or the
        queue is full; another account's item is not found."""
        row = self.db.get(ReviewItem, item_id)
        if row is None or row.user_id != user.id:
            raise NotFoundError("Review item not found")
        if not row.removed:
            return self.queue(user)
        again = self.db.scalar(
            select(ReviewItem.id).where(
                ReviewItem.user_id == user.id,
                ReviewItem.track == row.track,
                ReviewItem.question_id == row.question_id,
                ReviewItem.removed.is_(False),
            )
        )
        if again is not None:
            raise ConflictError(
                "It's back in your review queue already: it was saved again.", code="already_in_queue"
            )
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
        row.removed = False
        row.removed_at = None
        self.db.commit()
        return self.queue(user)

    def removed_recently(self, user: User) -> list[RemovedReviewItem]:
        """Questions taken out of the queue that can be put back (Volume 19, prompt 2): removed in the
        last REMOVED_DAYS days, newest first, then removals from before their time was kept, up to
        REMOVED_LIMIT in all; one that was saved again since (it's in the queue as another item) isn't
        listed. One statement."""
        again = aliased(ReviewItem)
        since = _now() - timedelta(days=REMOVED_DAYS)
        rows = self.db.scalars(
            select(ReviewItem)
            .where(
                ReviewItem.user_id == user.id,
                ReviewItem.removed.is_(True),
                or_(ReviewItem.removed_at >= since, ReviewItem.removed_at.is_(None)),
                ~exists().where(
                    again.user_id == user.id,
                    again.track == ReviewItem.track,
                    again.question_id == ReviewItem.question_id,
                    again.removed.is_(False),
                ),
            )
            .order_by(ReviewItem.removed_at.desc().nulls_last(), ReviewItem.created_at.desc())
            .limit(REMOVED_LIMIT)
        ).all()
        out = []
        for row in rows:
            q = get_question(row.track, row.question_id)
            out.append(
                RemovedReviewItem(
                    id=row.id,
                    track=row.track,
                    career_title=CATALOG[row.track].title if row.track in CATALOG else row.track,
                    question_id=row.question_id,
                    title=q.title if q else "A question that's no longer in the library",
                    href=f"/careers/{row.track}/questions/{row.question_id}",
                    removed_at=row.removed_at,
                    points=saved_points(row),
                )
            )
        return out

    def snooze(self, user: User, item_id: str, days: int) -> ReviewQueue:
        row = self._item(user, item_id)
        row.due_at = max(_aware(row.due_at), _now()) + timedelta(days=days)
        row.snoozed = True
        self.db.commit()
        return self.queue(user)

    def remove(self, user: User, item_id: str) -> ReviewQueue:
        row = self._item(user, item_id)
        row.removed = True
        row.removed_at = _now()  # so it can be put back after a reload (Volume 19, prompt 2)
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
                    else f"an interview answer, for “{dispute.criterion}”, and you disputed that point"
                )
                why = (
                    f"Not scheduled: you saved it from {what} {dispute.when}, and that's the only reason it's here. "
                    "Count that feedback again to put it back, or answer it any time."
                )
            elif dispute is not None:
                which = (
                    "feedback you disputed"
                    if dispute.criterion == OVERALL
                    else f"your dispute of “{dispute.criterion}”"
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
                points=saved_points(row),
                recounted=recounted,
                removed_points=[RemovedPoint(point=p, removed_at=at) for p, at in removed_points(row)],
                released=lad.released_note(),
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
    points = saved_points(row)
    if points:  # a dispute on any of the points it was saved for (Volume 16, prompt 5)
        return next((d for p in points if (d := covering(disputes, answer_id, p)) is not None), None)
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
    # The points it's saved for now (Volume 17, prompt 8), so the recount names them.
    saved: tuple[str, ...] = ()
    # Points taken off it whose dispute would have held a score back: (point, when removed, scores).
    released: tuple[tuple[str, datetime, int], ...] = ()

    def released_note(self) -> str | None:
        """Why a disputed score counts again: the point it was disputed on was taken off."""
        if not self.released:
            return None
        return " ".join(
            f"“{p}” was taken off on {_day(at)}, so {count_words(n)} disputed score{'s' if n != 1 else ''} "
            f"on it count{'s' if n == 1 else ''} again."
            for p, at, n in self.released
        )

    def recount_note(self, now: datetime) -> str | None:
        """What changed, when a recount moved it: never earlier (or later) without saying why."""
        if not self.left_out or self.counted_due_at is None:
            return None
        was, is_ = _when(self.counted_due_at, now), _when(self.due_at, now)
        if was == is_:
            return None
        n = len(self.left_out)
        # The disputed points it left out, in the order they were disputed (Volume 17, prompt 8).
        points: list[str] = []
        for d in sorted(self.left_out, key=lambda d: (d.disputed_at or self.created_at, d.flag_id)):
            if d.criterion != OVERALL and d.criterion not in points:
                points.append(d.criterion)
        what = f"{count_words(n)} earlier score{'s' if n != 1 else ''} {'was' if n == 1 else 'were'} disputed"
        saved = list(self.saved)
        if len(points) == 1 and len(saved) <= 1:
            what += f" (on “{points[0]}”, the point it was saved for)"
        elif points and len(saved) > 1:
            rest = [p for p in saved if p not in points]
            if rest:
                which = "one of the points" if len(points) == 1 else "points"
                what += f" (on {_quoted(points)}, {which} it's saved for; it stays for {_quoted(rest)})"
            else:
                what += f" (on {_quoted(points)}, every point it's saved for)"
        elif points:  # each disputed point it left out (Volume 16, prompt 5)
            what += f", on {_quoted(points)}"
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
    saved = tuple(saved_points(row))
    # A point taken off no longer holds a score back (Volume 17, prompt 8); say so where it would have.
    released: list[tuple[str, datetime, int]] = []
    latest_removal: dict[str, datetime] = {}
    for p, at in removed_points(row):
        if p not in saved:
            latest_removal[p] = at
    for p, at in latest_removal.items():
        n = sum(
            1 for a in since if covering(disputes, a.id, p) is not None and held(row, disputes, a.id) is None
        )
        if n:
            released.append((p, at, n))
    stored = replace(stored, saved=saved, released=tuple(released))
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
        saved=saved,
        released=tuple(released),
    )


@dataclass(frozen=True)
class QueueRead:
    row: ReviewItem
    ladder: Ladder
    withheld: bool
    dispute: Dispute | None
