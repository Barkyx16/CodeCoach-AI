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
    FollowInterviewIn,
    PrepEntryOut,
    PrepShiftIn,
    PrepShiftOut,
    PrepShiftResult,
    PrepTime,
    SchedulableOut,
    ScheduleSettingsIn,
    ScheduleSettingsOut,
)
from app.services import request_keys
from app.services.applications import not_over
from app.services.content import is_problem_retired
from app.services.ics import IcsEvent, calendar
from app.services.timeutil import local_to_utc, parse_hhmm, zone

MAX_ENTRIES = 500
MAX_RANGE_DAYS = 120


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo is not None else d.replace(tzinfo=UTC)


def _opt(d: datetime | None) -> datetime | None:
    return _aware(d) if d is not None else None


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
            follows_interview=e.anchor_at is not None,
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
        """A retry with the same client_request_id returns the entry the first made, even if it
        was moved since; the same key for another activity or time is a 409."""
        print_ = request_keys.fingerprint(
            "schedule.create", body.model_dump(mode="json", exclude={"client_request_id"})
        )
        if body.client_request_id and (existing := self._by_request(body.client_request_id)) is not None:
            request_keys.check(existing.request_fingerprint, print_, "schedule entry")
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
            request_fingerprint=print_ if body.client_request_id else None,
            status="scheduled",
            sequence=0,
        )
        self._apply_time(e, body.on_date, body.all_day, body.local_time, body.timezone, body.fold)
        self.db.add(e)
        try:
            self.db.commit()
        except IntegrityError:  # the same retry raced
            self.db.rollback()
            existing = self._by_request(body.client_request_id) if body.client_request_id else None
            if existing is None:
                raise
            request_keys.check(existing.request_fingerprint, print_, "schedule entry")
            return self.get(existing.id), False
        return self.get(e.id), True

    def _by_request(self, key: str) -> ScheduleEntry | None:
        return self.db.scalar(
            select(ScheduleEntry).where(
                ScheduleEntry.user_id == self.user.id, ScheduleEntry.client_request_id == key
            )
        )

    def move(self, entry_id: str, body: EntryMove) -> EntryOut:
        e = self._owned(entry_id)
        if e.status == "cancelled":
            raise ConflictError(
                "This entry was cancelled. Schedule the activity again instead.", code="entry_cancelled"
            )
        self._apply_time(e, body.on_date, body.all_day, body.local_time, body.timezone, body.fold)
        if e.anchor_at is not None:
            # Moved by hand: the new time is relative to the interview as it is now. An all-day time,
            # or an interview without an exact time, can't be kept relative: it becomes fixed.
            ev = self._prep_event(e)
            e.anchor_at = ev.starts_at if ev is not None and ev.starts_at and e.starts_at else None
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

    # --- interview preparation kept relative to its interview --------------------------------------
    #
    # Policy: preparation times are fixed. The learner can choose, per entry, to keep one relative
    # to its interview; that records the interview's start (the anchor). When the interview moves,
    # nothing changes until the learner previews and confirms: the selected entries keep the same
    # elapsed time before the interview (so across a daylight-saving change the clock time can
    # differ). Without exact times on both sides there's nothing to keep relative: the learner picks
    # a time. Completed and past preparation never moves.

    def _prep_event(self, e: ScheduleEntry) -> ApplicationEvent | None:
        if e.kind != "application_event":
            return None
        row = self.db.execute(
            select(ApplicationEvent)
            .join(Application)
            .where(ApplicationEvent.id == e.ref, Application.user_id == self.user.id)
        ).first()
        return row[0] if row else None

    def _owned_event(self, app_id: str, event_id: str) -> ApplicationEvent:
        row = self.db.execute(
            select(ApplicationEvent)
            .join(Application)
            .where(
                ApplicationEvent.id == event_id, Application.id == app_id, Application.user_id == self.user.id
            )
        ).first()
        if row is None:
            raise NotFoundError("Interview not found")
        return row[0]

    def follow_interview(self, entry_id: str, body: FollowInterviewIn) -> EntryOut:
        e = self._owned(entry_id)
        if e.sequence != body.expected_sequence:
            raise ConflictError(
                "This entry changed since you opened it. Nothing was changed.",
                code="stale_sequence",
                details={"current_sequence": e.sequence},
            )
        if not body.follows:
            e.anchor_at = None
        else:
            if e.kind != "application_event":
                raise AppError(
                    "Only interview preparation can follow an interview.", code="not_interview_prep"
                )
            if e.status == "cancelled":
                raise ConflictError("This entry was cancelled.", code="entry_cancelled")
            if e.starts_at is None:
                raise AppError(
                    "An all-day entry has no exact time to keep relative to the interview. Give it a time first.",
                    code="untimed_entry",
                )
            ev = self._prep_event(e)
            if ev is None:
                raise NotFoundError("Interview not found")
            if ev.starts_at is None:
                raise AppError(
                    "The interview has no exact time (date, time and time zone) yet, so there's nothing to "
                    "keep this relative to.",
                    code="interview_time_unknown",
                )
            e.anchor_at = ev.starts_at
        e.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(e.id)

    @staticmethod
    def _local(instant: datetime, tz: str) -> tuple[date, str, int]:
        local = instant.astimezone(zone(tz))
        return local.date(), local.strftime("%H:%M"), local.fold

    def _prep_entry(self, e: ScheduleEntry, ev: ApplicationEvent, now: datetime) -> PrepEntryOut:
        current = PrepTime(
            on_date=e.on_date,
            local_time=e.local_time,
            timezone=e.timezone,
            starts_at=e.starts_at,
            all_day=e.all_day,
        )
        proposal = None
        if e.anchor_at is None:
            status, note = "fixed", "A fixed time: it stays where it is."
        elif e.starts_at is None or not e.timezone:
            status, note = (
                "untimed",
                "An all-day entry: there's no exact time to keep relative. Move it yourself.",
            )
        elif ev.starts_at is None:
            status, note = (
                "interview_time_unknown",
                "The interview has no exact time now, so nothing is proposed. Move it yourself if you need to.",
            )
        elif _aware(e.anchor_at) == _aware(ev.starts_at):
            status, note = "aligned", "Already matches the interview's current time."
        elif _aware(e.starts_at) < now:
            status, note = "past", "This preparation time has passed, so it isn't moved."
        else:
            new_start = _aware(ev.starts_at) + (_aware(e.starts_at) - _aware(e.anchor_at))
            day, hhmm, _fold = self._local(new_start, e.timezone)
            proposal = PrepTime(on_date=day, local_time=hhmm, timezone=e.timezone, starts_at=new_start)
            if new_start < now:
                status, note = (
                    "would_be_past",
                    "The new time would already have passed. Choose a time yourself.",
                )
                proposal = None
            else:
                before = _aware(ev.starts_at) - new_start
                hours = before.total_seconds() / 3600
                gap = f"{hours:g} hours" if hours != 1 else "1 hour"
                same_clock = e.local_time == hhmm
                note = f"Keeps the same {gap} before the interview" + (
                    "."
                    if same_clock
                    else ". The clock time differs if a daylight-saving change is in between."
                )
                status = "can_move"
        return PrepEntryOut(
            id=e.id,
            title=e.title,
            sequence=e.sequence,
            follows_interview=e.anchor_at is not None,
            current=current,
            status=status,
            proposal=proposal,
            note=note,
        )

    def _prep_entries(self, ev: ApplicationEvent) -> list[ScheduleEntry]:
        return list(
            self.db.scalars(
                select(ScheduleEntry)
                .where(
                    ScheduleEntry.user_id == self.user.id,
                    ScheduleEntry.kind == "application_event",
                    ScheduleEntry.ref == ev.id,
                    ScheduleEntry.status == "scheduled",
                )
                .order_by(ScheduleEntry.on_date, ScheduleEntry.starts_at, ScheduleEntry.id)
            )
        )

    def prep_preview(self, app_id: str, event_id: str) -> PrepShiftOut:
        ev = self._owned_event(app_id, event_id)
        now = datetime.now(UTC)
        return PrepShiftOut(
            event_id=ev.id,
            event_title=ev.title,
            event_starts_at=ev.starts_at,
            event_on_date=ev.on_date,
            event_local_time=ev.local_time,
            event_timezone=ev.timezone,
            entries=[self._prep_entry(e, ev, now) for e in self._prep_entries(ev)],
        )

    def prep_shift(self, app_id: str, event_id: str, body: PrepShiftIn) -> PrepShiftResult:
        """Moves exactly the selected entries, all or none, against the preview the learner saw."""
        ev = self._owned_event(app_id, event_id)
        if _opt(ev.starts_at) != _opt(body.event_starts_at):
            raise ConflictError(
                "The interview's time changed again since this preview. Nothing was moved; review it again.",
                code="interview_changed",
                details={"event_starts_at": ev.starts_at.isoformat() if ev.starts_at else None},
            )
        now = datetime.now(UTC)
        entries = {e.id: e for e in self._prep_entries(ev)}
        moved: list[str] = []
        already: list[str] = []
        refused: list[dict[str, str | int]] = []
        plans: list[tuple[ScheduleEntry, PrepEntryOut]] = []
        for want in body.entries:
            e = entries.get(want.id)
            if e is None:
                refused.append({"id": want.id, "reason": "not_found"})
                continue
            p = self._prep_entry(e, ev, now)
            if p.status == "aligned":
                already.append(e.id)  # a resend after a lost response, or set by hand: it matches already
            elif e.sequence != want.sequence:
                refused.append({"id": e.id, "reason": "changed", "current_sequence": e.sequence})
            elif p.status != "can_move":
                refused.append({"id": e.id, "reason": p.status})
            else:
                plans.append((e, p))
        if refused:
            raise ConflictError(
                "Some of the chosen preparation can't be moved as previewed. Nothing was moved.",
                code="prep_not_movable",
                details={"entries": refused},
            )
        for e, p in plans:
            assert p.proposal is not None and p.proposal.starts_at is not None and e.timezone
            day, hhmm, fold = self._local(p.proposal.starts_at, e.timezone)
            e.on_date, e.local_time, e.fold, e.starts_at = day, hhmm, fold, p.proposal.starts_at
            e.anchor_at = ev.starts_at
            e.sequence += 1  # a downloaded calendar file updates the event when downloaded again
            e.updated_at = now
            moved.append(e.id)
        self.db.commit()
        return PrepShiftResult(
            moved=moved, already_aligned=already, preview=self.prep_preview(app_id, event_id)
        )

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
                    # Interview preparation kept relative to its interview: the interview start it
                    # was last aligned with (null: a fixed time).
                    "follows_interview_from": e.anchor_at.isoformat() if e.anchor_at else None,
                }
                for e in self.db.scalars(
                    select(ScheduleEntry)
                    .where(ScheduleEntry.user_id == self.user.id)
                    .order_by(ScheduleEntry.created_at, ScheduleEntry.id)
                )
            ],
        }
