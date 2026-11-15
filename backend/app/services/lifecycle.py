"""Archive and delete, previewed by the same plan that carries them out (Volume 12, prompt 9;
docs/LIFECYCLE.md).

One planning function per action works out every one of the learner's records it touches:
archived (reversible), deleted, unlinked (the other record stays), kept, or made unavailable. The
preview shows that plan; carrying it out works the plan out again, compares it with the one the
learner saw (a fingerprint), and does exactly what it lists, in one transaction. A changed scope is
refused with the new plan, never carried out silently. A keyed request sent again after a lost reply
is answered with what was done (a receipt), never done twice. Only the learner's own records are
ever read: another account's id is "not found", the same as one that doesn't exist.

Adopted by deleting an application, archiving a note (Volume 12, prompt 9), deleting a story,
deleting a note (with its undo window) and archiving a target (Volume 13, prompt 5), and archiving
or deleting an accepted improvement (Volume 14, prompt 5).
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
    ApplicationEvent,
    Bookmark,
    ExperienceEntry,
    InterviewKit,
    InterviewReflection,
    LifecycleReceipt,
    Note,
    OfferComparison,
    PracticeAnswer,
    ReflectionAction,
    RoleTarget,
    ScheduleEntry,
    StoryRevision,
    TargetRequirement,
    User,
)
from app.schemas.lifecycle import Effect, EffectKind, Impact, LifecycleIn, LifecycleOutcome
from app.services import request_keys
from app.services.story_freshness import forget

RECEIPT_DAYS = 7  # the browser retries an unconfirmed request for at most a day (pendingIntents.ts)
TOMBSTONE = "tombstone:application"  # a deleted application's create key: never made again
STORY_TOMBSTONE = "tombstone:story"  # the same for a deleted story
NOTE_UNDO = timedelta(minutes=10)  # app/services/notes.py UNDO_WINDOW


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

    # --- delete a story ------------------------------------------------------------------------------

    def _story(self, story_id: str) -> ExperienceEntry:
        st = self.db.get(ExperienceEntry, story_id)
        if st is None or st.user_id != self.user.id:
            raise NotFoundError("Story not found")
        return st

    def _holding_story(self, model, story_id: str) -> list:
        """This account's records of one kind that list the story (their `story_ids`)."""
        return [
            r
            for r in self.db.scalars(select(model).where(model.user_id == self.user.id))
            if story_id in (r.story_ids or [])
        ]

    def plan_delete_story(self, story_id: str) -> Impact:
        st = self._story(story_id)
        uid = self.user.id
        revisions = len(
            list(self.db.scalars(select(StoryRevision.id).where(StoryRevision.story_id == st.id)))
        )
        effects = [
            _effect(
                "deleted",
                "story",
                st.title,
                st.id,
                f"With its {_plural(revisions, 'saved version')}." if revisions else None,
            )
        ]
        reqs = (
            {
                r.id: r
                for r in self.db.scalars(
                    select(TargetRequirement)
                    .join(RoleTarget, RoleTarget.id == TargetRequirement.target_id)
                    .where(
                        RoleTarget.user_id == uid, TargetRequirement.id.in_(list(st.requirement_ids or []))
                    )
                )
            }
            if st.requirement_ids
            else {}
        )
        for rid in st.requirement_ids or []:
            if (r := reqs.get(rid)) is not None:
                effects.append(
                    _effect(
                        "deleted",
                        "requirement link",
                        f"Its link to “{r.text}”",
                        r.id,
                        "With the review decisions you made about it. The requirement itself stays on its target.",
                    )
                )
        events = {
            e.id: e.title
            for e in self.db.scalars(
                select(ApplicationEvent)
                .join(Application, Application.id == ApplicationEvent.application_id)
                .where(Application.user_id == uid)
            )
        }
        for k in self._holding_story(InterviewKit, st.id):
            effects.append(
                _effect(
                    "kept",
                    "interview-day kit",
                    f"Kit for {events.get(k.event_id, 'an interview')}",
                    k.event_id,
                    "Keeps what it prepared from this story, as it was, until you remove it there "
                    "(docs/STORY_FRESHNESS.md).",
                )
            )
        for a in self._holding_story(Application, st.id):
            effects.append(
                _effect(
                    "unlinked",
                    "application",
                    f"{a.role_title} at {a.employer}",
                    a.id,
                    "Stays in your applications; it no longer lists this story.",
                )
            )
        for r in self._holding_story(InterviewReflection, st.id):
            # A reflection records what was used, so it keeps the link and says the story was
            # deleted since (missing_stories), as it always has.
            effects.append(
                _effect(
                    "unavailable",
                    "reflection",
                    f"Reflection on {r.event_title}",
                    r.event_id,
                    "Stays, and says a story you linked was deleted from your story bank since.",
                )
            )
        for ans in self.db.scalars(
            select(PracticeAnswer).where(PracticeAnswer.user_id == uid, PracticeAnswer.story_id == st.id)
        ):
            effects.append(
                _effect(
                    "unlinked",
                    "practice answer",
                    "An answer that rehearsed it",
                    ans.id,
                    "Keeps its text and score; it no longer names the story.",
                )
            )
        links = sum(e.kind == "requirement link" for e in effects)
        parts = [
            p
            for p in (
                f"its {_plural(links, 'requirement link')}" if links else "",
                "its revisions" if revisions else "",
            )
            if p
        ]
        return Impact(
            action="delete_story",
            target_id=st.id,
            title=st.title,
            summary="Delete this story" + (", " + " and ".join(parts) if parts else ""),
            effects=effects,
            notes=[
                "This can't be undone. Archive keeps it out of the way instead.",
                "Backups you made before now still hold a copy until you delete them.",
            ],
            fingerprint=fingerprint("delete_story", st.id, effects),
        )

    def delete_story(self, story_id: str, body: LifecycleIn | None) -> LifecycleOutcome:
        if (done := self._replay(body, "delete_story", story_id)) is not None:
            return done
        try:
            st = lock_for_update(self.db, self._story(story_id))
        except InvalidRequestError:
            self.db.rollback()
            if (done := self._replay(body, "delete_story", story_id)) is not None:
                return done
            raise NotFoundError("Story not found") from None
        if body and body.client_request_id and body.client_request_id == st.client_request_id:
            raise request_keys.reused("request")
        impact = self.plan_delete_story(story_id)  # ownership and links, again
        self._check(impact, body)
        for row in self._holding_story(Application, st.id):
            row.story_ids = [x for x in row.story_ids if x != st.id]
        # Answers that rehearsed it keep their text and score; their story_id is cleared by the
        # database (fk_answer_story, ON DELETE SET NULL), as the preview lists.
        # Its requirement links go with it, and so do the decisions about them; a kit keeps what it
        # prepared, with its decisions, until removed there (docs/STORY_FRESHNESS.md).
        forget(self.db, self.user.id, holder_kind="requirement_link", source_id=st.id)
        if st.client_request_id:
            self.db.add(
                LifecycleReceipt(
                    user_id=self.user.id,
                    client_request_id=st.client_request_id,
                    action=STORY_TOMBSTONE,
                    target_id=st.id,
                    impact={},
                    created_at=datetime.now(UTC),
                )
            )
        self.db.delete(st)  # its revisions go with it
        return self._finish(impact, body, f"Deleted {impact.title}.")

    # --- delete a note (restorable for 10 minutes) ----------------------------------------------------

    def plan_delete_note(self, note_id: str) -> Impact:
        n = self._note(note_id)
        title = n.title or "Untitled note"
        effects = [
            _effect(
                "deleted",
                "note",
                title,
                n.id,
                "Restorable for 10 minutes after you delete it (Undo), exactly as it is now; after that it's "
                "removed from CodeCoach.",
            )
        ]
        if n.pinned:
            effects.append(
                _effect(
                    "kept",
                    "pin",
                    "Pinned to the top of your notes",
                    n.id,
                    "Restoring it brings it back pinned.",
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
                _effect("kept", "reflection next step", s.title, s.id, "Still done on your reflection.")
            )
        effects.append(
            _effect(
                "kept",
                "practice packet",
                "Practice packets",
                None,
                "A packet is made when you ask for one, so a deleted note just isn't offered; a packet you "
                "already saved keeps its copy.",
            )
        )
        return Impact(
            action="delete_note",
            target_id=n.id,
            title=title,
            summary="Delete this note (you can undo it for 10 minutes)",
            effects=effects,
            notes=["Backups you made before now still hold a copy until you delete them."],
            fingerprint=fingerprint("delete_note", n.id, effects),
        )

    def delete_note(self, note_id: str, body: LifecycleIn | None) -> LifecycleOutcome:
        if (done := self._replay(body, "delete_note", note_id)) is not None:
            return done
        impact = self.plan_delete_note(note_id)
        self._check(impact, body)
        n = self._note(note_id)
        delete_note_now(n)
        until = _aware(n.deleted_at or datetime.now(UTC)) + NOTE_UNDO
        out = self._finish(
            impact, body, f"Deleted {impact.title}. You can undo it for 10 minutes.", restorable_until=until
        )
        return out

    # --- archive a target ------------------------------------------------------------------------------

    def _target(self, target_id: str) -> RoleTarget:
        t = self.db.get(RoleTarget, target_id)
        if t is None or t.user_id != self.user.id:
            raise NotFoundError("Target not found")
        return t

    def plan_archive_target(self, target_id: str) -> Impact:
        from app.services.requirement_versions import RequirementVersions

        t = self._target(target_id)
        uid = self.user.id
        effects: list[Effect] = []
        if not t.archived:
            effects.append(
                _effect(
                    "archived",
                    "target",
                    t.title,
                    t.id,
                    "Hidden from your targets list. Unarchive it any time and it comes back as it was; nothing "
                    "is deleted.",
                )
            )
            if t.selected:
                effects.append(
                    _effect(
                        "unlinked",
                        "active target",
                        "Your active target",
                        t.id,
                        "It stops being your active target; unarchiving won't make it active again.",
                    )
                )
        for r in sorted((r for r in t.requirements if not r.removed), key=lambda r: r.position):
            effects.append(
                _effect("kept", "requirement", r.text, r.id, "Kept with the target, with its versions.")
            )
        for st in self.db.scalars(
            select(ExperienceEntry).where(ExperienceEntry.user_id == uid, ExperienceEntry.target_id == t.id)
        ):
            effects.append(
                _effect("kept", "story", st.title, st.id, "Stays in your story bank, still linked to it.")
            )
        for a in self.db.scalars(
            select(Application).where(Application.user_id == uid, Application.target_id == t.id)
        ):
            effects.append(
                _effect(
                    "kept",
                    "application",
                    f"{a.role_title} at {a.employer}",
                    a.id,
                    "Stays, still linked to it.",
                )
            )
        seen: set[str] = set()
        for link in RequirementVersions(self.db, self.user).action_links(t):
            if link.action_id in seen:
                continue
            seen.add(link.action_id)
            effects.append(
                _effect(
                    "kept",
                    "accepted improvement",
                    link.title,
                    link.action_id,
                    "Stays on your plan and schedule; still listed with the target's requirements.",
                )
            )
        effects.append(
            _effect(
                "kept",
                "practice",
                "Answers and rounds you practised for it",
                None,
                "They stay in your history and still count.",
            )
        )
        return Impact(
            action="archive_target",
            target_id=t.id,
            title=t.title,
            summary="Archive this target" if not t.archived else "This target is already archived",
            effects=effects,
            notes=[
                "Archiving isn't deleting: everything listed stays, comes back when you unarchive it, and is in "
                "your data export."
            ],
            fingerprint=fingerprint("archive_target", t.id, effects),
        )

    def archive_target(self, target_id: str, body: LifecycleIn | None) -> LifecycleOutcome:
        if (done := self._replay(body, "archive_target", target_id)) is not None:
            return done
        impact = self.plan_archive_target(target_id)
        self._check(impact, body)
        t = self._target(target_id)
        if not t.archived:
            archive_target_now(t)
            t.updated_at = datetime.now(UTC)
        return self._finish(impact, body, f"Archived {impact.title}. Unarchive it any time.")

    # --- accepted improvements (Volume 14, prompt 5; docs/ACCEPTED_ACTIONS.md) -------------------

    def _action(self, action_id: str) -> AcceptedAction:
        a = self.db.get(AcceptedAction, action_id)
        if a is None or a.user_id != self.user.id:
            raise NotFoundError("Action not found")
        return a

    def _action_reach(self, a: AcceptedAction) -> tuple[list[ScheduleEntry], list[InterviewKit], list]:
        """What an accepted improvement reaches: its occurrences, the kits whose checklist names it,
        and the target requirements it's listed with (worked out from what it practises)."""
        from app.services.requirement_versions import RequirementVersions

        uid = self.user.id
        occurrences = list(
            self.db.scalars(
                select(ScheduleEntry)
                .where(
                    ScheduleEntry.user_id == uid,
                    ScheduleEntry.kind == "accepted_action",
                    ScheduleEntry.ref == a.id,
                )
                .order_by(ScheduleEntry.on_date, ScheduleEntry.created_at)
            )
        )
        kits = [
            k
            for k in self.db.scalars(select(InterviewKit).where(InterviewKit.user_id == uid))
            if any(c.get("origin") == "action" and c.get("action_id") == a.id for c in k.checklist or [])
        ]
        versions = RequirementVersions(self.db, self.user)
        links = []
        for t in self.db.scalars(
            select(RoleTarget).where(RoleTarget.user_id == uid).order_by(RoleTarget.created_at)
        ):
            links += [(t, link) for link in versions.action_links(t) if link.action_id == a.id]
        return occurrences, kits, links

    def _kit_title(self, k: InterviewKit) -> str:
        ev = self.db.get(ApplicationEvent, k.event_id)
        return f"Kit for {ev.title}" if ev is not None else "An interview-day kit"

    def _occurrence_effect(
        self, a: AcceptedAction, e: ScheduleEntry, effect: EffectKind, note: str
    ) -> Effect:
        done = (a.done_at if a.recurrence == "once" else e.completed_at) is not None
        state = "cancelled" if e.status == "cancelled" else "done" if done else "not done yet"
        return _effect(effect, "occurrence", f"{e.on_date.isoformat()} ({state})", e.id, note)

    def plan_archive_action(self, action_id: str) -> Impact:
        a = self._action(action_id)
        occurrences, kits, links = self._action_reach(a)
        effects: list[Effect] = []
        if a.archived_at is None:
            effects.append(
                _effect(
                    "archived",
                    "accepted improvement",
                    a.title,
                    a.id,
                    "Off your plan, your schedule and Today. Unarchive it any time and it comes back as it "
                    "was; nothing is deleted.",
                )
            )
        for e in occurrences:
            effects.append(
                self._occurrence_effect(
                    a,
                    e,
                    "kept",
                    "Off your schedule while it's archived; it comes back when you unarchive it. Marks of done "
                    "are kept.",
                )
            )
        for k in kits:
            effects.append(
                _effect(
                    "kept", "kit checklist item", self._kit_title(k), k.event_id, "Stays, labelled archived."
                )
            )
        for t, link in links:
            effects.append(
                _effect(
                    "kept",
                    "requirement link",
                    f"{t.title}: a requirement it practises",
                    link.requirement_id,
                    "Still listed with the requirement.",
                )
            )
        effects.append(self._suggestion_effect(a, "The interview's review still shows it as accepted."))
        return Impact(
            action="archive_action",
            target_id=a.id,
            title=a.title,
            summary="Archive this improvement"
            if a.archived_at is None
            else "This improvement is already archived",
            effects=effects,
            notes=[
                "Archiving isn't deleting: everything listed stays, comes back when you unarchive it, and is in "
                "your data export. A calendar file you downloaded earlier keeps its copy of the occurrences."
            ],
            fingerprint=fingerprint("archive_action", a.id, effects),
        )

    def _suggestion_effect(self, a: AcceptedAction, note: str) -> Effect:
        src = a.source or {}
        return _effect(
            "kept",
            "suggestion",
            f"{src.get('label', a.title)}, in {src.get('interview_title', 'an interview')}'s review",
            a.source_id,
            note,
        )

    def archive_action(self, action_id: str, body: LifecycleIn | None) -> LifecycleOutcome:
        if (done := self._replay(body, "archive_action", action_id)) is not None:
            return done
        impact = self.plan_archive_action(action_id)
        self._check(impact, body)
        a = self._action(action_id)
        if a.archived_at is None:
            a.archived_at = datetime.now(UTC)
            a.updated_at = a.archived_at
        return self._finish(impact, body, f"Archived {impact.title}. Unarchive it any time.")

    def unarchive_action(self, action_id: str) -> None:
        """Back on the plan, the schedule and Today, with its occurrences as they were."""
        a = self._action(action_id)
        if a.archived_at is not None:
            a.archived_at = None
            a.updated_at = datetime.now(UTC)
            self.db.commit()

    def plan_delete_action(self, action_id: str) -> Impact:
        a = self._action(action_id)
        occurrences, kits, links = self._action_reach(a)
        effects: list[Effect] = [
            _effect(
                "deleted",
                "accepted improvement",
                a.title,
                a.id,
                "With its notes and its marks of done.",
            )
        ]
        for e in occurrences:
            effects.append(self._occurrence_effect(a, e, "deleted", "Removed from your schedule."))
        for k in kits:
            effects.append(
                _effect(
                    "kept",
                    "kit checklist item",
                    self._kit_title(k),
                    k.event_id,
                    "Stays on the kit's checklist as “An improvement you removed”.",
                )
            )
        for t, link in links:
            effects.append(
                _effect(
                    "unlinked",
                    "requirement link",
                    f"{t.title}: a requirement it practises",
                    link.requirement_id,
                    "No longer listed with the requirement; the requirement stays.",
                )
            )
        effects.append(
            self._suggestion_effect(
                a, "It stays in the interview's review, and you can accept it again as a new improvement."
            )
        )
        effects.append(
            _effect(
                "kept",
                "practice",
                "Answers and submissions you practised it with",
                None,
                "They stay in your history and still count.",
            )
        )
        return Impact(
            action="delete_action",
            target_id=a.id,
            title=a.title,
            summary="Delete this improvement",
            effects=effects,
            notes=[
                "Deleting can't be undone here. A data export (version 2) you downloaded earlier can bring it "
                "back with its occurrences; backups CodeCoach made earlier keep a copy until they age out."
            ],
            fingerprint=fingerprint("delete_action", a.id, effects),
        )

    def delete_action(self, action_id: str, body: LifecycleIn | None) -> LifecycleOutcome:
        if (done := self._replay(body, "delete_action", action_id)) is not None:
            return done
        impact = self.plan_delete_action(action_id)
        self._check(impact, body)
        a = self._action(action_id)
        self.db.execute(
            delete(ScheduleEntry).where(
                ScheduleEntry.user_id == self.user.id,
                ScheduleEntry.kind == "accepted_action",
                ScheduleEntry.ref == a.id,
            )
        )
        self.db.delete(a)
        return self._finish(impact, body, f"Deleted {impact.title}.")

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

    def _finish(
        self, impact: Impact, body: LifecycleIn | None, message: str, restorable_until: datetime | None = None
    ) -> LifecycleOutcome:
        out = LifecycleOutcome(
            **impact.model_dump(),
            done_at=datetime.now(UTC),
            message=message,
            restorable_until=restorable_until,
        )
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


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def delete_note_now(n: Note) -> None:
    """What deleting a note does, wherever it's asked: hidden for the undo window, then removed. Its
    pin is kept, so Undo brings it back exactly as it was."""
    n.deleted_at = datetime.now(UTC)


def archive_target_now(t: RoleTarget) -> None:
    """What archiving a target does, wherever it's asked (the preview, the target's own Archive):
    hidden, and no longer the active one. Nothing is deleted; unarchiving doesn't make it active."""
    t.archived = True
    t.selected = False


def archive_note_now(n: Note) -> None:
    """What archiving a note does, wherever it's asked (the preview, a note's own Archive, a bulk
    archive): hidden, and unpinned. Nothing is erased; unarchiving doesn't pin it again."""
    n.archived = True
    n.pinned = False


def deleted_earlier(db: Session, user: User, key: str | None, kind: str = "application") -> None:
    """A create sent again after the record it made was deleted: refused, not made again."""
    if not key:
        return
    if db.scalar(
        select(LifecycleReceipt.id).where(
            LifecycleReceipt.user_id == user.id,
            LifecycleReceipt.client_request_id == key,
            LifecycleReceipt.action == (STORY_TOMBSTONE if kind == "story" else TOMBSTONE),
        )
    ):
        raise GoneError(
            f"This request made {'a story' if kind == 'story' else 'an application'} that has since been "
            "deleted, so it isn't made again.",
            code="deleted_earlier",
        )


def purge(db: Session, now: datetime | None = None) -> int:
    """Housekeeping: receipts (and tombstones) older than RECEIPT_DAYS. Returns how many went."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RECEIPT_DAYS)
    result = db.execute(delete(LifecycleReceipt).where(LifecycleReceipt.created_at < cutoff))
    return int(getattr(result, "rowcount", 0) or 0)
