"""Private application tracker.

Applications are facts the learner records: nothing is inferred (no offer or rejection from
silence), nothing is sent, nothing is submitted. Stage changes are append-only history with the
title and employer as they were, so correcting a mistake or renaming a role never rewrites what
happened. Everything is scoped to its owner."""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import JSON, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError, ConflictError, NotFoundError, PreconditionRequiredError
from app.models import (
    Application,
    ApplicationEvent,
    ApplicationStageChange,
    ExperienceEntry,
    RoleTarget,
    User,
)
from app.schemas.applications import (
    MAX_LINKED_STORIES,
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
from app.schemas.common import SaveReplay
from app.services import request_keys, update_receipts
from app.services.timeutil import local_to_utc, parse_hhmm, zone

MAX_APPLICATIONS = 300
MAX_EVENTS = 30
LINK_ATTEMPTS = 10  # a story link's conditional write, retried when another change got there first
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
                stories.append(ApplicationStoryLink(id=s.id, title=s.title, archived=s.archived))
        return ApplicationOut(
            **self._summary(a).model_dump(),
            link=a.link,
            notes=a.notes,
            notes_revision=a.notes_revision or 1,
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

    def link_story(self, app_id: str, story_id: str, linked: bool) -> ApplicationOut:
        """Link one of your stories to this application, or unlink it (Volume 11, prompt 6;
        docs/BACKLINKS.md). One story at a time, so a page showing an older list can't undo a link
        made elsewhere, and asking twice is the same as asking once: linking what's linked, or
        unlinking what isn't, changes nothing (a lost reply can simply be sent again). Both ends
        must be yours: the application (404 otherwise) and, to link, the story (404 otherwise).
        Unlinking needs no story, so an id left by a story deleted since can be taken out.

        The write is conditional on the list it was worked out from (`... WHERE story_ids =
        <as read>`), so two links made at the same moment both stay on any database: the one that
        finds the list changed reads it again and tries once more."""
        if linked:
            s = self.db.get(ExperienceEntry, story_id)
            if s is None or s.user_id != self.user.id:
                self._get(app_id)  # an application that isn't yours is "not found" first
                raise NotFoundError("Story not found")
        for _ in range(LINK_ATTEMPTS):
            a = self._get(app_id)
            before = a.story_ids
            ids = list(before or [])
            if linked:
                if story_id in ids:
                    return self.get(a.id)
                if len(ids) >= MAX_LINKED_STORIES:
                    raise ConflictError(
                        f"An application links up to {MAX_LINKED_STORIES} stories. Unlink one first.",
                        code="too_many_stories",
                    )
                after = [*ids, story_id]
            else:
                if story_id not in ids:
                    return self.get(a.id)
                after = [x for x in ids if x != story_id]
            same = (
                or_(Application.story_ids.is_(None), Application.story_ids == JSON.NULL)
                if before is None
                else Application.story_ids == before
            )
            done = self.db.execute(
                update(Application)
                .where(Application.id == a.id, Application.user_id == self.user.id, same)
                .values(story_ids=after, updated_at=datetime.now(UTC))
                .execution_options(synchronize_session=False)
            )
            if int(getattr(done, "rowcount", 0) or 0) == 1:
                self.db.commit()
                self.db.expire_all()
                return self.get(a.id)
            self.db.rollback()  # changed meanwhile: read it again
        raise ConflictError("The application kept changing. Try again.", code="busy")

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
        """Returns (application, created). A retry with the same client_request_id returns the
        first; the same key with other content is refused (409 `idempotency_key_reused`)."""
        print_ = request_keys.fingerprint(
            "application.create", body.model_dump(mode="json", exclude={"client_request_id"})
        )
        if body.client_request_id and (made := self._by_request(body.client_request_id)) is not None:
            request_keys.check(made.request_fingerprint, print_, "application")
            return self.get(made.id), False
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
            request_fingerprint=print_ if body.client_request_id else None,
        )
        self._links(a, body.target_id, body.story_ids)
        self._record_stage(a, body.stage)
        self.db.add(a)
        try:
            self.db.commit()
        except IntegrityError:  # the same retry raced: return the one that won
            self.db.rollback()
            made = self._by_request(body.client_request_id) if body.client_request_id else None
            if made is None:
                raise
            request_keys.check(made.request_fingerprint, print_, "application")
            return self.get(made.id), False
        return self.get(a.id), True

    def _by_request(self, key: str) -> Application | None:
        return self.db.scalar(
            select(Application).where(
                Application.user_id == self.user.id, Application.client_request_id == key
            )
        )

    def update(self, app_id: str, body: ApplicationUpdate) -> ApplicationOut:
        a = self._get(app_id)
        data = body.model_dump(exclude_unset=True)
        if (replayed := self._notes(a, body, data)) is not None:
            return replayed
        for f in ("employer", "role_title", "next_action"):
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

    def _notes(self, a: Application, body: ApplicationUpdate, data: dict) -> ApplicationOut | None:
        """The private notes, revision-checked (Volume 8, prompt 5; docs/PERSISTENCE.md). Only a
        change to them needs `notes_expected_revision`; the same text, or no notes at all, leaves
        them and their revision alone, so editing the next action never conflicts with them.

        The write is conditional (`... WHERE notes_revision = expected`), so two devices saving from
        the same base can't both succeed on any database: one wins, the other gets the saved notes
        back to compare. A keyed save whose reply was lost is recognised by its receipt and answered
        "went through", not as a conflict with itself. Returns that replay, else None."""
        if data.get("notes") is None:
            return None
        new = clean(data["notes"])
        expected = body.notes_expected_revision
        key = body.client_request_id
        print_ = update_receipts.fingerprint("app_notes", a.id, expected or 0, {"notes": new})
        if expected is not None:
            done = update_receipts.find(self.db, self.user, key, "app_notes", a.id, expected, print_)
            if done is not None:
                out = self.get(a.id)
                out.save_replay = SaveReplay(
                    accepted_revision=done.accepted_revision, current_revision=out.notes_revision
                )
                return out
        if new == a.notes:
            return None  # unchanged: nothing to check, nothing to bump
        if expected is None:
            raise PreconditionRequiredError(
                "Changing the notes needs the revision they were edited from. Reload, then save again.",
                code="notes_revision_required",
            )
        moved = self.db.execute(
            update(Application)
            .where(Application.id == a.id, Application.notes_revision == expected)
            .values(notes=new, notes_revision=Application.notes_revision + 1)
            .execution_options(synchronize_session=False)
        )
        if int(getattr(moved, "rowcount", 0) or 0) != 1:
            self.db.rollback()
            current = self.db.get(Application, a.id)
            assert current is not None
            raise ConflictError(
                "These notes were changed somewhere else (maybe another tab) since you opened them. "
                "Your text is still on this page.",
                code="notes_conflict",
                details={"current_revision": current.notes_revision, "current": current.notes},
            )
        self.db.expire(a, ["notes", "notes_revision"])
        update_receipts.record(self.db, self.user, key, "app_notes", a.id, expected, expected + 1, print_)
        return None

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
        """A retry with the same client_request_id returns the application with the event the
        first made (also when two copies arrive at once); other content under that key is a 409."""
        a = self._get(app_id)
        print_ = request_keys.fingerprint(
            "application.event",
            {"application": a.id, **body.model_dump(mode="json", exclude={"client_request_id"})},
        )
        if body.client_request_id and (made := self._event_by_request(a, body.client_request_id)):
            request_keys.check(made.request_fingerprint, print_, "event")
            return self.get(a.id)
        if len(a.events) >= MAX_EVENTS:
            raise AppError(f"Up to {MAX_EVENTS} events per application.", code="too_many_events")
        e = ApplicationEvent(
            client_request_id=body.client_request_id,
            request_fingerprint=print_ if body.client_request_id else None,
        )
        self._event_fields(e, body)
        a.events.append(e)
        a.updated_at = datetime.now(UTC)
        try:
            self.db.commit()
        except IntegrityError:  # the same event, sent twice at once: the other copy made it
            self.db.rollback()
            a = self._get(app_id)
            made = self._event_by_request(a, body.client_request_id) if body.client_request_id else None
            if made is None:
                raise
            request_keys.check(made.request_fingerprint, print_, "event")
        return self.get(a.id)

    @staticmethod
    def _event_by_request(a: Application, key: str) -> ApplicationEvent | None:
        return next((e for e in a.events if e.client_request_id == key), None)

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
