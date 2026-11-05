"""Putting existing activities on a calendar the learner controls.

An entry is time set aside; it is never the work itself. Whether the activity was done comes
from the activity's own rules (a plan step marked done by the plan, an answer to the question or
a submission for the problem made after it was scheduled). Nothing here moves an entry by itself,
sends a reminder or invitation, or touches an outside calendar: a downloaded `.ics` file is the
only way out, and only for what the learner picked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.careers.questions import get_question, is_retired
from app.drills import BY_ID as DRILLS_BY_ID
from app.errors import AppError, ConflictError, NotFoundError
from app.models import (
    Application,
    ApplicationEvent,
    DrillAttempt,
    PlanItem,
    PracticeAnswer,
    PracticePlan,
    Problem,
    ReviewItem,
    ScheduleEntry,
    ScheduleSettings,
    Submission,
    User,
)
from app.schemas.schedule import (
    EntryIn,
    EntryMove,
    EntryOut,
    SchedulableOut,
    ScheduleSettingsIn,
    ScheduleSettingsOut,
)
from app.services.applications import not_over
from app.services.content import is_problem_retired
from app.services.ics import IcsEvent, calendar
from app.services.timeutil import local_to_utc, parse_hhmm, zone

MAX_ENTRIES = 500
MAX_RANGE_DAYS = 120


class Schedule:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- settings -----------------------------------------------------------------------------

    def settings(self) -> ScheduleSettingsOut:
        s = self.db.get(ScheduleSettings, self.user.id)
        if s is None:
            return ScheduleSettingsOut(
                timezone=None, reminders=False, reminder_minutes=10, quiet_start=None, quiet_end=None
            )
        return ScheduleSettingsOut(
            timezone=s.timezone,
            reminders=s.reminders,
            reminder_minutes=s.reminder_minutes,
            quiet_start=s.quiet_start,
            quiet_end=s.quiet_end,
        )

    def save_settings(self, body: ScheduleSettingsIn) -> ScheduleSettingsOut:
        s = self.db.get(ScheduleSettings, self.user.id)
        if s is None:
            if not body.timezone:
                raise AppError("Choose a time zone for your schedule first.", code="timezone_required")
            s = ScheduleSettings(
                user_id=self.user.id, timezone=body.timezone, reminders=False, reminder_minutes=10
            )
            self.db.add(s)
        data = body.model_dump(exclude_unset=True)
        if data.get("timezone"):
            zone(data["timezone"])
            s.timezone = data["timezone"]
        if data.get("reminders") is not None:
            s.reminders = data["reminders"]
        if data.get("reminder_minutes") is not None:
            s.reminder_minutes = data["reminder_minutes"]
        for f in ("quiet_start", "quiet_end"):
            if f in data:
                v = data[f] or None
                if v:
                    parse_hhmm(v)
                setattr(s, f, v)
        s.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.settings()

    # --- what an entry points at ----------------------------------------------------------------

    def _resolve(self, kind: str, ref: str) -> tuple[str, str | None, bool]:
        """(title, href, available) for an activity the learner owns, or 404."""
        if kind == "plan_item":
            item = self.db.scalar(
                select(PlanItem)
                .join(PracticePlan)
                .where(PlanItem.id == ref, PracticePlan.user_id == self.user.id)
            )
            if item is None:
                raise NotFoundError("Plan step not found")
            return item.title, "/plan", item.status in ("pending", "done")
        if kind == "review_item":
            r = self.db.scalar(
                select(ReviewItem).where(ReviewItem.id == ref, ReviewItem.user_id == self.user.id)
            )
            if r is None:
                raise NotFoundError("Review not found")
            q = get_question(r.track, r.question_id)
            title = f"Review: {q.title}" if q else "Review a question"
            return (
                title,
                f"/careers/{r.track}/questions/{r.question_id}",
                not r.removed and not is_retired(r.track, r.question_id),
            )
        if kind == "question":
            track, _, qid = ref.partition("/")
            q = get_question(track, qid)
            if q is None:
                raise NotFoundError("Question not found")
            return q.title, f"/careers/{track}/questions/{qid}", not is_retired(track, qid)
        if kind == "problem":
            p = self.db.scalar(select(Problem).where(Problem.slug == ref))
            if p is None:
                raise NotFoundError("Problem not found")
            return p.title, f"/problems/{p.slug}", not is_problem_retired(p.slug)
        if kind == "drill":
            drill = DRILLS_BY_ID.get(ref)
            if drill is None:
                raise NotFoundError("Drill not found")
            return f"Drill: {drill.title}", f"/drills/{ref}", True
        if kind == "application_event":
            row = self.db.execute(
                select(ApplicationEvent, Application)
                .join(Application)
                .where(ApplicationEvent.id == ref, Application.user_id == self.user.id)
            ).first()
            if row is None:
                raise NotFoundError("Event not found")
            ev, app = row
            # Preparing for an interview happens in its kit (which links back to the application).
            return f"Prepare: {ev.title} ({app.employer})", f"/applications/{app.id}/events/{ev.id}/kit", True
        raise AppError("Unknown kind.", code="unknown_kind")  # pragma: no cover - the schema limits it

    def _done_at(self, e: ScheduleEntry) -> datetime | None:
        """When the activity was actually done, by its own rules. Scheduling never counts."""
        if e.kind == "plan_item":
            item = self.db.get(PlanItem, e.ref)
            return item.resolved_at if item is not None and item.status == "done" else None
        if e.kind in ("question", "review_item"):
            if e.kind == "review_item":
                r = self.db.get(ReviewItem, e.ref)
                if r is None:
                    return None
                track, qid = r.track, r.question_id
            else:
                track, _, qid = e.ref.partition("/")
            return self.db.scalar(
                select(func.min(PracticeAnswer.created_at)).where(
                    PracticeAnswer.user_id == self.user.id,
                    PracticeAnswer.track == track,
                    PracticeAnswer.question_id == qid,
                    PracticeAnswer.created_at >= e.created_at,
                )
            )
        if e.kind == "drill":
            return self.db.scalar(
                select(func.min(DrillAttempt.created_at)).where(
                    DrillAttempt.user_id == self.user.id,
                    DrillAttempt.drill_id == e.ref,
                    DrillAttempt.created_at >= e.created_at,
                )
            )
        if e.kind == "problem":
            return self.db.scalar(
                select(func.min(Submission.created_at))
                .join(Problem, Problem.id == Submission.problem_id)
                .where(
                    Submission.user_id == self.user.id,
                    Problem.slug == e.ref,
                    Submission.created_at >= e.created_at,
                )
            )
        return None

    def _out(self, e: ScheduleEntry, conflicts: list[str]) -> EntryOut:
        try:
            _, href, available = self._resolve(e.kind, e.ref)
        except NotFoundError:
            href, available = None, False
        ends = e.starts_at + timedelta(minutes=e.duration_min) if e.starts_at else None
        return EntryOut(
            id=e.id,
            uid=e.uid,
            kind=e.kind,
            ref=e.ref,
            title=e.title,
            href=href,
            all_day=e.all_day,
            on_date=e.on_date,
            local_time=e.local_time,
            timezone=e.timezone,
            starts_at=e.starts_at,
            ends_at=ends,
            duration_min=e.duration_min,
            status=e.status,
            done_at=self._done_at(e),
            available=available,
            conflicts=conflicts,
            sequence=e.sequence,
            notes=e.notes,
            created_at=e.created_at,
        )

    @staticmethod
    def _conflicts(entries: list[ScheduleEntry]) -> dict[str, list[str]]:
        """Overlapping timed entries. Explained to the learner; never moved for them."""
        timed = [e for e in entries if e.status == "scheduled" and e.starts_at is not None]
        out: dict[str, list[str]] = {e.id: [] for e in entries}
        for i, a in enumerate(timed):
            a_end = a.starts_at + timedelta(minutes=a.duration_min)  # type: ignore[operator]
            for b in timed[i + 1 :]:
                b_end = b.starts_at + timedelta(minutes=b.duration_min)  # type: ignore[operator]
                if a.starts_at < b_end and b.starts_at < a_end:  # type: ignore[operator]
                    out[a.id].append(b.id)
                    out[b.id].append(a.id)
        return out

    # --- reads ------------------------------------------------------------------------------------

    def _owned(self, entry_id: str) -> ScheduleEntry:
        e = self.db.get(ScheduleEntry, entry_id)
        if e is None or e.user_id != self.user.id:
            raise NotFoundError("Schedule entry not found")
        return e

    def _range(self, start: date, end: date, include_cancelled: bool) -> list[ScheduleEntry]:
        if end < start or (end - start).days > MAX_RANGE_DAYS:
            raise AppError(f"Ask for up to {MAX_RANGE_DAYS} days at a time.", code="invalid_range")
        q = select(ScheduleEntry).where(
            ScheduleEntry.user_id == self.user.id,
            # A day either side: an entry's own date can differ from the day it falls on where you are.
            ScheduleEntry.on_date >= start - timedelta(days=1),
            ScheduleEntry.on_date <= end + timedelta(days=1),
        )
        if not include_cancelled:
            q = q.where(ScheduleEntry.status == "scheduled")
        return list(self.db.scalars(q.order_by(ScheduleEntry.on_date, ScheduleEntry.starts_at)).all())

    def between(self, start: date, end: date, include_cancelled: bool = False) -> list[EntryOut]:
        rows = self._range(start, end, include_cancelled)
        conflicts = self._conflicts(rows)
        return [self._out(e, conflicts[e.id]) for e in rows]

    def get(self, entry_id: str) -> EntryOut:
        e = self._owned(entry_id)
        same_day = self._range(e.on_date, e.on_date, False)
        return self._out(e, self._conflicts([*same_day, *([e] if e not in same_day else [])]).get(e.id, []))

    def schedulable(self) -> list[SchedulableOut]:
        """Your current plan's open steps, reviews that are due soon, and upcoming interviews."""
        out: list[SchedulableOut] = []
        plan = self.db.scalar(
            select(PracticePlan)
            .where(PracticePlan.user_id == self.user.id, PracticePlan.track == self.user.career_track)
            .order_by(PracticePlan.version.desc())
        )
        if plan is not None:
            for item in plan.items:
                if item.status == "pending":
                    out.append(
                        SchedulableOut(
                            kind="plan_item",
                            ref=item.id,
                            title=item.title,
                            detail="From your plan",
                            minutes=item.minutes,
                        )
                    )
        soon = datetime.now(UTC) + timedelta(days=14)
        for r in self.db.scalars(
            select(ReviewItem)
            .where(
                ReviewItem.user_id == self.user.id, ReviewItem.removed.is_(False), ReviewItem.due_at <= soon
            )
            .order_by(ReviewItem.due_at)
            .limit(20)
        ):
            q = get_question(r.track, r.question_id)
            if q is not None:
                out.append(
                    SchedulableOut(
                        kind="review_item",
                        ref=r.id,
                        title=f"Review: {q.title}",
                        detail="From your review queue",
                        minutes=10,
                    )
                )
        now = datetime.now(UTC)
        for ev, app in self.db.execute(
            select(ApplicationEvent, Application)
            .join(Application)
            .where(Application.user_id == self.user.id, Application.archived.is_(False))
        ).all():
            # Undated events can be prepared for; dated ones until they're over (same rule as an
            # application's next event, not the server's own date).
            if ev.on_date is None or not_over(ev, now):
                out.append(
                    SchedulableOut(
                        kind="application_event",
                        ref=ev.id,
                        title=f"Prepare: {ev.title} ({app.employer})",
                        detail=f"For your application to {app.role_title}",
                        minutes=60,
                    )
                )
        return out

    # --- writes -------------------------------------------------------------------------------

    def _apply_time(
        self,
        e: ScheduleEntry,
        on_date: date,
        all_day: bool,
        local_time: str | None,
        tz: str | None,
        fold: int | None,
    ) -> None:
        e.on_date = on_date
        e.all_day = all_day
        if all_day:
            e.local_time = e.timezone = None
            e.fold = None
            e.starts_at = None
            return
        if not local_time or not tz:
            raise AppError(
                "A timed entry needs a time and a time zone (or make it all-day).", code="time_required"
            )
        e.starts_at = local_to_utc(
            on_date, local_time, tz, fold
        )  # refuses impossible times, asks about repeated ones
        e.local_time, e.timezone, e.fold = local_time, tz, fold

    def create(self, body: EntryIn) -> tuple[EntryOut, bool]:
        if body.client_request_id:
            existing = self.db.scalar(
                select(ScheduleEntry).where(
                    ScheduleEntry.user_id == self.user.id,
                    ScheduleEntry.client_request_id == body.client_request_id,
                )
            )
            if existing is not None:
                return self.get(existing.id), False
        n = (
            self.db.scalar(
                select(func.count()).select_from(ScheduleEntry).where(ScheduleEntry.user_id == self.user.id)
            )
            or 0
        )
        if n >= MAX_ENTRIES:
            raise AppError(f"Up to {MAX_ENTRIES} schedule entries.", code="too_many_entries")
        title, _, available = self._resolve(body.kind, body.ref)
        if not available:
            raise ConflictError("That activity isn't available for practice any more.", code="not_available")
        e = ScheduleEntry(
            user_id=self.user.id,
            uid=f"{uuid.uuid4()}@codecoach",
            kind=body.kind,
            ref=body.ref,
            title=title[:200],
            duration_min=body.duration_min,
            notes=body.notes.strip(),
            client_request_id=body.client_request_id,
            status="scheduled",
            sequence=0,
        )
        self._apply_time(e, body.on_date, body.all_day, body.local_time, body.timezone, body.fold)
        self.db.add(e)
        try:
            self.db.commit()
        except IntegrityError:  # the same retry raced
            self.db.rollback()
            existing = self.db.scalar(
                select(ScheduleEntry).where(
                    ScheduleEntry.user_id == self.user.id,
                    ScheduleEntry.client_request_id == body.client_request_id,
                )
            )
            if existing is None:
                raise
            return self.get(existing.id), False
        return self.get(e.id), True

    def move(self, entry_id: str, body: EntryMove) -> EntryOut:
        e = self._owned(entry_id)
        if e.status == "cancelled":
            raise ConflictError(
                "This entry was cancelled. Schedule the activity again instead.", code="entry_cancelled"
            )
        self._apply_time(e, body.on_date, body.all_day, body.local_time, body.timezone, body.fold)
        if body.duration_min is not None:
            e.duration_min = body.duration_min
        if body.notes is not None:
            e.notes = body.notes.strip()
        e.sequence += 1
        e.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(e.id)

    def cancel(self, entry_id: str) -> EntryOut:
        e = self._owned(entry_id)
        if e.status != "cancelled":  # a repeated cancel changes nothing
            e.status = "cancelled"
            e.sequence += 1
            e.updated_at = datetime.now(UTC)
            self.db.commit()
        return self.get(e.id)

    # --- calendar file ----------------------------------------------------------------------------

    def ics(self, ids: list[str] | None, start: date | None, end: date | None, base_url: str) -> str:
        if ids:
            rows = [self._owned(i) for i in dict.fromkeys(ids)]
        elif start and end:
            rows = [e for e in self._range(start, end, include_cancelled=True) if start <= e.on_date <= end]
        else:
            raise AppError("Choose entries or a date range to export.", code="nothing_selected")
        events = [
            IcsEvent(
                uid=e.uid,
                sequence=e.sequence,
                summary=f"CodeCoach: {e.title}",
                status="CANCELLED" if e.status == "cancelled" else "CONFIRMED",
                all_day=e.all_day,
                on_date=e.on_date,
                starts_at=e.starts_at,
                minutes=e.duration_min,
                url=f"{base_url.rstrip('/')}/schedule",
                description="Practice time you set aside in CodeCoach.",
            )
            for e in rows
        ]
        return calendar(events)

    def export(self, *, with_ids: bool = False) -> dict:
        return {
            "settings": self.settings().model_dump(),
            "entries": [
                {
                    **({"id": e.id} if with_ids else {}),
                    "kind": e.kind,
                    "ref": e.ref,
                    "title": e.title,
                    "all_day": e.all_day,
                    "date": e.on_date.isoformat(),
                    "time": e.local_time,
                    "timezone": e.timezone,
                    "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                    "duration_min": e.duration_min,
                    "status": e.status,
                    "notes": e.notes,
                }
                for e in self.db.scalars(
                    select(ScheduleEntry)
                    .where(ScheduleEntry.user_id == self.user.id)
                    .order_by(ScheduleEntry.created_at, ScheduleEntry.id)
                )
            ],
        }
