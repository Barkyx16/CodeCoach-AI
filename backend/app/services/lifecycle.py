"""Archive and delete, previewed by the same plan that carries them out (Volume 12, prompt 9;
docs/LIFECYCLE.md).

One planning function per action works out every one of the learner's records it touches:
archived (reversible), deleted, unlinked (the other record stays), kept, or made unavailable. The
preview shows that plan; carrying it out works the plan out again, compares it with the one the
learner saw (a fingerprint), and does exactly what it lists, in one transaction. A changed scope is
refused with the new plan, never carried out silently. A keyed request sent again after a lost reply
is answered with what was done (a receipt), never done twice. Only the learner's own records are
ever read: another account's id is "not found", the same as one that doesn't exist.

Adopted so far by deleting an application and archiving a note.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session

from app.db.locking import lock_for_update
from app.errors import ConflictError, GoneError, NotFoundError
from app.models import (
    AcceptedAction,
    Application,
    Bookmark,
    ExperienceEntry,
    InterviewKit,
    InterviewReflection,
    LifecycleReceipt,
    Note,
    OfferComparison,
    ReflectionAction,
    ScheduleEntry,
    User,
)
from app.schemas.lifecycle import Effect, EffectKind, Impact, LifecycleIn, LifecycleOutcome
from app.services import request_keys
from app.services.story_freshness import forget

RECEIPT_DAYS = 7  # the browser retries an unconfirmed request for at most a day (pendingIntents.ts)
TOMBSTONE = "tombstone:application"  # a deleted application's create key: never made again


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def fingerprint(action: str, target_id: str, effects: list[Effect]) -> str:
    """What the plan does, by item: the same items with the same effects give the same print."""
    items = sorted((e.effect, e.kind, e.id or "", e.title) for e in effects)
    return hashlib.sha256(json.dumps([action, target_id, items]).encode()).hexdigest()[:32]


def _effect(effect: EffectKind, kind: str, title: str, id_: str | None, note: str | None = None) -> Effect:
    return Effect(effect=effect, kind=kind, title=title, id=id_, note=note)


class Lifecycle:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- delete an application -------------------------------------------------------------------

    def _application(self, app_id: str) -> Application:
        a = self.db.get(Application, app_id)
        if a is None or a.user_id != self.user.id:
            raise NotFoundError("Application not found")  # another account's: the same answer
        return a

    def plan_delete_application(self, app_id: str) -> Impact:
        a = self._application(app_id)
        uid = self.user.id
        events = sorted(
            a.events, key=lambda e: (e.on_date is None, e.on_date or datetime.min.date(), e.title)
        )
        event_ids = [e.id for e in events]
        titles = {e.id: e.title for e in events}
        kits = (
            list(
                self.db.scalars(
                    select(InterviewKit).where(
                        InterviewKit.event_id.in_(event_ids), InterviewKit.user_id == uid
                    )
                )
            )
            if event_ids
            else []
        )
        reflections = list(
            self.db.scalars(
                select(InterviewReflection).where(
                    InterviewReflection.application_id == a.id, InterviewReflection.user_id == uid
                )
            )
        )
        steps = (
            list(
                self.db.scalars(
                    select(ReflectionAction).where(
                        ReflectionAction.event_id.in_(event_ids), ReflectionAction.user_id == uid
                    )
                )
            )
            if event_ids
            else []
        )
        effects: list[Effect] = []
        history = len(a.history)
        effects.append(
            _effect(
                "deleted",
                "application",
                f"{a.role_title} at {a.employer}",
                a.id,
                f"With its notes and stage history ({_plural(history, 'change')})."
                if history
                else "With its notes.",
            )
        )
        for e in events:
            when = f" ({e.on_date:%-d %B %Y})" if e.on_date else ""
            effects.append(_effect("deleted", "interview event", f"{e.title}{when}", e.id))
        for k in kits:
            effects.append(
                _effect(
                    "deleted",
                    "interview-day kit",
                    f"Kit for {titles.get(k.event_id, 'an event')}",
                    k.event_id,
                    "Its checklist, questions and chosen examples, and what it kept from them.",
                )
            )
        for r in reflections:
            effects.append(_effect("deleted", "reflection", f"Reflection on {r.event_title}", r.event_id))
        for s in steps:
            kept = self._made_by_step(s)
            if kept is not None:
                effects.append(kept)
        # Stories chosen for it, its kits or its reflections: unlinked, kept in the story bank.
        story_ids: list[str] = list(a.story_ids or [])
        for k in kits:
            story_ids += list(k.story_ids or [])
        for r in reflections:
            story_ids += list(getattr(r, "story_ids", None) or [])
        for sid in dict.fromkeys(story_ids):
            st = self.db.get(ExperienceEntry, sid)
            if st is not None and st.user_id == uid:
                effects.append(_effect("unlinked", "story", st.title, st.id, "Stays in your story bank."))
        # Accepted improvements on its kits' checklists: unlinked, kept as actions.
        action_ids = [
            str(c.get("action_id"))
            for k in kits
            for c in (k.checklist or [])
            if c.get("origin") == "action" and c.get("action_id")
        ]
        for aid in dict.fromkeys(action_ids):
            act = self.db.get(AcceptedAction, aid)
            if act is not None and act.user_id == uid:
                effects.append(
                    _effect(
                        "unlinked",
                        "accepted improvement",
                        act.title,
                        act.id,
                        "Stays on your plan page and schedule.",
                    )
                )
        # Its events on the schedule stay there, marked no longer available.
        if event_ids:
            for entry in self.db.scalars(
                select(ScheduleEntry).where(
                    ScheduleEntry.user_id == uid,
                    ScheduleEntry.kind == "application_event",
                    ScheduleEntry.ref.in_(event_ids),
                    ScheduleEntry.status != "cancelled",
                )
            ):
                effects.append(
                    _effect(
                        "unavailable",
                        "schedule entry",
                        entry.title,
                        entry.id,
                        "Stays on your schedule, marked no longer available. Remove it there if you don't need it.",
                    )
                )
        # Offer comparisons that name it keep the figures you entered; the link goes.
        for c in self._comparisons_naming(a.id):
            effects.append(
                _effect(
                    "unlinked",
                    "offer comparison",
                    c.title,
                    c.id,
                    "Keeps the figures you entered for this offer; it just no longer links to the application.",
                )
            )
        parts = [
            _plural(n, word)
            for n, word in ((len(events), "event"), (len(kits), "kit"), (len(reflections), "reflection"))
            if n
        ]
        reach = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else "".join(parts)
        return Impact(
            action="delete_application",
            target_id=a.id,
            title=f"{a.role_title} at {a.employer}",
            summary=f"Delete this application, its {reach}" if reach else "Delete this application",
            effects=effects,
            notes=[
                "This can't be undone. Archive keeps it out of the way instead.",
                "Backups you made before now still hold a copy until you delete them.",
            ],
            fingerprint=fingerprint("delete_application", a.id, effects),
        )

    def _made_by_step(self, s: ReflectionAction) -> Effect | None:
        """What an accepted next step created stays: it was never part of the reflection."""
        if s.status != "accepted" or not s.applied_ref:
            return None
        uid = self.user.id
        if s.target == "notebook":
            n = self.db.get(Note, s.applied_ref)
            if n is not None and n.user_id == uid and n.deleted_at is None:
                return _effect(
                    "kept", "note", n.title or s.title, n.id, "Made from a reflection's next step; it stays."
                )
        elif s.target == "schedule":
            e = self.db.get(ScheduleEntry, s.applied_ref)
            if e is not None and e.user_id == uid:
                return _effect(
                    "kept", "schedule entry", e.title, e.id, "Made from a reflection's next step; it stays."
                )
        elif s.target == "saved" and "/" in s.applied_ref:
            track, qid = s.applied_ref.split("/", 1)
            b = self.db.scalar(
                select(Bookmark).where(
                    Bookmark.user_id == uid,
                    Bookmark.item_type == "question",
                    Bookmark.track == track,
                    Bookmark.ref_id == qid,
                )
            )
            if b is not None:
                return _effect(
                    "kept", "saved question", s.title, b.id, "Made from a reflection's next step; it stays."
                )
        return None

    def _comparisons_naming(self, app_id: str) -> list[OfferComparison]:
        rows = self.db.scalars(select(OfferComparison).where(OfferComparison.user_id == self.user.id))
        return [
            c for c in rows if any(o.get("application_id") == app_id for o in (c.doc or {}).get("offers", []))
        ]

    def delete_application(self, app_id: str, body: LifecycleIn | None) -> LifecycleOutcome:
        """Carry out the plan the learner saw (body), or, for older clients that send no plan
        (body None), the plan as it is now."""
        if (done := self._replay(body, "delete_application", app_id)) is not None:
            return done
        try:  # two deletes at once: the second waits here, then finds it gone
            a = lock_for_update(self.db, self._application(app_id))
        except InvalidRequestError:
            self.db.rollback()
            if (done := self._replay(body, "delete_application", app_id)) is not None:
                return done
            raise NotFoundError("Application not found") from None
        if body and body.client_request_id and body.client_request_id == a.client_request_id:
            raise request_keys.reused("request")  # one key, one request
        impact = self.plan_delete_application(app_id)  # ownership and relationships, again
        self._check(impact, body)
        for c in self._comparisons_naming(a.id):
            doc = dict(c.doc or {})
            doc["offers"] = [
                {**o, "application_id": None} if o.get("application_id") == a.id else o
                for o in doc.get("offers", [])
            ]
            c.doc = doc
            c.revision += 1  # another tab's save of the old links gets the usual stale-save choice
            c.updated_at = datetime.now(UTC)
        forget(self.db, self.user.id, holder_kind="kit", holder_ids=[e.id for e in a.events])
        if a.client_request_id:
            # A late retry of the request that created it finds this, and doesn't make it again.
            self.db.add(
                LifecycleReceipt(
                    user_id=self.user.id,
                    client_request_id=a.client_request_id,
                    action=TOMBSTONE,
                    target_id=a.id,
                    impact={},
                    created_at=datetime.now(UTC),
                )
            )
        self.db.delete(a)  # its events, history, kits, reflections and their next steps go with it
        return self._finish(impact, body, f"Deleted {impact.title}.")

    # --- archive a note ---------------------------------------------------------------------------

    def _note(self, note_id: str) -> Note:
        n = self.db.get(Note, note_id)
        if n is None or n.user_id != self.user.id or n.deleted_at is not None:
            raise NotFoundError("Note not found")
        return n

    def plan_archive_note(self, note_id: str) -> Impact:
        n = self._note(note_id)
        title = n.title or "Untitled note"
        effects: list[Effect] = []
        if not n.archived:
            effects.append(
                _effect(
                    "archived",
                    "note",
                    title,
                    n.id,
                    "Hidden from your notes list, Continue and search unless you include archived notes. "
                    "Unarchive it any time; nothing is erased.",
                )
            )
            if n.pinned:
                effects.append(
                    _effect(
                        "unlinked",
                        "pin",
                        "Pinned to the top of your notes",
                        n.id,
                        "Unarchiving won't pin it again.",
                    )
                )
        for s in self.db.scalars(
            select(ReflectionAction).where(
                ReflectionAction.user_id == self.user.id,
                ReflectionAction.target == "notebook",
                ReflectionAction.applied_ref == n.id,
            )
        ):
            effects.append(
                _effect(
                    "kept",
                    "reflection next step",
                    s.title,
                    s.id,
                    "Still done on your reflection; the note is still there.",
                )
            )
        return Impact(
            action="archive_note",
            target_id=n.id,
            title=title,
            summary="Archive this note" if not n.archived else "This note is already archived",
            effects=effects,
            notes=[
                "Archiving isn't deleting: the note stays in your data export and can still go in a practice packet."
            ],
            fingerprint=fingerprint("archive_note", n.id, effects),
        )

    def archive_note(self, note_id: str, body: LifecycleIn | None) -> LifecycleOutcome:
        if (done := self._replay(body, "archive_note", note_id)) is not None:
            return done
        impact = self.plan_archive_note(note_id)
        self._check(impact, body)
        n = self._note(note_id)
        if not n.archived:
            archive_note_now(n)
            n.updated_at = datetime.now(UTC)
        return self._finish(impact, body, f"Archived {impact.title}.")

    # --- shared -------------------------------------------------------------------------------------

    def _replay(self, body: LifecycleIn | None, action: str, target_id: str) -> LifecycleOutcome | None:
        key = body.client_request_id if body else None
        if not key:
            return None
        r = self.db.scalar(
            select(LifecycleReceipt).where(
                LifecycleReceipt.user_id == self.user.id,
                LifecycleReceipt.client_request_id == key,
                LifecycleReceipt.created_at >= datetime.now(UTC) - timedelta(days=RECEIPT_DAYS),
            )
        )
        if r is None:
            return None
        if r.action != action or r.target_id != target_id:
            raise request_keys.reused("request")
        return LifecycleOutcome(
            **{**r.impact, "replayed": True, "message": "This was already done; nothing was done again."}
        )

    @staticmethod
    def _check(impact: Impact, body: LifecycleIn | None) -> None:
        if body is not None and body.expected_fingerprint != impact.fingerprint:
            raise ConflictError(
                "What this would affect has changed since you looked. Nothing was done: check the new list.",
                code="impact_changed",
                details={"current": impact.model_dump(mode="json")},
            )

    def _finish(self, impact: Impact, body: LifecycleIn | None, message: str) -> LifecycleOutcome:
        out = LifecycleOutcome(**impact.model_dump(), done_at=datetime.now(UTC), message=message)
        key = body.client_request_id if body else None
        if key:
            # What was done, by kind and id, without any titles: a receipt mustn't keep the words of
            # what was deleted (docs/LIFECYCLE.md). A retry's reply says what was done, not by name.
            kept = out.model_copy(
                update={
                    "title": "",
                    "message": "",
                    "effects": [e.model_copy(update={"title": "", "note": None}) for e in out.effects],
                }
            )
            self.db.add(
                LifecycleReceipt(
                    user_id=self.user.id,
                    client_request_id=key,
                    action=impact.action,
                    target_id=impact.target_id,
                    impact=kept.model_dump(mode="json"),
                    created_at=out.done_at,
                )
            )
        try:
            self.db.commit()
        except IntegrityError:  # the same request at the same moment: it did it; say what it did
            self.db.rollback()
            if (done := self._replay(body, impact.action, impact.target_id)) is not None:
                return done
            raise
        return out


def archive_note_now(n: Note) -> None:
    """What archiving a note does, wherever it's asked (the preview, a note's own Archive, a bulk
    archive): hidden, and unpinned. Nothing is erased; unarchiving doesn't pin it again."""
    n.archived = True
    n.pinned = False


def deleted_earlier(db: Session, user: User, key: str | None) -> None:
    """A create sent again after the application it made was deleted: refused, not made again."""
    if not key:
        return
    if db.scalar(
        select(LifecycleReceipt.id).where(
            LifecycleReceipt.user_id == user.id,
            LifecycleReceipt.client_request_id == key,
            LifecycleReceipt.action == TOMBSTONE,
        )
    ):
        raise GoneError(
            "This request made an application that has since been deleted, so it isn't made again.",
            code="deleted_earlier",
        )


def purge(db: Session, now: datetime | None = None) -> int:
    """Housekeeping: receipts (and tombstones) older than RECEIPT_DAYS. Returns how many went."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RECEIPT_DAYS)
    result = db.execute(delete(LifecycleReceipt).where(LifecycleReceipt.created_at < cutoff))
    return int(getattr(result, "rowcount", 0) or 0)
