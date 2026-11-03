"""Interview-day kits: one per recorded interview event.

Until the learner changes something, a kit is only suggestions (nothing is stored). Suggestions
are labelled as such and come from the event's format and the learner's own linked job target;
nothing is invented about the employer. A ticked checklist item means the learner ticked it:
CodeCoach never checks a camera, a network, documents or travel. Meeting links are kept as text
and never fetched."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Application, ApplicationEvent, ExperienceEntry, InterviewKit, RoleTarget, User
from app.schemas.kits import AskQuestion, ChecklistItem, Interviewer, KitOut, KitStory, KitUpdate

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
                out.append(
                    AskQuestion(
                        id=f"s-req-{r.id[:8]}",
                        text=f"How does the team approach “{r.text.rstrip('.')}” day to day?",
                        group="role",
                        origin="suggested",
                        note=f"Based on a requirement from your job target: “{r.text}”",
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
            [ChecklistItem(**c) for c in kit.checklist],
            [AskQuestion(**q) for q in kit.questions],
            kit.story_ids,
            saved=True,
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
    ) -> KitOut:
        stories = []
        for sid in story_ids:
            s = self.db.get(ExperienceEntry, sid)
            if s is not None and s.user_id == self.user.id:
                stories.append(KitStory(id=s.id, title=s.title, short_version=s.short_version))
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
        )

    def update(self, app_id: str, event_id: str, body: KitUpdate) -> KitOut:
        current = self.get(app_id, event_id)
        ev, app = self._event(app_id, event_id)
        kit = self.db.get(InterviewKit, ev.id)
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
            kit.checklist = [{**c.model_dump(), "text": clean(c.text)} for c in body.checklist]
        if body.questions is not None:
            kit.questions = [{**q.model_dump(), "text": clean(q.text)} for q in body.questions]
        # After the learner's own list is in, a new format swaps only the untouched suggestions.
        if body.format is not None and body.format != kit.format:
            kit.format = body.format
            # Switching format swaps the untouched suggestions for that format's; the learner's own
            # items, and suggestions they ticked or changed, stay.
            kept = [c for c in kit.checklist if c["origin"] == "yours" or c["done"] or c["hidden"]]
            fresh = [
                c.model_dump()
                for c in self._suggested_checklist(body.format)
                if c.text not in {k["text"] for k in kept}
            ]
            kit.checklist = kept + fresh
        if body.story_ids is not None:
            ids = list(dict.fromkeys(body.story_ids))
            for sid in ids:
                s = self.db.get(ExperienceEntry, sid)
                if s is None or s.user_id != self.user.id:
                    raise NotFoundError("Story not found")
            kit.story_ids = ids
        kit.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(app_id, event_id)

    @staticmethod
    def new_id() -> str:
        return f"u-{uuid.uuid4().hex[:8]}"

    def export(self) -> list[dict]:
        return [
            {
                "event": k.event_id,
                "format": k.format,
                "location": k.location,
                "meeting_link": k.meeting_link,
                "interviewers": k.interviewers,
                "notes": k.notes,
                "checklist": k.checklist,
                "questions": k.questions,
                "stories": k.story_ids,
            }
            for k in self.db.scalars(select(InterviewKit).where(InterviewKit.user_id == self.user.id))
        ]
