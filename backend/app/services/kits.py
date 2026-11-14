"""Interview-day kits: one per recorded interview event.

Until the learner changes something, a kit is only suggestions (nothing is stored). Suggestions
are labelled as such and come from the event's format and the learner's own linked job target;
nothing is invented about the employer. A ticked checklist item means the learner ticked it:
CodeCoach never checks a camera, a network, documents or travel. Meeting links are kept as text
and never fetched."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.errors import ConflictError, NotFoundError
from app.models import (
    AcceptedAction,
    Application,
    ApplicationEvent,
    ExperienceEntry,
    InterviewKit,
    RoleTarget,
    ScheduleEntry,
    User,
)
from app.schemas.common import SaveReplay
from app.schemas.freshness import SourceReviewIn
from app.schemas.kits import (
    AskQuestion,
    ChecklistItem,
    Interviewer,
    KeptStory,
    KitAction,
    KitOut,
    KitStory,
    KitUpdate,
    KitWhen,
    PreparedStory,
)
from app.services import update_receipts
from app.services.story_freshness import Prepared, StoryFreshness, digest, digest_of, forget

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

COMMON_BEFORE = ["Confirm the date, time and time zone"]
FORMAT_ITEMS = {
    "remote": [
        "Open the meeting link ahead of time to check it works for you",
        "Check your microphone and camera",
        "Find a quiet place with good light",
    ],
    "phone": ["Make sure your phone is charged and you'll have signal", "Find a quiet place to talk"],
    "in_person": [
        "Check the address and how long it takes to get there",
        "Plan to arrive a little early",
        "Bring anything they asked for (for example ID or certificates)",
    ],
    "unknown": ["Find out whether it's remote, by phone or in person"],
}
COMMON_AFTER = [
    "Reread the job description",
    "Choose two or three examples to talk about",
    "Pick the questions you want to ask",
]

GENERIC_QUESTIONS = [
    ("role", "What would you want the person in this role to achieve in the first three months?"),
    ("team", "How does the team support each other on a busy day?"),
    ("training", "What training or onboarding is there for someone new?"),
    ("workflow", "What does a typical day or week look like?"),
    ("next_steps", "What are the next steps after this interview?"),
]
# If the posting already talks about this, say so; never hide the question for the learner.
ANSWERED_HINTS = {
    "training": r"\b(training|onboarding|induction|preceptorship|mentor\w*)\b",
    "workflow": r"\b(shifts?|rota|schedule|hours|day-to-day)\b",
    "team": r"\b(team of|multidisciplinary|teamwork)\b",
}


def clean(text: str | None) -> str:
    return _CONTROL.sub("", text or "").strip()


def _short(text: str, limit: int) -> str:
    """At most `limit` characters, cut at a word with an ellipsis (requirements can be 300 long)."""
    text = text.strip().rstrip(".")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


# Where a suggested question's requirement came from, in the learner's terms. "inferred" ones were
# added from the career profile, not found in the posting, and mustn't be described as the employer's.
_REQUIREMENT_SOURCE = {
    "explicit": "Based on a requirement in the job description you pasted",
    "user": "Based on a requirement you added to your job target",
    "inferred": "Based on a skill commonly expected in this career (not from the job description)",
}


def when_key(ev: ApplicationEvent) -> str:
    """The event's logistics as recorded: date, local time and zone (any may be unknown)."""
    return f"{ev.on_date.isoformat() if ev.on_date else ''}|{ev.local_time or ''}|{ev.timezone or ''}"


def _when(key: str) -> KitWhen:
    day, local_time, zone = (key.split("|") + ["", "", ""])[:3]
    return KitWhen(
        on_date=date.fromisoformat(day) if day else None, local_time=local_time or None, timezone=zone or None
    )


class Kits:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _event(self, app_id: str, event_id: str) -> tuple[ApplicationEvent, Application]:
        row = self.db.execute(
            select(ApplicationEvent, Application)
            .join(Application)
            .where(
                ApplicationEvent.id == event_id, Application.id == app_id, Application.user_id == self.user.id
            )
        ).first()
        if row is None:
            raise NotFoundError("Interview not found")
        return row[0], row[1]

    def _target(self, app: Application) -> RoleTarget | None:
        return self.db.get(RoleTarget, app.target_id) if app.target_id else None

    def _suggested_checklist(self, fmt: str) -> list[ChecklistItem]:
        texts = [*COMMON_BEFORE, *FORMAT_ITEMS.get(fmt, FORMAT_ITEMS["unknown"]), *COMMON_AFTER]
        return [ChecklistItem(id=f"s-{fmt}-{i}", text=t, origin="suggested") for i, t in enumerate(texts)]

    def _suggested_questions(self, target: RoleTarget | None) -> list[AskQuestion]:
        posting = (target.description if target else "") or ""
        out: list[AskQuestion] = []
        if target is not None:
            reqs = [
                r
                for r in target.requirements
                if not r.removed and r.category in ("responsibility", "required_skill", "competency")
            ]
            for r in reqs[:3]:
                source = _REQUIREMENT_SOURCE.get(r.origin, _REQUIREMENT_SOURCE["user"])
                out.append(
                    AskQuestion(
                        id=f"s-req-{r.id[:8]}",
                        text=f"How does the team approach “{_short(r.text, 240)}” day to day?",
                        group="role",
                        origin="suggested",
                        note=f"{source}: “{_short(r.text, 196 - len(source))}”",
                    )
                )
        for i, (group, text) in enumerate(GENERIC_QUESTIONS):
            note = None
            pattern = ANSWERED_HINTS.get(group)
            m = re.search(pattern, posting, re.I) if pattern else None
            if m:
                note = f"The job description mentions “{m.group(0)}”: check whether it already answers this."
            out.append(AskQuestion(id=f"s-q{i}", text=text, group=group, origin="suggested", note=note))
        return out

    def get(self, app_id: str, event_id: str) -> KitOut:
        ev, app = self._event(app_id, event_id)
        kit = self.db.get(InterviewKit, ev.id)
        target = self._target(app)
        if kit is None:
            fmt = "phone" if ev.kind == "phone_screen" else "unknown"
            return self._out(
                ev,
                app,
                target,
                fmt,
                "",
                None,
                [],
                "",
                self._suggested_checklist(fmt),
                self._suggested_questions(target),
                [],
                saved=False,
            )
        return self._out(
            ev,
            app,
            target,
            kit.format,
            kit.location,
            kit.meeting_link,
            [Interviewer(**i) for i in kit.interviewers],
            kit.notes,
            self._checklist(kit.checklist),
            [AskQuestion(**q) for q in kit.questions],
            kit.story_ids,
            saved=True,
            row=kit,
        )

    def _out(
        self,
        ev,
        app,
        target,
        fmt,
        location,
        link,
        interviewers,
        notes,
        checklist,
        questions,
        story_ids,
        *,
        saved: bool,
        row: InterviewKit | None = None,
    ) -> KitOut:
        stories, missing = [], 0
        chosen = (row.story_revisions if row is not None else None) or {}
        snaps = (row.story_snapshots if row is not None else None) or {}
        fresh = StoryFreshness(self.db, self.user.id)
        for sid in story_ids:
            s = self.db.get(ExperienceEntry, sid)
            if s is None or s.user_id != self.user.id:
                if sid not in snaps:
                    missing += 1  # deleted since it was chosen, nothing kept: said, not silently dropped
                continue
            snap = snaps.get(sid)
            stories.append(
                KitStory(
                    id=s.id,
                    title=s.title,
                    short_version=s.short_version,
                    archived=s.archived,
                    revision=s.revision,
                    chosen_revision=chosen.get(s.id),
                    prepared=PreparedStory(**{k: snap[k] for k in ("revision", "title", "short_version")})
                    if snap
                    else None,
                    freshness=fresh.assess(
                        "kit", ev.id, s, self._prepared(chosen, snaps, sid), "you chose it for this kit"
                    )
                    if row is not None
                    else None,
                )
            )
        kept = []
        for sid, snap in snaps.items():
            s = self.db.get(ExperienceEntry, sid)
            if s is None or s.user_id != self.user.id:
                kept.append(
                    KeptStory(
                        id=sid,
                        revision=snap["revision"],
                        title=snap["title"],
                        short_version=snap["short_version"],
                        text="This story is no longer available. What the kit prepared from it is kept here.",
                    )
                )
        moved = None
        if row is not None and row.event_when is not None and row.event_when != when_key(ev):
            moved = _when(row.event_when)
        return KitOut(
            event_id=ev.id,
            application_id=app.id,
            role_title=app.role_title,
            employer=app.employer,
            event_title=ev.title,
            event_kind=ev.kind,
            on_date=ev.on_date,
            local_time=ev.local_time,
            timezone=ev.timezone,
            starts_at=ev.starts_at,
            format=fmt,
            location=location,
            meeting_link=link,
            interviewers=interviewers,
            notes=notes,
            checklist=checklist,
            questions=questions,
            stories=stories,
            target_title=target.title if target else None,
            saved=saved,
            revision=row.revision if row is not None else 0,
            rescheduled_from=moved,
            missing_stories=missing,
            kept_stories=kept,
        )

    def _stored_item(self, c: ChecklistItem) -> dict:
        """What a checklist item saves as. An accepted action is kept by id only (never its words or
        its state, which stay the action's); another account's id is refused like a missing one."""
        if c.origin == "action":
            action = self.db.scalar(
                select(AcceptedAction).where(
                    AcceptedAction.id == c.action_id, AcceptedAction.user_id == self.user.id
                )
            )
            if action is None:
                raise NotFoundError("Action not found")
            return {
                "id": c.id,
                "origin": "action",
                "action_id": action.id,
                "text": "",
                "done": False,
                "hidden": c.hidden,
            }
        return {"id": c.id, "text": clean(c.text), "origin": c.origin, "done": c.done, "hidden": c.hidden}

    def _checklist(self, stored: list[dict]) -> list[ChecklistItem]:
        """The saved checklist, with each accepted action read as it is now."""
        out = []
        for c in stored:
            if c.get("origin") != "action":
                out.append(ChecklistItem(**c))
                continue
            action = self.db.scalar(
                select(AcceptedAction).where(
                    AcceptedAction.id == c.get("action_id"), AcceptedAction.user_id == self.user.id
                )
            )
            if action is None:
                out.append(
                    ChecklistItem(
                        id=c["id"],
                        origin="action",
                        action_id=c.get("action_id"),
                        text="An improvement that's no longer available",
                        hidden=c.get("hidden", False),
                    )
                )
                continue
            entries = [
                e
                for e in self.db.scalars(
                    select(ScheduleEntry).where(
                        ScheduleEntry.user_id == self.user.id,
                        ScheduleEntry.kind == "accepted_action",
                        ScheduleEntry.ref == action.id,
                        ScheduleEntry.status != "cancelled",
                    )
                )
            ]
            once = action.recurrence == "once"
            done = once and action.done_at is not None
            out.append(
                ChecklistItem(
                    id=c["id"],
                    origin="action",
                    action_id=action.id,
                    text=action.title,
                    done=done,
                    hidden=c.get("hidden", False),
                    action=KitAction(
                        id=action.id,
                        title=action.title,
                        recurrence="once" if once else "weekly",
                        done=done,
                        occurrences_done=sum(
                            1 for e in entries if (done if once else e.completed_at is not None)
                        ),
                        occurrences_total=len(entries),
                        href=action.practice_href,
                    ),
                )
            )
        return out

    def _stale(self, app_id: str, event_id: str) -> ConflictError:
        self.db.rollback()
        saved = self.get(app_id, event_id)
        return ConflictError(
            "This kit was saved somewhere else (maybe another tab) since you opened it. "
            "Your changes weren't saved; they're still on this page.",
            code="stale_revision",
            details={"current_revision": saved.revision, "current": saved.model_dump(mode="json")},
        )

    def update(self, app_id: str, event_id: str, body: KitUpdate) -> KitOut:
        current = self.get(app_id, event_id)
        ev, app = self._event(app_id, event_id)
        kit = self.db.get(InterviewKit, ev.id)
        key = body.client_request_id if body.expected_revision is not None else None
        base = body.expected_revision or 0
        print_ = update_receipts.fingerprint(
            "kit",
            ev.id,
            base,
            body.model_dump(mode="json", exclude={"client_request_id", "expected_revision"}),
        )
        if (replayed := self._replayed(app_id, event_id, key, ev.id, base, print_)) is not None:
            return replayed
        if body.expected_revision is not None and body.expected_revision != current.revision:
            raise ConflictError(
                "This kit was saved somewhere else (maybe another tab) since you opened it. "
                "Your changes weren't saved; they're still on this page.",
                code="stale_revision",
                details={"current_revision": current.revision, "current": current.model_dump(mode="json")},
            )
        if kit is None:
            kit = InterviewKit(
                event_id=ev.id,
                user_id=self.user.id,
                format=current.format,
                location="",
                interviewers=[],
                notes="",
                checklist=[c.model_dump() for c in current.checklist],
                questions=[q.model_dump() for q in current.questions],
                story_ids=[],
            )
            self.db.add(kit)
        data = body.model_dump(exclude_unset=True)
        if "location" in data and body.location is not None:
            kit.location = clean(body.location)
        if body.clear_meeting_link:
            kit.meeting_link = None
        elif body.meeting_link:
            kit.meeting_link = body.meeting_link
        if body.interviewers is not None:
            kit.interviewers = [{"name": clean(i.name), "role": clean(i.role)} for i in body.interviewers]
        if body.notes is not None:
            kit.notes = clean(body.notes)
        if body.checklist is not None:
            kit.checklist = [self._stored_item(c) for c in body.checklist]
        if body.questions is not None:
            kit.questions = [{**q.model_dump(), "text": clean(q.text)} for q in body.questions]
        # After the learner's own list is in, a new format swaps only the untouched suggestions.
        if body.format is not None and body.format != kit.format:
            kit.format = body.format
            # Switching format swaps the untouched suggestions for that format's; the learner's own
            # items, and suggestions they ticked or changed, stay.
            kept = [
                c for c in kit.checklist if c["origin"] in ("yours", "action") or c["done"] or c["hidden"]
            ]
            fresh = [
                c.model_dump()
                for c in self._suggested_checklist(body.format)
                if c.text not in {k["text"] for k in kept}
            ]
            kit.checklist = kept + fresh
        before = list(kit.story_ids or [])
        if body.story_ids is not None:
            ids = []
            for sid in dict.fromkeys(body.story_ids):
                s = self.db.get(ExperienceEntry, sid)
                if s is not None and s.user_id == self.user.id:
                    ids.append(sid)
                elif s is None and sid in before:
                    continue  # deleted since it was chosen (maybe in another tab): dropped, not an error
                else:
                    raise NotFoundError("Story not found")
            kit.story_ids = ids
        prev_revs = dict(kit.story_revisions or {})
        reviewed = set(body.reviewed_story_ids or [])
        kit.story_revisions = self._story_revisions(kit, before, reviewed)
        kit.story_snapshots = self._story_snapshots(kit.story_revisions, dict(kit.story_snapshots or {}))
        # Older clients' "I've reread it": a refresh to the story as it is now, recorded like one.
        stories = StoryFreshness(self.db, self.user.id)
        for sid in reviewed & set(kit.story_ids or []):
            s = self.db.get(ExperienceEntry, sid)
            if (
                s is not None
                and s.user_id == self.user.id
                and sid in before
                and prev_revs.get(sid) != s.revision
            ):
                stories.decide("kit", ev.id, s, Prepared(prev_revs.get(sid)), s.revision, "refresh")
        kit.event_when = when_key(ev)  # saved on this page, where a move is shown
        kit.updated_at = datetime.now(UTC)
        try:
            self.db.flush()  # the revision is bumped here
            update_receipts.record(self.db, self.user, key, "kit", ev.id, base, kit.revision, print_)
            self.db.commit()
        except (StaleDataError, IntegrityError):  # another save got there first
            self.db.rollback()
            # A copy of this same save, sent at the same moment, may be the one that got there.
            if (replayed := self._replayed(app_id, event_id, key, ev.id, base, print_)) is not None:
                return replayed
            raise self._stale(app_id, event_id) from None
        return self.get(app_id, event_id)

    def _replayed(
        self, app_id: str, event_id: str, key: str | None, entity_id: str, base: int, print_: str
    ) -> KitOut | None:
        done = update_receipts.find(self.db, self.user, key, "kit", entity_id, base, print_)
        if done is None:
            return None
        out = self.get(app_id, event_id)
        out.save_replay = SaveReplay(accepted_revision=done.accepted_revision, current_revision=out.revision)
        return out

    def _story_revisions(self, kit: InterviewKit, before: list[str], reviewed: set[str]) -> dict:
        """Each chosen story's version when it was chosen (or last marked as reread). A story newly
        chosen gets its current version; one chosen before keeps what was recorded, or stays unknown
        if nothing was (it isn't backfilled with today's version)."""
        prev = dict(kit.story_revisions or {})
        out: dict[str, int] = {}
        for sid in kit.story_ids or []:
            s = self.db.get(ExperienceEntry, sid)
            if s is None or s.user_id != self.user.id:
                continue
            if sid in reviewed or sid not in before:
                out[sid] = s.revision
            elif sid in prev:
                out[sid] = prev[sid]
        return out

    def _snapshot_at(self, s: ExperienceEntry, revision: int) -> dict | None:
        """The story at `revision` as a kit shows it, with a digest of the content it relies on."""
        if revision == s.revision:
            return {
                "revision": s.revision,
                "digest": digest(s),
                "title": s.title,
                "short_version": s.short_version,
            }
        fields = StoryFreshness(self.db, self.user.id).fields_at(s.id, revision)
        if fields is None:
            return None  # that version isn't kept any more: nothing is made up
        return {
            "revision": revision,
            "digest": digest_of(fields),
            "title": fields.get("title") or "",
            "short_version": fields.get("short_version") or "",
        }

    def _story_snapshots(self, revisions: dict, prev: dict) -> dict:
        """Each chosen story as prepared (its recorded version), and those deleted since, kept."""
        out: dict[str, dict] = {}
        for sid, rev in revisions.items():
            s = self.db.get(ExperienceEntry, sid)
            if s is None or s.user_id != self.user.id:
                continue
            snap = prev.get(sid)
            if snap is not None and snap.get("revision") == rev:
                out[sid] = snap
            elif (made := self._snapshot_at(s, rev)) is not None:
                out[sid] = made
        for sid, snap in prev.items():
            if sid in out:
                continue
            s = self.db.get(ExperienceEntry, sid)
            if s is None or s.user_id != self.user.id:
                out[sid] = snap  # deleted since: what the kit prepared from it stays until removed
        return out

    @staticmethod
    def _prepared(revisions: dict, snaps: dict, sid: str) -> Prepared:
        rev = revisions.get(sid)
        snap = snaps.get(sid)
        return Prepared(rev, snap.get("digest") if snap and snap.get("revision") == rev else None)

    def review_story(self, app_id: str, event_id: str, story_id: str, body: SourceReviewIn) -> KitOut:
        """Refresh a chosen story to the revision the learner reviewed, or keep it as prepared
        (docs/STORY_FRESHNESS.md). One transaction: a failure leaves the kit exactly as it was."""
        ev, _app = self._event(app_id, event_id)
        kit = self.db.get(InterviewKit, ev.id)
        if kit is None or story_id not in (kit.story_ids or []):
            raise NotFoundError("Story not found")
        s = self.db.get(ExperienceEntry, story_id)
        revs = dict(kit.story_revisions or {})
        snaps = dict(kit.story_snapshots or {})
        row = StoryFreshness(self.db, self.user.id).decide(
            "kit", ev.id, s, self._prepared(revs, snaps, story_id), body.reviewed_revision, body.decision
        )
        if row is None:
            return self.get(app_id, event_id)  # already so: nothing recorded twice
        if row.decision == "refreshed":
            assert s is not None
            revs[story_id] = s.revision
            snaps[story_id] = self._snapshot_at(s, s.revision) or {}
            kit.story_revisions, kit.story_snapshots = revs, snaps
            kit.updated_at = datetime.now(UTC)
        try:
            self.db.commit()
        except (StaleDataError, IntegrityError):  # the same decision from another tab got there first
            self.db.rollback()
        return self.get(app_id, event_id)

    def remove_kept(self, app_id: str, event_id: str, story_id: str) -> KitOut:
        """Remove what the kit kept from a story deleted since. Only that: nothing else changes."""
        ev, _app = self._event(app_id, event_id)
        kit = self.db.get(InterviewKit, ev.id)
        snaps = dict((kit.story_snapshots if kit is not None else None) or {})
        s = self.db.get(ExperienceEntry, story_id)
        if kit is None or story_id not in snaps or (s is not None and s.user_id == self.user.id):
            raise NotFoundError("Nothing kept for that story")
        del snaps[story_id]
        forget(self.db, self.user.id, holder_kind="kit", holder_ids=[ev.id], source_id=story_id)
        kit.story_snapshots = snaps
        kit.story_ids = [i for i in kit.story_ids or [] if i != story_id]
        kit.story_revisions = {k: v for k, v in (kit.story_revisions or {}).items() if k != story_id}
        kit.updated_at = datetime.now(UTC)
        try:
            self.db.commit()
        except StaleDataError:
            raise self._stale(app_id, event_id) from None
        return self.get(app_id, event_id)

    @staticmethod
    def new_id() -> str:
        return f"u-{uuid.uuid4().hex[:8]}"

    def export(self, *, with_ids: bool = False) -> list[dict]:
        return [
            {
                **({"id": k.event_id} if with_ids else {}),  # a kit is identified by its interview
                "event": k.event_id,
                "format": k.format,
                "location": k.location,
                "meeting_link": k.meeting_link,
                "interviewers": k.interviewers,
                "notes": k.notes,
                "checklist": k.checklist,
                "questions": k.questions,
                "stories": k.story_ids,
                # What it was last saved against (null for kits saved before these were kept).
                "revision": k.revision,
                "saved_for_event_time": k.event_when,
                "story_versions_when_chosen": k.story_revisions,
                # Each chosen story as the kit prepared it (docs/STORY_FRESHNESS.md).
                "stories_as_prepared": k.story_snapshots,
            }
            for k in self.db.scalars(
                select(InterviewKit)
                .where(InterviewKit.user_id == self.user.id)
                .order_by(InterviewKit.event_id)
            )
        ]
