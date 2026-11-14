"""Accepted improvements (Volume 12, prompt 1; docs/ACCEPTED_ACTIONS.md).

One accepted suggestion is one action with one id. The plan page lists it beside the plan (the
plan's own adaptation is untouched), its occurrences are schedule entries pointing at it, and an
interview kit's checklist can hold it by id. None of those copies its text or its state.

Kept apart: a suggestion (an interview review's improvement, worked out from the feedback each time
the review is read, never stored), the accepted action (this), its occurrences (schedule entries),
the practice actually done (the attempts' own tables, counted, never edited) and completion, which
the learner states: on the action for a one-off, on each occurrence for a weekly one. Completing
an action changes no score and claims nothing about mastery.

Accepting the same suggestion again finds the same row: the suggestion's identity (the interview
and the improvement's key) is unique per account, so a double click, a second tab or a resend after
a lost reply returns the action already made. Edits are checked against the revision the page
loaded, with update receipts for a save whose reply was lost (docs/RECOVERY.md). Another account's
ids are 404, the same as ids that don't exist.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.db.locking import lock_for_update
from app.errors import AppError, ConflictError, NotFoundError
from app.models import (
    AcceptedAction,
    InterviewRetry,
    PracticeSession,
    Problem,
    ScheduleEntry,
    Submission,
    User,
)
from app.schemas.actions import (
    ActionAccept,
    ActionOut,
    ActionSource,
    ActionUpdate,
    ActionVersion,
    OccurrenceOut,
    OccurrencesIn,
)
from app.schemas.common import SaveReplay
from app.services import request_keys, update_receipts
from app.services.review import InterviewReviews
from app.services.schedule import MAX_ENTRIES, Schedule

KIND = "interview_improvement"
_RETRY = re.compile(r"^/interviews/([^/]+)/retry/(\d+)$")
_PROBLEM = re.compile(r"^/problems/([a-z0-9-]+)$")


def clean(text: str) -> str:
    return " ".join(text.split())


class Actions:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- reads ------------------------------------------------------------------------------------

    def _find(self, action_id: str, *, lock: bool = False) -> AcceptedAction:
        row = self.db.scalar(
            select(AcceptedAction).where(
                AcceptedAction.id == action_id, AcceptedAction.user_id == self.user.id
            )
        )
        if row is None:
            raise NotFoundError("Action not found")
        return lock_for_update(self.db, row) if lock else row

    def _occurrences(self, action_id: str) -> list[ScheduleEntry]:
        return list(
            self.db.scalars(
                select(ScheduleEntry)
                .where(
                    ScheduleEntry.user_id == self.user.id,
                    ScheduleEntry.kind == "accepted_action",
                    ScheduleEntry.ref == action_id,
                )
                .order_by(ScheduleEntry.on_date, ScheduleEntry.starts_at, ScheduleEntry.created_at)
            )
        )

    def _attempts_since(self, row: AcceptedAction) -> int | None:
        """Practice of the action's target since it was accepted, by the attempts' own records."""
        href = row.practice_href or ""
        if m := _RETRY.match(href):
            return (
                self.db.scalar(
                    select(func.count())
                    .select_from(InterviewRetry)
                    .where(
                        InterviewRetry.user_id == self.user.id,
                        InterviewRetry.session_id == m.group(1),
                        InterviewRetry.question_index == int(m.group(2)),
                        InterviewRetry.created_at >= row.created_at,
                    )
                )
                or 0
            )
        if m := _PROBLEM.match(href):
            return (
                self.db.scalar(
                    select(func.count())
                    .select_from(Submission)
                    .join(Problem, Problem.id == Submission.problem_id)
                    .where(
                        Submission.user_id == self.user.id,
                        Problem.slug == m.group(1),
                        Submission.created_at >= row.created_at,
                    )
                )
                or 0
            )
        return None

    def _out(self, row: AcceptedAction, replay: SaveReplay | None = None) -> ActionOut:
        src = row.source or {}
        available = (
            self.db.scalar(
                select(func.count())
                .select_from(PracticeSession)
                .where(PracticeSession.id == row.source_id, PracticeSession.user_id == self.user.id)
            )
            or 0
        ) > 0
        occurrences = [
            OccurrenceOut(
                id=e.id,
                on_date=e.on_date,
                all_day=e.all_day,
                local_time=e.local_time,
                timezone=e.timezone,
                starts_at=e.starts_at,
                status="cancelled" if e.status == "cancelled" else "scheduled",
                sequence=e.sequence,
                completed_at=(row.done_at if row.recurrence == "once" else e.completed_at)
                if e.status != "cancelled"
                else None,
            )
            for e in self._occurrences(row.id)
        ]
        return ActionOut(
            id=row.id,
            title=row.title,
            notes=row.notes,
            practice_href=row.practice_href,
            practice_label=src.get("practice_label"),
            recurrence="weekly" if row.recurrence == "weekly" else "once",
            status="done" if row.recurrence == "once" and row.done_at is not None else "open",
            done_at=row.done_at,
            source=ActionSource(
                kind=KIND,
                interview_id=row.source_id,
                key=row.source_key,
                label=src.get("label", row.title),
                why=src.get("why", ""),
                interview_title=src.get("interview_title", "An interview"),
                interview_date=datetime.fromisoformat(src["interview_date"])
                if src.get("interview_date")
                else None,
                versions=[ActionVersion(**v) for v in src.get("versions") or []],
                available=available,
            ),
            occurrences=occurrences,
            attempts_since=self._attempts_since(row),
            revision=row.revision,
            save_replay=replay,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def mine(self, status: str = "all") -> list[ActionOut]:
        rows = self.db.scalars(
            select(AcceptedAction)
            .where(AcceptedAction.user_id == self.user.id)
            .order_by(AcceptedAction.created_at.desc(), AcceptedAction.id)
        )
        out = [self._out(r) for r in rows]
        return [a for a in out if status == "all" or a.status == status]

    def get(self, action_id: str) -> ActionOut:
        return self._out(self._find(action_id))

    # --- accepting --------------------------------------------------------------------------------

    def _existing(self, interview_id: str, key: str) -> AcceptedAction | None:
        return self.db.scalar(
            select(AcceptedAction).where(
                AcceptedAction.user_id == self.user.id,
                AcceptedAction.source_kind == KIND,
                AcceptedAction.source_id == interview_id,
                AcceptedAction.source_key == key,
            )
        )

    def accept(self, body: ActionAccept) -> tuple[ActionOut, bool]:
        """The action for this suggestion: made now (True), or the one made before (False)."""
        src = body.source
        session = self.db.scalar(
            select(PracticeSession).where(
                PracticeSession.id == src.interview_id, PracticeSession.user_id == self.user.id
            )
        )
        if session is None:
            raise NotFoundError("Interview not found")
        if (existing := self._existing(src.interview_id, src.key)) is not None:
            return self._out(existing), False
        # The suggestion is read from the review as the server builds it now: what the page sent
        # is only which one, never its text.
        review = InterviewReviews(self.db).build(self.user, session)
        imp = next((i for i in review.improvements if i.key == src.key), None)
        if imp is None:
            raise NotFoundError("That improvement isn't in this interview's review.")
        items = {i.key: i for i in review.items}
        versions = []
        for ev in imp.evidence:
            item = items.get(ev.item_key)
            if item is not None and item.feedback is not None:
                versions.append({"question": item.title, "version": item.feedback.content_version})
        if review.problem is not None:
            interview_title = f"Coding interview: {review.problem.title}"
        else:
            interview_title = f"{review.career_title or 'Practice'} interview"
        href = imp.practice.href
        if href is None and imp.practice.retry_index is not None:
            href = f"/interviews/{session.id}/retry/{imp.practice.retry_index}"
        now = datetime.now(UTC)
        row = AcceptedAction(
            user_id=self.user.id,
            source_kind=KIND,
            source_id=session.id,
            source_key=src.key,
            source={
                "label": imp.title,
                "why": imp.why,
                "interview_title": interview_title,
                "interview_date": review.started_at.isoformat(),
                "versions": versions,
                "practice_label": imp.practice.label,
            },
            title=imp.title[:200],
            notes="",
            practice_href=href,
            recurrence=body.recurrence,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:  # the same suggestion accepted at the same moment (another tab)
            self.db.rollback()
            existing = self._existing(src.interview_id, src.key)
            if existing is None:
                raise
            return self._out(existing), False
        return self._out(row), True

    # --- editing ----------------------------------------------------------------------------------

    def _stale(self, action_id: str) -> ConflictError:
        self.db.rollback()
        current = self.get(action_id)
        return ConflictError(
            "This action was changed somewhere else (maybe another tab) since you opened it. "
            "Your changes weren't saved; they're still on this page.",
            code="stale_revision",
            details={"current_revision": current.revision, "current": current.model_dump(mode="json")},
        )

    def update(self, action_id: str, body: ActionUpdate) -> ActionOut:
        """Rename it or change its notes against the revision the page loaded. A save whose reply
        was lost, sent again with its key, is answered as having gone through; a stale one is 409
        with the saved action so both can be shown."""
        row = self._find(action_id, lock=True)
        data = body.model_dump(
            mode="json", exclude={"client_request_id", "expected_revision"}, exclude_none=True
        )
        key = body.client_request_id
        print_ = update_receipts.fingerprint("action", action_id, body.expected_revision, data)
        done = update_receipts.find(
            self.db, self.user, key, "action", action_id, body.expected_revision, print_
        )
        if done is not None:
            return self._out(
                row, SaveReplay(accepted_revision=done.accepted_revision, current_revision=row.revision)
            )
        if body.expected_revision != row.revision:
            raise self._stale(action_id)
        if body.title is not None:
            title = clean(body.title)
            if not title:
                raise AppError("Give the action a name.", code="missing_title")
            row.title = title[:200]
        if body.notes is not None:
            row.notes = body.notes.strip()
        if body.recurrence is not None and body.recurrence != row.recurrence:
            # Changing what an occurrence means once it exists would rewrite history: refused.
            if any(e.status != "cancelled" for e in self._occurrences(row.id)):
                raise ConflictError(
                    "It's on your schedule: cancel those entries first, or keep it as it is.",
                    code="has_occurrences",
                )
            if row.done_at is not None:
                raise ConflictError("It's marked done: mark it not done first.", code="action_done")
            row.recurrence = body.recurrence
        row.updated_at = datetime.now(UTC)
        try:
            self.db.flush()  # the revision moves here, only if nobody else moved it first
            update_receipts.record(
                self.db, self.user, key, "action", action_id, body.expected_revision, row.revision, print_
            )
            self.db.commit()
        except (StaleDataError, IntegrityError):
            self.db.rollback()
            done = update_receipts.find(
                self.db, self.user, key, "action", action_id, body.expected_revision, print_
            )
            if done is not None:
                row = self._find(action_id)
                return self._out(
                    row, SaveReplay(accepted_revision=done.accepted_revision, current_revision=row.revision)
                )
            raise self._stale(action_id) from None
        return self._out(row)

    # --- completion -------------------------------------------------------------------------------

    def _set_done(self, row: AcceptedAction, done: bool) -> None:
        if row.recurrence != "once":
            raise ConflictError(
                "A weekly action is done one occurrence at a time: mark the occurrence on its date.",
                code="weekly_action",
            )
        if done and row.done_at is None:
            row.done_at = datetime.now(UTC)
        elif not done and row.done_at is not None:
            row.done_at = None
        else:
            return  # already so: nothing changes, not even the revision
        row.updated_at = datetime.now(UTC)
        try:
            self.db.commit()
        except StaleDataError:  # another tab changed it first; its state stands
            self.db.rollback()

    def complete(self, action_id: str) -> ActionOut:
        row = self._find(action_id, lock=True)
        self._set_done(row, True)
        return self.get(action_id)

    def reopen(self, action_id: str) -> ActionOut:
        row = self._find(action_id, lock=True)
        self._set_done(row, False)
        return self.get(action_id)

    def _occurrence(self, row: AcceptedAction, entry_id: str) -> ScheduleEntry:
        e = self.db.get(ScheduleEntry, entry_id)
        if e is None or e.user_id != self.user.id or e.kind != "accepted_action" or e.ref != row.id:
            raise NotFoundError("Occurrence not found")
        return e

    def complete_occurrence(self, action_id: str, entry_id: str, done: bool) -> ActionOut:
        """Done (or not) for one occurrence. A one-off's occurrence is the action itself; a weekly
        action's others stay as they are."""
        row = self._find(action_id, lock=True)
        e = self._occurrence(row, entry_id)
        if e.status == "cancelled":
            raise ConflictError("This occurrence was cancelled.", code="occurrence_cancelled")
        if row.recurrence == "once":
            self._set_done(row, done)
            return self.get(action_id)
        if done and e.completed_at is None:
            e.completed_at = datetime.now(UTC)
        elif not done and e.completed_at is not None:
            e.completed_at = None
        else:
            return self.get(action_id)
        e.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(action_id)

    # --- scheduling -------------------------------------------------------------------------------

    def schedule(self, action_id: str, body: OccurrencesIn) -> ActionOut:
        """Occurrences on the schedule: one for a one-off, one a week for a weekly action. Each is
        its own schedule entry (its own calendar event); moving one later keeps its id."""
        row = self._find(action_id, lock=True)
        weeks = body.weeks if row.recurrence == "weekly" else 1
        if row.recurrence == "once" and body.weeks != 1:
            raise AppError("A one-off action is scheduled once.", code="once_scheduled_once")
        print_ = request_keys.fingerprint(
            "action.schedule",
            {"action": action_id, **body.model_dump(mode="json", exclude={"client_request_id"})},
        )
        keys = [body.client_request_id if i == 0 else f"{body.client_request_id}-{i}" for i in range(weeks)]
        if body.client_request_id and (first := self._by_request(body.client_request_id)) is not None:
            request_keys.check(first.request_fingerprint, print_, "schedule entry")
            return self.get(action_id)
        active = [e for e in self._occurrences(row.id) if e.status != "cancelled"]
        if row.recurrence == "once" and active:
            raise ConflictError(
                f"Already on your schedule on {active[0].on_date.isoformat()}. Move it there instead.",
                code="already_scheduled",
            )
        n = (
            self.db.scalar(
                select(func.count()).select_from(ScheduleEntry).where(ScheduleEntry.user_id == self.user.id)
            )
            or 0
        )
        if n + weeks > MAX_ENTRIES:
            raise AppError(f"Up to {MAX_ENTRIES} schedule entries.", code="too_many_entries")
        schedule = Schedule(self.db, self.user)
        for i in range(weeks):
            e = ScheduleEntry(
                user_id=self.user.id,
                uid=f"{uuid.uuid4()}@codecoach",
                kind="accepted_action",
                ref=row.id,
                title=row.title[:200],  # kept for completeness; every read uses the action's title
                duration_min=body.duration_min,
                notes="",
                client_request_id=keys[i],
                request_fingerprint=print_ if body.client_request_id else None,
                status="scheduled",
                sequence=0,
            )
            schedule._apply_time(
                e, body.on_date + timedelta(weeks=i), body.all_day, body.local_time, body.timezone, body.fold
            )
            self.db.add(e)
        try:
            self.db.commit()
        except IntegrityError:  # the same request, sent twice at once
            self.db.rollback()
            if body.client_request_id and (first := self._by_request(body.client_request_id)) is not None:
                request_keys.check(first.request_fingerprint, print_, "schedule entry")
                return self.get(action_id)
            raise
        return self.get(action_id)

    def _by_request(self, key: str) -> ScheduleEntry | None:
        return self.db.scalar(
            select(ScheduleEntry).where(
                ScheduleEntry.user_id == self.user.id, ScheduleEntry.client_request_id == key
            )
        )

    # --- export -----------------------------------------------------------------------------------

    def export(self, *, with_ids: bool = False) -> list[dict]:
        out = []
        for a in self.mine():
            out.append(
                {
                    **({"id": a.id} if with_ids else {}),
                    "title": a.title,
                    "notes": a.notes,
                    "recurrence": a.recurrence,
                    "status": a.status,
                    "done_at": a.done_at.isoformat() if a.done_at else None,
                    "practice": a.practice_href,
                    "source": {
                        "kind": a.source.kind,
                        "interview": a.source.interview_id,
                        "improvement": a.source.label,
                        "feedback": a.source.why,
                        "question_versions": [v.model_dump() for v in a.source.versions],
                    },
                    "occurrences": [
                        {
                            **({"schedule_entry": o.id} if with_ids else {}),
                            "date": o.on_date.isoformat(),
                            "status": o.status,
                            "completed_at": o.completed_at.isoformat() if o.completed_at else None,
                        }
                        for o in a.occurrences
                    ],
                    "accepted_at": a.created_at.isoformat(),
                }
            )
        return out
