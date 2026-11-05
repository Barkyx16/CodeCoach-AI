"""Private application tracker.

Applications are facts the learner records: nothing is inferred (no offer or rejection from
silence), nothing is sent, nothing is submitted. Stage changes are append-only history with the
title and employer as they were, so correcting a mistake or renaming a role never rewrites what
happened. Everything is scoped to its owner."""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError, NotFoundError
from app.models import (
    Application,
    ApplicationEvent,
    ApplicationStageChange,
    ExperienceEntry,
    RoleTarget,
    User,
)
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationEventIn,
    ApplicationEventOut,
    ApplicationOut,
    ApplicationStageChangeOut,
    ApplicationStageIn,
    ApplicationStoryLink,
    ApplicationSummary,
    ApplicationTargetLink,
    ApplicationUpdate,
)
from app.services.timeutil import local_to_utc, parse_hhmm, zone

MAX_APPLICATIONS = 300
MAX_EVENTS = 30
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(text: str | None) -> str:
    return _CONTROL.sub("", text or "").strip()


def event_out(e: ApplicationEvent) -> ApplicationEventOut:
    return ApplicationEventOut(
        id=e.id,
        kind=e.kind,
        title=e.title,
        on_date=e.on_date,
        local_time=e.local_time,
        timezone=e.timezone,
        starts_at=e.starts_at,
        notes=e.notes,
        created_at=e.created_at,
    )


def not_over(e: ApplicationEvent, now: datetime) -> bool:
    """Whether an event may still be ahead. With an exact time: until it starts. With only a date
    (no time or zone known): until that date has ended everywhere (UTC-12), so it isn't dropped
    early for a learner west of UTC. With no date: never "upcoming" (nothing is assumed)."""
    if e.starts_at is not None:
        return _utc(e.starts_at) >= now
    if e.on_date is not None:
        return now < datetime.combine(e.on_date + timedelta(days=1), time(12, 0), tzinfo=UTC)
    return False


def _next_event(a: Application, now: datetime) -> ApplicationEvent | None:
    """The next event that hasn't happened, in a stated order: by its own date; on the same date,
    exactly-timed events by their instant before date-only ones (whose time isn't known); then by
    when it was recorded. Never by random id."""
    upcoming = [e for e in a.events if not_over(e, now)]

    def key(e: ApplicationEvent) -> tuple:
        starts = _utc(e.starts_at) if e.starts_at is not None else None
        day = e.on_date or (starts.date() if starts else now.date())  # a timed event has its date too
        return (day, 0 if starts else 1, starts or now, _utc(e.created_at))

    return min(upcoming, key=key) if upcoming else None


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo is not None else d.replace(tzinfo=UTC)


class Applications:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- reads --------------------------------------------------------------------------------

    def _get(self, app_id: str) -> Application:
        a = self.db.scalar(
            select(Application)
            .where(Application.id == app_id, Application.user_id == self.user.id)
            .options(selectinload(Application.events), selectinload(Application.history))
        )
        if a is None:
            raise NotFoundError("Application not found")
        return a

    def _target(self, a: Application) -> ApplicationTargetLink | None:
        if not a.target_id:
            return None
        t = self.db.get(RoleTarget, a.target_id)
        return ApplicationTargetLink(id=t.id, title=t.title) if t else None

    def _summary(self, a: Application) -> ApplicationSummary:
        nxt = _next_event(a, datetime.now(UTC))
        return ApplicationSummary(
            id=a.id,
            employer=a.employer,
            role_title=a.role_title,
            stage=a.stage,
            applied_on=a.applied_on,
            next_action=a.next_action,
            next_action_due=a.next_action_due,
            target=self._target(a),
            archived=a.archived,
            next_event=event_out(nxt) if nxt else None,
            updated_at=a.updated_at,
        )

    def all(self, archived: bool = False) -> list[ApplicationSummary]:
        rows = self.db.scalars(
            select(Application)
            .where(Application.user_id == self.user.id, Application.archived.is_(archived))
            .options(selectinload(Application.events))
            .order_by(Application.updated_at.desc())
        ).all()
        return [self._summary(a) for a in rows]

    def get(self, app_id: str) -> ApplicationOut:
        a = self._get(app_id)
        stories = []
        for sid in a.story_ids or []:
            s = self.db.get(ExperienceEntry, sid)
            if s is not None and s.user_id == self.user.id:  # a deleted story simply drops out
                stories.append(ApplicationStoryLink(id=s.id, title=s.title))
        return ApplicationOut(
            **self._summary(a).model_dump(),
            link=a.link,
            notes=a.notes,
            stories=stories,
            events=[
                event_out(e)
                for e in sorted(a.events, key=lambda e: (e.on_date is None, e.on_date, e.local_time or ""))
            ],
            history=[
                ApplicationStageChangeOut(
                    from_stage=h.from_stage,
                    to_stage=h.to_stage,
                    correction=h.correction,
                    note=h.note,
                    role_title=h.role_title,
                    employer=h.employer,
                    changed_at=h.changed_at,
                )
                for h in reversed(a.history)
            ],
            created_at=a.created_at,
        )

    # --- writes -------------------------------------------------------------------------------

    def _links(self, a: Application, target_id: str | None, story_ids: list[str] | None) -> None:
        if target_id is not None:
            t = self.db.get(RoleTarget, target_id)
            if t is None or t.user_id != self.user.id:
                raise NotFoundError("Target not found")
            a.target_id = t.id
        if story_ids is not None:
            ids = list(dict.fromkeys(story_ids))
            for sid in ids:
                s = self.db.get(ExperienceEntry, sid)
                if s is None or s.user_id != self.user.id:
                    raise NotFoundError("Story not found")
            a.story_ids = ids

    def _record_stage(
        self, a: Application, to: str, note: str = "", correction: bool = False, frm: str | None = None
    ) -> None:
        a.history.append(
            ApplicationStageChange(
                from_stage=frm,
                to_stage=to,
                correction=correction,
                note=clean(note),
                role_title=a.role_title,
                employer=a.employer,
            )
        )

    def create(self, body: ApplicationCreate) -> tuple[ApplicationOut, bool]:
        """Returns (application, created). A retry with the same client_request_id returns the first."""
        if body.client_request_id:
            existing = self.db.scalar(
                select(Application.id).where(
                    Application.user_id == self.user.id,
                    Application.client_request_id == body.client_request_id,
                )
            )
            if existing:
                return self.get(existing), False
        count = len(self.db.scalars(select(Application.id).where(Application.user_id == self.user.id)).all())
        if count >= MAX_APPLICATIONS:
            raise AppError(
                f"Up to {MAX_APPLICATIONS} applications. Archive or delete some first.",
                code="too_many_applications",
            )
        a = Application(
            user_id=self.user.id,
            employer=clean(body.employer),
            role_title=clean(body.role_title),
            link=body.link,
            applied_on=body.applied_on,
            stage=body.stage,
            next_action=clean(body.next_action),
            next_action_due=body.next_action_due,
            notes=clean(body.notes),
            story_ids=[],
            client_request_id=body.client_request_id,
        )
        self._links(a, body.target_id, body.story_ids)
        self._record_stage(a, body.stage)
        self.db.add(a)
        try:
            self.db.commit()
        except IntegrityError:  # the same retry raced: return the one that won
            self.db.rollback()
            existing = self.db.scalar(
                select(Application.id).where(
                    Application.user_id == self.user.id,
                    Application.client_request_id == body.client_request_id,
                )
            )
            if existing is None:
                raise
            return self.get(existing), False
        return self.get(a.id), True

    def update(self, app_id: str, body: ApplicationUpdate) -> ApplicationOut:
        a = self._get(app_id)
        data = body.model_dump(exclude_unset=True)
        for f in ("employer", "role_title", "next_action", "notes"):
            if data.get(f) is not None:
                setattr(a, f, clean(data[f]))
        if not a.employer or not a.role_title:
            raise AppError("An application needs an employer and a role title.", code="missing_fields")
        for f in ("link", "applied_on", "next_action_due"):
            if data.get(f) is not None:
                setattr(a, f, data[f])
        for f in body.clear:
            setattr(a, f, None)
        self._links(a, data.get("target_id"), data.get("story_ids"))
        a.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(a.id)

    def set_stage(self, app_id: str, body: ApplicationStageIn, *, commit: bool = True) -> ApplicationOut:
        """With commit=False the change joins the caller's transaction, so it's saved together with
        the caller's own change (a reflection outcome) or not at all."""
        a = self._get(app_id)
        if a.stage == body.stage:
            return self.get(a.id)  # a repeated click changes nothing
        self._record_stage(a, body.stage, body.note, body.correction, frm=a.stage)
        a.stage = body.stage
        a.updated_at = datetime.now(UTC)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get(a.id)

    def set_archived(self, app_id: str, archived: bool) -> ApplicationOut:
        a = self._get(app_id)
        a.archived = archived
        a.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(a.id)

    def delete(self, app_id: str) -> None:
        self.db.delete(self._get(app_id))
        self.db.commit()

    # --- events -------------------------------------------------------------------------------

    def _event_fields(self, e: ApplicationEvent, body: ApplicationEventIn) -> None:
        e.kind = body.kind
        e.title = clean(body.title)
        e.on_date = body.on_date
        e.notes = clean(body.notes)
        e.local_time = None
        e.timezone = None
        e.starts_at = None
        if body.timezone:
            zone(body.timezone)
            e.timezone = body.timezone
        if body.local_time:
            parse_hhmm(body.local_time)
            if body.on_date is None:
                raise AppError("A time needs a date.", code="time_without_date")
            e.local_time = body.local_time
        if e.on_date and e.local_time and e.timezone:
            e.starts_at = local_to_utc(e.on_date, e.local_time, e.timezone, body.fold)

    def add_event(self, app_id: str, body: ApplicationEventIn) -> ApplicationOut:
        a = self._get(app_id)
        if body.client_request_id and any(e.client_request_id == body.client_request_id for e in a.events):
            return self.get(a.id)
        if len(a.events) >= MAX_EVENTS:
            raise AppError(f"Up to {MAX_EVENTS} events per application.", code="too_many_events")
        e = ApplicationEvent(client_request_id=body.client_request_id)
        self._event_fields(e, body)
        a.events.append(e)
        a.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(a.id)

    def update_event(self, app_id: str, event_id: str, body: ApplicationEventIn) -> ApplicationOut:
        a = self._get(app_id)
        e = next((x for x in a.events if x.id == event_id), None)
        if e is None:
            raise NotFoundError("Event not found")
        self._event_fields(e, body)
        a.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(a.id)

    def delete_event(self, app_id: str, event_id: str) -> ApplicationOut:
        a = self._get(app_id)
        e = next((x for x in a.events if x.id == event_id), None)
        if e is None:
            raise NotFoundError("Event not found")
        a.events.remove(e)
        self.db.commit()
        return self.get(a.id)

    def export(self, *, with_ids: bool = False) -> list[dict]:
        """Every application with its events and stage history. With `with_ids` (export version 2)
        each application and event also carries its id, so other records can point to it."""
        rows = self.db.scalars(
            select(Application)
            .where(Application.user_id == self.user.id)
            .options(selectinload(Application.events), selectinload(Application.history))
            .order_by(Application.created_at, Application.id)
        ).all()
        return [
            {
                **({"id": a.id} if with_ids else {}),
                "employer": a.employer,
                "role_title": a.role_title,
                "link": a.link,
                "applied_on": a.applied_on.isoformat() if a.applied_on else None,
                "stage": a.stage,
                "next_action": a.next_action,
                "next_action_due": a.next_action_due.isoformat() if a.next_action_due else None,
                "notes": a.notes,
                "target": a.target_id,
                "stories": a.story_ids,
                "archived": a.archived,
                "events": [
                    {
                        **({"id": e.id} if with_ids else {}),
                        "kind": e.kind,
                        "title": e.title,
                        "date": e.on_date.isoformat() if e.on_date else None,
                        "time": e.local_time,
                        "timezone": e.timezone,
                        "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                        "notes": e.notes,
                    }
                    for e in sorted(a.events, key=lambda e: (_utc(e.created_at), e.id))
                ],
                "stage_history": [
                    {
                        "from": h.from_stage,
                        "to": h.to_stage,
                        "correction": h.correction,
                        "note": h.note,
                        "role_title": h.role_title,
                        "employer": h.employer,
                        "at": h.changed_at.isoformat(),
                    }
                    for h in a.history
                ],
                "created_at": a.created_at.isoformat(),
            }
            for a in rows
        ]
