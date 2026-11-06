"""Private reflections on real interviews.

The learner's own observations about an interview they recorded on an application, kept apart
from simulated practice and generated feedback. Next steps are suggested deterministically from
what they wrote and from content that exists; nothing is applied until they accept it, and
accepting twice never duplicates anything. An outcome changes the application only when they
ask. No AI provider is involved, nothing is sent anywhere, and reflection text is never logged.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.careers.questions import get_question, is_retired, questions_for
from app.errors import AppError, ConflictError, NotFoundError
from app.models import (
    Application,
    ApplicationEvent,
    Bookmark,
    ExperienceEntry,
    InterviewReflection,
    Note,
    ScheduleEntry,
    User,
)
from app.models import ReflectionAction as ActionRow
from app.schemas.applications import ApplicationStageIn
from app.schemas.explore import CollectionItemIn
from app.schemas.notes import NoteIn
from app.schemas.reflections import (
    ReflectionActionAccept,
    ReflectionActionEdit,
    ReflectionActionOut,
    ReflectionIn,
    ReflectionObservation,
    ReflectionOut,
    ReflectionOutcomeChange,
    ReflectionOutcomeIn,
    ReflectionSummary,
)
from app.schemas.schedule import EntryIn

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WORD = re.compile(r"[a-z][a-z'-]{2,}")
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "what",
    "when",
    "how",
    "why",
    "about",
    "your",
    "you",
    "they",
    "them",
    "asked",
    "ask",
    "question",
    "questions",
    "time",
    "tell",
    "did",
    "was",
    "were",
    "have",
    "had",
    "would",
    "could",
    "more",
    "some",
    "any",
    "again",
    "really",
    "felt",
    "feel",
    "very",
    "just",
    "like",
    "into",
    "from",
    "their",
    "there",
    "work",
    "role",
    "job",
    "interview",
    "interviewer",
    "example",
    "give",
    "gave",
    "describe",
}
# Explicit only: an outcome never moves the application unless the learner asks, and "awaiting"
# or "unknown" never move it at all (a slow reply is not a rejection).
STAGE_FOR: dict[str, str] = {
    "another_round": "interviewing",
    "offer": "offer",
    "not_selected": "closed",
    "withdrawn": "withdrawn",
}
MAX_SUGGESTIONS = 8
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?:\+?\d[\s-]?){9,}")
_ID_NUMBER = re.compile(r"\b\d{6,}\b")


def _clean(text: str) -> str:
    return _CONTROL.sub("", text).strip()


def _lines(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        c = _clean(item)
        if c and c.lower() not in {k.lower() for k in seen}:
            seen[c] = None
    return list(seen)


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def warnings_for(r: InterviewReflection) -> list[str]:
    """Gentle, non-blocking hints. The text is checked here and never logged."""
    text = " ".join(
        [
            *r.questions,
            *r.topics,
            r.clear,
            r.difficult,
            *(o["text"] for o in r.observations),
            r.follow_ups,
            *r.practice,
        ]
    )
    out = []
    if _EMAIL.search(text):
        out.append(
            "This looks like it includes an email address. Reflections are private, but you may not need anyone's contact details here."
        )
    if _PHONE.search(text) or _ID_NUMBER.search(text):
        out.append(
            "This looks like it includes a phone number or an ID number. Consider leaving identifiers out, especially about patients, clients or colleagues."
        )
    return out


class Reflections:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- lookups --------------------------------------------------------------------------------

    def _event(self, app_id: str, event_id: str) -> tuple[Application, ApplicationEvent]:
        row = self.db.execute(
            select(ApplicationEvent, Application)
            .join(Application)
            .where(
                ApplicationEvent.id == event_id, Application.id == app_id, Application.user_id == self.user.id
            )
        ).first()
        if row is None:
            raise NotFoundError("Interview not found")
        return row[1], row[0]

    def _row(self, event_id: str) -> InterviewReflection | None:
        r = self.db.get(InterviewReflection, event_id)
        return r if r is not None and r.user_id == self.user.id else None

    def _actions(self, event_id: str) -> list[ActionRow]:
        return list(
            self.db.scalars(
                select(ActionRow)
                .where(ActionRow.event_id == event_id)
                .order_by(ActionRow.created_at, ActionRow.key)
            )
        )

    @staticmethod
    def _targets(a: ActionRow) -> list[str]:
        return ["notebook", "schedule", "saved"] if a.kind == "practice" else ["notebook"]

    def _action_out(self, a: ActionRow) -> ReflectionActionOut:
        href = None
        if a.ref:
            track, _, qid = a.ref.partition("/")
            href = f"/careers/{track}/questions/{qid}"
        return ReflectionActionOut(
            id=a.id,
            kind=a.kind,
            title=a.title,
            detail=a.detail,
            ref=a.ref,
            href=href,
            status=a.status,
            targets=self._targets(a),
            target=a.target,
            applied_ref=a.applied_ref,
            applied_available=self._still_there(a),
        )

    def _still_there(self, a: ActionRow) -> bool | None:
        """Whether what an accepted step created still exists for this learner (never another's)."""
        if a.status != "accepted" or not a.applied_ref:
            return None
        if a.target == "notebook":
            n = self.db.get(Note, a.applied_ref)
            return n is not None and n.user_id == self.user.id and n.deleted_at is None  # not in the bin
        if a.target == "schedule":
            e = self.db.get(ScheduleEntry, a.applied_ref)
            return e is not None and e.user_id == self.user.id and e.status == "scheduled"
        track, _, qid = a.applied_ref.partition("/")
        return (
            self.db.scalar(
                select(Bookmark.id).where(
                    Bookmark.user_id == self.user.id,
                    Bookmark.item_type == "question",
                    Bookmark.track == track,
                    Bookmark.ref_id == qid,
                )
            )
            is not None
        )

    def _stories(self, ids: list[str] | None) -> tuple[list[str], int]:
        """The learner's stories among `ids` that still exist, and how many don't any more."""
        kept = []
        for sid in ids or []:
            s = self.db.get(ExperienceEntry, sid)
            if s is not None and s.user_id == self.user.id:
                kept.append(sid)
        return kept, len(ids or []) - len(kept)

    def _out(self, app: Application, ev: ApplicationEvent, r: InterviewReflection | None) -> ReflectionOut:
        if r is None:  # nothing saved yet: an empty, optional form
            return ReflectionOut(
                event_id=ev.id,
                application_id=app.id,
                application_archived=app.archived,
                role_title=app.role_title,
                employer=app.employer,
                stage=app.stage,
                event_title=ev.title,
                event_on=ev.on_date,
                questions=[],
                topics=[],
                clear="",
                difficult="",
                observations=[],
                follow_ups="",
                practice=[],
                story_ids=self._stories(app.story_ids)[0],  # a deleted one isn't offered back
                outcome="unknown",
                outcome_history=[],
                revision=0,
                saved=False,
                updated_at=None,
                warnings=[],
                actions=[],
            )
        return ReflectionOut(
            event_id=r.event_id,
            application_id=r.application_id,
            application_archived=app.archived,
            role_title=r.role_title,
            employer=r.employer,
            stage=r.stage,
            event_title=r.event_title,
            event_on=r.event_on,
            questions=r.questions,
            topics=r.topics,
            clear=r.clear,
            difficult=r.difficult,
            observations=[ReflectionObservation(**o) for o in r.observations],
            follow_ups=r.follow_ups,
            practice=r.practice,
            story_ids=self._stories(r.story_ids)[0],
            missing_stories=self._stories(r.story_ids)[1],
            outcome=r.outcome,
            outcome_history=[ReflectionOutcomeChange(**h) for h in r.outcome_history],
            revision=r.revision,
            saved=True,
            updated_at=r.updated_at,
            warnings=warnings_for(r),
            actions=[self._action_out(a) for a in self._actions(r.event_id)],
        )

    # --- reading --------------------------------------------------------------------------------

    def get(self, app_id: str, event_id: str) -> ReflectionOut:
        app, ev = self._event(app_id, event_id)
        return self._out(app, ev, self._row(ev.id))

    def all(
        self, q: str = "", outcome: str | None = None, include_archived: bool = True
    ) -> list[ReflectionSummary]:
        """Private search over your own reflections (in the database you own; nothing is indexed elsewhere)."""
        stmt = (
            select(InterviewReflection, Application)
            .join(Application, Application.id == InterviewReflection.application_id)
            .where(InterviewReflection.user_id == self.user.id)
            .order_by(InterviewReflection.updated_at.desc())
        )
        terms = [t for t in q.lower().split() if t]
        out = []
        for r, app in self.db.execute(stmt).all():
            if outcome and r.outcome != outcome:
                continue
            if app.archived and not include_archived:
                continue
            hay = " ".join(
                [
                    r.role_title,
                    r.employer,
                    r.event_title,
                    *r.questions,
                    *r.topics,
                    r.clear,
                    r.difficult,
                    r.follow_ups,
                    *r.practice,
                    *(o["text"] for o in r.observations),
                ]
            ).lower()
            if terms and not all(t in hay for t in terms):
                continue
            open_actions = sum(1 for a in self._actions(r.event_id) if a.status == "suggested")
            out.append(
                ReflectionSummary(
                    event_id=r.event_id,
                    application_id=r.application_id,
                    application_archived=app.archived,
                    role_title=r.role_title,
                    employer=r.employer,
                    event_title=r.event_title,
                    event_on=r.event_on,
                    outcome=r.outcome,
                    topics=r.topics,
                    open_actions=open_actions,
                    updated_at=r.updated_at,
                )
            )
        return out

    # --- writing --------------------------------------------------------------------------------

    def save(self, app_id: str, event_id: str, body: ReflectionIn) -> ReflectionOut:
        app, ev = self._event(app_id, event_id)
        r = self._row(ev.id)
        current = r.revision if r else 0
        if body.expected_revision != current:
            raise ConflictError(
                "This reflection was saved somewhere else since you opened it. Your text is still on this page.",
                code="stale_revision",
                details={"current_revision": current},
            )
        linked = set(r.story_ids if r else []) | set(app.story_ids or [])
        story_ids = []
        for sid in dict.fromkeys(body.story_ids):
            s = self.db.get(ExperienceEntry, sid)
            if s is not None and s.user_id == self.user.id:
                story_ids.append(sid)
            elif s is None and sid in linked:
                continue  # deleted since it was linked (maybe in another tab): unlinked, not an error
            else:
                raise NotFoundError("Story not found")
        if r is None:
            r = InterviewReflection(
                event_id=ev.id,
                user_id=self.user.id,
                application_id=app.id,
                role_title=app.role_title,
                employer=app.employer,
                stage=app.stage,
                event_title=ev.title,
                event_on=ev.on_date,
                outcome="unknown",
                outcome_history=[],
                revision=0,
            )
            self.db.add(r)
        r.questions, r.topics, r.practice = _lines(body.questions), _lines(body.topics), _lines(body.practice)
        r.clear, r.difficult, r.follow_ups = (
            _clean(body.clear),
            _clean(body.difficult),
            _clean(body.follow_ups),
        )
        r.observations = [
            {"text": _clean(o.text), "kind": o.kind} for o in body.observations if _clean(o.text)
        ]
        r.story_ids = story_ids
        r.revision = current + 1
        r.updated_at = datetime.now(UTC)
        self.db.commit()
        return self._out(app, ev, r)

    def suggest(self, app_id: str, event_id: str) -> ReflectionOut:
        """Turn what the learner wrote into suggestions. Accepted and dismissed ones are left alone,
        and nothing is applied. Interpretations ("they disliked me") are never acted on."""
        app, ev = self._event(app_id, event_id)
        r = self._row(ev.id)
        if r is None:
            raise AppError(
                "Save your reflection first; suggestions come only from what you wrote.", code="nothing_saved"
            )
        track = self.user.career_track
        bank = [q for q in questions_for(track) if not is_retired(track, q.id)]
        wanted: list[tuple[str, str]] = [(t, "topic") for t in r.topics] + [
            (p, "practice") for p in r.practice
        ]
        wanted += [(q, "question") for q in r.questions]
        if r.difficult:
            wanted.append((r.difficult, "difficult"))
        fresh: list[dict] = []
        used: set[str] = set()
        for text, source in wanted:
            terms = _terms(text)
            if not terms:
                continue
            scored = sorted(
                ((len(terms & _terms(" ".join([q.title, *q.tags]))), q) for q in bank),
                key=lambda x: (-x[0], x[1].id),
            )
            best = [q for n, q in scored if n > 0 and q.id not in used][:1]
            label = text if len(text) <= 80 else text[:79] + "…"
            if best:
                q = best[0]
                used.add(q.id)
                fresh.append(
                    {
                        "key": f"practice:{track}/{q.id}",
                        "kind": "practice",
                        "title": f"Practise: {q.title}",
                        "detail": f"From your reflection ({source}): “{label}”.",
                        "ref": f"{track}/{q.id}",
                    }
                )
            elif source in ("topic", "practice"):
                fresh.append(
                    {
                        "key": f"gap:{text.lower()[:150]}",
                        "kind": "gap",
                        "title": f"No practice here yet for “{label}”",
                        "detail": "CodeCoach has nothing that covers this, so no lesson is suggested. You can keep it as a note of what to learn elsewhere.",
                        "ref": None,
                    }
                )
        if r.follow_ups:
            fresh.append(
                {
                    "key": "note:follow-ups",
                    "kind": "note",
                    "title": "Keep a note of what you said you'd do",
                    "detail": r.follow_ups,
                    "ref": None,
                }
            )
        existing = {a.key: a for a in self._actions(r.event_id)}
        for s in fresh[:MAX_SUGGESTIONS]:
            if s["key"] in existing:
                continue  # never resurrect a dismissed one or touch an accepted one
            self.db.add(ActionRow(event_id=r.event_id, user_id=self.user.id, status="suggested", **s))
        self.db.commit()
        return self._out(app, ev, r)

    def _action(self, event_id: str, action_id: str) -> ActionRow:
        a = self.db.get(ActionRow, action_id)
        if a is None or a.event_id != event_id or a.user_id != self.user.id:
            raise NotFoundError("Suggestion not found")
        return a

    def edit_action(
        self, app_id: str, event_id: str, action_id: str, body: ReflectionActionEdit
    ) -> ReflectionOut:
        app, ev = self._event(app_id, event_id)
        a = self._action(ev.id, action_id)
        if a.status == "accepted":
            raise ConflictError(
                "This step was already added. Change it where it went (your notebook, schedule or Saved).",
                code="already_accepted",
            )
        if body.title is not None:
            a.title = _clean(body.title) or a.title
        if body.detail is not None:
            a.detail = _clean(body.detail)
        if body.status is not None:
            a.status = body.status
        a.updated_at = datetime.now(UTC)
        self.db.commit()
        return self._out(app, ev, self._row(ev.id))

    def accept(
        self, app_id: str, event_id: str, action_id: str, body: ReflectionActionAccept
    ) -> ReflectionOut:
        app, ev = self._event(app_id, event_id)
        a = self._action(ev.id, action_id)
        if a.status == "accepted":
            # Accepting twice changes nothing and creates nothing new, even if what it created was
            # removed since: that's shown (applied_available), not silently recreated.
            return self._out(app, ev, self._row(ev.id))
        if body.target not in self._targets(a):
            raise AppError("This step can only go to your notebook.", code="invalid_target")
        if body.target == "schedule" and body.on_date is None:
            raise AppError("Choose a date for the schedule.", code="date_required")
        track, _, qid = (a.ref or "").partition("/")
        if body.target == "saved" and get_question(track, qid) is None:
            raise NotFoundError("That question isn't in the library any more")
        # Claim the step before creating anything. The conditional UPDATE takes the row's write
        # lock, so a second accept at the same moment waits, then finds it accepted and creates
        # nothing (a lookup followed by a create wouldn't guarantee that).
        claimed = self.db.execute(
            update(ActionRow)
            .where(ActionRow.id == a.id, ActionRow.status != "accepted")
            .values(status="accepted", target=body.target, updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:  # type: ignore[attr-defined]
            self.db.rollback()
            return self._out(app, ev, self._row(ev.id))
        applied: str | None
        try:
            if body.target == "notebook":
                from app.services.notes import Notebook

                note = Notebook(self.db).create(
                    self.user,
                    NoteIn(
                        title=a.title[:200],
                        body=f"{a.detail}\n\nFrom your reflection on {app.role_title} at {app.employer} ({ev.title}).",
                        tags=["interview reflection"],
                    ),
                    commit=False,  # saved together with the claim, or not at all
                )
                applied = note.id
            elif body.target == "schedule":
                from app.services.schedule import Schedule

                entry, _ = Schedule(self.db, self.user).create(
                    EntryIn(
                        kind="question",
                        ref=a.ref or "",
                        on_date=body.on_date,
                        all_day=True,
                        timezone=body.timezone,
                        notes="From your interview reflection",
                        client_request_id=f"reflection-{a.id}",  # its own key: never a second entry
                    )
                )
                applied = entry.id
            else:
                from app.services.explore import Explorer

                Explorer(self.db).set_bookmark(
                    self.user, CollectionItemIn(item_type="question", track=track, ref_id=qid), True
                )
                applied = a.ref
            self.db.execute(
                update(ActionRow)
                .where(ActionRow.id == a.id)
                .values(applied_ref=applied)
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
        except Exception:
            self.db.rollback()  # the claim goes too: the step stays suggested
            raise
        self.db.expire_all()
        return self._out(app, ev, self._row(ev.id))

    def set_outcome(self, app_id: str, event_id: str, body: ReflectionOutcomeIn) -> ReflectionOut:
        app, ev = self._event(app_id, event_id)
        r = self._row(ev.id)
        if r is None:
            raise AppError("Save your reflection first.", code="nothing_saved")
        move = body.update_application and body.outcome in STAGE_FOR and app.stage != STAGE_FOR[body.outcome]
        if body.outcome == r.outcome and not move:
            return self._out(app, ev, r)  # a repeat (another click, a resend) adds no history
        try:
            if move:
                from app.services.applications import Applications

                Applications(self.db, self.user).set_stage(
                    app.id,
                    ApplicationStageIn(
                        stage=STAGE_FOR[body.outcome], note="Recorded from your interview reflection"
                    ),
                    commit=False,  # saved with the outcome below, or neither is
                )
            r.outcome = body.outcome
            r.outcome_history = [
                *r.outcome_history,
                {
                    "outcome": body.outcome,
                    "at": datetime.now(UTC).isoformat(),
                    "applied_to_application": move,
                },
            ]
            r.updated_at = datetime.now(UTC)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(app)
        return self._out(app, ev, r)

    def export(self, *, with_ids: bool = False) -> list[dict]:
        out = []
        for r in self.db.scalars(
            select(InterviewReflection)
            .where(InterviewReflection.user_id == self.user.id)
            .order_by(InterviewReflection.event_id)
        ):
            out.append(
                {
                    "event_id": r.event_id,
                    "application_id": r.application_id,
                    "role_title": r.role_title,
                    "employer": r.employer,
                    "stage": r.stage,
                    "event_title": r.event_title,
                    "event_on": r.event_on.isoformat() if r.event_on else None,
                    "questions": r.questions,
                    "topics": r.topics,
                    "clear": r.clear,
                    "difficult": r.difficult,
                    "observations": r.observations,
                    "follow_ups": r.follow_ups,
                    "practice": r.practice,
                    "story_ids": r.story_ids,
                    "outcome": r.outcome,
                    "outcome_history": r.outcome_history,
                    "updated_at": r.updated_at.isoformat(),
                    "actions": [
                        {
                            **({"id": a.id} if with_ids else {}),
                            "kind": a.kind,
                            "title": a.title,
                            "detail": a.detail,
                            "ref": a.ref,
                            "status": a.status,
                            "target": a.target,
                            "applied_ref": a.applied_ref,
                        }
                        for a in self._actions(r.event_id)
                    ],
                }
            )
        return out
