"""A private practice packet (Volume 11, prompt 8; docs/PACKET.md).

The learner chooses questions, notes and stories, which parts of each, and their order; this
assembles exactly that, once, for a preview. The page builds the downloaded file (text, or the
browser's print to PDF) from that same preview, so an edit made after previewing can't change the
file; nothing is generated or stored on the server, so there's no file to guess, fetch or expire.

- Owner first, item by item: a note or story must be yours (another account's id reads "not found",
  the same as a deleted one). Questions come from the public library and only as far as its pages
  show them: the title, the prompt and the tips. Never hidden tests, sealed evaluation cases,
  model instructions or anything about other accounts; coding problems aren't offered.
- Labelled: authored question material, what you wrote, and automated feedback (with its coach,
  rubric and date, and "not a grade from a person") are separate sections, each saying where it
  came from and when, as recorded. Nothing here certifies, endorses or verifies anything.
- Private by default: email addresses and phone numbers in your own text are removed unless you
  ask to keep them; meeting links, offer terms, audio and account details aren't selectable at all.
- Bounded: at most PACKET_ITEMS items (so at most that many accepted improvements), one interview's
  kit, and MAX_CHARS characters; anything cut short says so.
- Accepted improvements and a kit (Volume 13, prompt 7) are read live, from the same records as
  their pages (app/services/actions.py, app/services/kits.py): an improvement is listed as a plan
  with the weeks you scheduled and marked done, never as an achievement; a kit gives its checklist
  (accepted improvements by id, read now) and questions to ask, and its meeting link, interviewers'
  names and your private notes only when chosen, part by part.
- Honest: a choice that can't be included (deleted, retired, repeated, not found) is listed with
  its reason, never silently dropped. An empty choice is refused: nothing is chosen for you.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.answers import answer_out
from app.careers.questions import get_question, is_retired
from app.models import (
    AcceptedAction,
    Application,
    ApplicationEvent,
    ExperienceEntry,
    InterviewKit,
    Note,
    PracticeAnswer,
    User,
)
from app.schemas.actions import ActionOut
from app.schemas.careers import AnswerOut
from app.schemas.packet import (
    DEFAULT_PARTS,
    KIT_PRIVATE_PARTS,
    PACKET_KITS,
    PacketIn,
    PacketItemIn,
    PacketItemOut,
    PacketKitChoice,
    PacketOut,
    PacketSection,
    PacketUnavailable,
)

MAX_CHARS = 150_000  # the whole packet's text
MAX_SECTION = 20_000  # one section's text
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?<![\w/])\+?\d[\d\s().-]{7,}\d(?![\w/])")
STORY_LABELS = {
    "situation": "Situation",
    "task": "Task",
    "action": "Action",
    "result": "Result",
    "reflection": "Reflection",
    "short_version": "Short version",
    "long_version": "Longer version",
}
NOT_FOUND = "Not found: it may have been deleted."


def _day(dt: datetime | None) -> str:
    return dt.date().isoformat() if dt else "date not recorded"


def _long_day(d) -> str:
    return f"{d.day} {d:%B %Y}"


PRIVATE_LEFT_OUT = {
    "meeting_link": "The meeting link isn't included: choose \u201cMeeting link\u201d to add it.",
    "interviewers": "The interviewers' names aren't included: choose \u201cInterviewers\u201d to add them.",
    "notes": "Your private kit notes aren't included: choose \u201cPrivate notes\u201d to add them.",
}


class _Budget:
    def __init__(self, keep_contact: bool):
        self.left = MAX_CHARS
        self.keep_contact = keep_contact
        self.redacted = 0
        self.shortened = False

    def own(self, text: str) -> str:
        """Your own words: contact details removed unless you chose to keep them."""
        if self.keep_contact:
            return text
        text, emails = _EMAIL.subn("[email address removed]", text)
        text, phones = _PHONE.subn("[phone number removed]", text)
        self.redacted += emails + phones
        return text

    def section(self, kind: str, heading: str, text: str, provenance: str) -> PacketSection | None:
        text = text.strip()
        if not text:
            return None
        cap = min(MAX_SECTION, self.left)
        shortened = len(text) > cap
        if shortened:
            self.shortened = True
            text = text[:cap].rstrip() + "\n[Shortened here: a packet holds a bounded amount of text.]"
        self.left = max(0, self.left - len(text))
        return PacketSection(
            kind=kind, heading=heading, text=text, provenance=provenance, shortened=shortened
        )


class Packets:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def preview(self, body: PacketIn) -> PacketOut:
        budget = _Budget(body.keep_contact_details)
        items: list[PacketItemOut] = []
        unavailable: list[PacketUnavailable] = []
        seen: set[tuple[str, str]] = set()
        kits = 0
        for choice in body.items:
            key = (choice.type, choice.id)
            if key in seen:
                unavailable.append(
                    PacketUnavailable(type=choice.type, id=choice.id, reason="Already in the packet.")
                )
                continue
            seen.add(key)
            parts = list(dict.fromkeys(choice.parts)) or list(DEFAULT_PARTS[choice.type])
            if choice.type == "kit" and kits >= PACKET_KITS:
                unavailable.append(
                    PacketUnavailable(
                        type="kit",
                        id=choice.id,
                        reason=self._kit_missing(choice.id)
                        or "A packet holds one interview's kit, so this one isn't included.",
                    )
                )
                continue
            made: PacketItemOut | str
            if choice.type == "question":
                made = self._question(choice, parts, budget)
            elif choice.type == "note":
                made = self._note(choice, parts, budget)
            elif choice.type == "story":
                made = self._story(choice, parts, budget)
            elif choice.type == "action":
                made = self._action(choice, parts, budget)
            else:
                made = self._kit(choice, parts, budget)
                if not isinstance(made, str):
                    kits += 1
            if isinstance(made, str):
                unavailable.append(PacketUnavailable(type=choice.type, id=choice.id, reason=made))
            else:
                items.append(made)
        title = body.title.strip() or "My practice packet"
        digest = hashlib.sha256(
            json.dumps(
                {"title": title, "items": [i.model_dump(mode="json") for i in items]}, sort_keys=True
            ).encode()
        ).hexdigest()[:16]
        return PacketOut(
            title=title,
            assembled_at=datetime.now(UTC),
            items=items,
            unavailable=unavailable,
            redacted=budget.redacted,
            shortened=budget.shortened,
            digest=digest,
        )

    def _question(self, choice: PacketItemIn, parts: list[str], budget: _Budget) -> PacketItemOut | str:
        track, _, qid = choice.id.partition("/")
        if track not in CATALOG or not qid:
            return "Not in the question library."
        q = get_question(track, qid)
        if q is None:
            return "Not in the question library."
        if is_retired(track, qid):
            return "Retired from the library, so it isn't included."
        sections: list[PacketSection | None] = []
        notes: list[str] = []
        if "question" in parts:
            tips = "\n".join(f"- {t}" for t in q.tips)
            text = q.prompt + (f"\n\nTips:\n{tips}" if tips else "")
            sections.append(
                budget.section(
                    "question",
                    "The question",
                    text,
                    f"Authored question, {CATALOG[track].title}, version {q.version}",
                )
            )
        if "your_answer" in parts or "feedback" in parts:
            row = self.db.scalar(
                select(PracticeAnswer)
                .where(
                    PracticeAnswer.user_id == self.user.id,
                    PracticeAnswer.track == track,
                    PracticeAnswer.question_id == qid,
                )
                .order_by(PracticeAnswer.created_at.desc(), PracticeAnswer.id.desc())
                .limit(1)
            )
            if row is None:
                notes.append(
                    "You haven't answered this question, so there's no answer or feedback to include."
                )
            else:
                a = answer_out(row)
                if "your_answer" in parts:
                    sections.append(
                        budget.section(
                            "your_answer",
                            "Your latest answer",
                            budget.own(a.answer),
                            f"Your answer, {_day(a.created_at)}, to version {a.content_version} of the question",
                        )
                    )
                if "feedback" in parts:
                    sections.append(self._feedback(a, budget))
        kept = [s for s in sections if s]
        if not kept and not notes:
            return "Nothing to include from it with the parts chosen."
        return PacketItemOut(type="question", id=choice.id, title=q.title, sections=kept, notes=notes)

    @staticmethod
    def _feedback(a: AnswerOut, budget: _Budget) -> PacketSection | None:
        lines = []
        if a.evidence_level == "sufficient":
            lines.append(f"Score: {a.score}/100 ({a.rating})")
        else:
            lines.append(
                "Not scored: the answer was too short to evaluate, or its evaluation wasn't recorded."
            )
        if a.summary:
            lines.append(a.summary)
        for p in a.points:
            lines.append(f"- {'Covered' if p.covered else 'To add'}: {p.label}. {p.advice}".rstrip())
        provenance = (
            f"Automated feedback from the {a.coach} coach, rubric {a.rubric_version}, {_day(a.created_at)}. "
            "Not a grade from a person, and not a verification of anything."
        )
        if a.evaluation_note:
            provenance += f" {a.evaluation_note}"
        return budget.section(
            "automated_feedback", "Automated feedback on that answer", "\n".join(lines), provenance
        )

    def _note(self, choice: PacketItemIn, parts: list[str], budget: _Budget) -> PacketItemOut | str:
        n = self.db.scalar(
            select(Note).where(Note.id == choice.id, Note.user_id == self.user.id, Note.deleted_at.is_(None))
        )
        if n is None:
            return NOT_FOUND
        when = f"Your note, revision {n.revision}, saved {_day(n.updated_at)}"
        sections: list[PacketSection | None] = []
        if "note" in parts:
            sections.append(budget.section("your_note", "Note", budget.own(n.body), when))
        if "reflection" in parts:
            sections.append(budget.section("your_note", "Reflection", budget.own(n.reflection or ""), when))
        if "excerpt" in parts and n.excerpt:
            source = n.source_title or "its source"
            sections.append(
                budget.section(
                    "question",
                    f"Excerpt from {source}",
                    n.excerpt,
                    f"Copied into your note from {source} when the note was made (version {n.source_version or 'not recorded'})",
                )
            )
        kept = [s for s in sections if s]
        if not kept:
            return "Nothing to include from it with the parts chosen (they're empty)."
        return PacketItemOut(type="note", id=n.id, title=n.title or "Untitled note", sections=kept)

    def _story(self, choice: PacketItemIn, parts: list[str], budget: _Budget) -> PacketItemOut | str:
        e = self.db.get(ExperienceEntry, choice.id)
        if e is None or e.user_id != self.user.id:
            return NOT_FOUND
        when = f"Your story, revision {e.revision}, saved {_day(e.updated_at)}"
        kept = [
            s
            for part in parts
            if (
                s := budget.section(
                    "your_story", STORY_LABELS[part], budget.own(getattr(e, part) or ""), when
                )
            )
        ]
        if not kept:
            return "Nothing to include from it with the parts chosen (they're empty)."
        return PacketItemOut(type="story", id=e.id, title=e.title, sections=kept)

    # --- accepted improvements and a kit (Volume 13, prompt 7) -----------------------------------

    def _action(self, choice: PacketItemIn, parts: list[str], budget: _Budget) -> PacketItemOut | str:
        from app.services.actions import Actions

        if (
            self.db.scalar(
                select(AcceptedAction.id).where(
                    AcceptedAction.id == choice.id, AcceptedAction.user_id == self.user.id
                )
            )
            is None
        ):
            return NOT_FOUND
        a = Actions(self.db, self.user).get(choice.id)  # as the plan page reads it, now
        when = (
            f"from your practice interview on {_long_day(a.source.interview_date)}"
            if a.source.interview_date
            else "from a practice interview"
        )
        state = self._plan_state(a)
        provenance = (
            f"Accepted improvement, {when} ({a.source.interview_title}); read {_long_day(datetime.now(UTC))}: "
            f"{state}. A plan you made, not a measure of improvement."
        )
        if not a.source.available:
            provenance += " The interview it came from no longer exists."
        sections: list[PacketSection | None] = []
        if "improvement" in parts:
            lines = [budget.own(a.title)]
            if a.source.why:
                lines.append(f"Why (from the automated feedback when you accepted it): {a.source.why}")
            if a.practice_label:
                lines.append(f"Practice: {a.practice_label}")
            sections.append(budget.section("your_plan", "What you planned", "\n".join(lines), provenance))
        if "schedule" in parts:
            sections.append(
                budget.section("your_plan", "Your schedule for it", self._schedule_text(a), provenance)
            )
        if "notes" in parts:
            sections.append(budget.section("your_plan", "Your notes on it", budget.own(a.notes), provenance))
        kept = [x for x in sections if x]
        if not kept:
            return "Nothing to include from it with the parts chosen (they're empty)."
        return PacketItemOut(type="action", id=a.id, title=a.title, sections=kept)

    @staticmethod
    def _plan_state(a: ActionOut) -> str:
        live = [o for o in a.occurrences if o.status != "cancelled"]
        if a.recurrence == "weekly":
            done = sum(1 for o in live if o.completed_at is not None)
            return f"weekly, {done} of {len(live)} week{'s' if len(live) != 1 else ''} marked done"
        if a.status == "done" and a.done_at:
            return f"a one-off, marked done on {_long_day(a.done_at)}"
        return "a one-off, not marked done yet" + ("" if live else " and not on your schedule")

    @staticmethod
    def _schedule_text(a: ActionOut) -> str:
        live = [o for o in a.occurrences if o.status != "cancelled"]
        if not live:
            return "Not on your schedule."
        lines = []
        for o in live:
            label = f"Week of {o.on_date.isoformat()}" if a.recurrence == "weekly" else o.on_date.isoformat()
            mark = f"marked done {_long_day(o.completed_at)}" if o.completed_at else "not marked done"
            lines.append(f"- {label}: {mark}")
        lines.append("You mark these yourself.")
        return "\n".join(lines)

    def _event(self, event_id: str) -> tuple[ApplicationEvent, Application] | None:
        row = self.db.execute(
            select(ApplicationEvent, Application)
            .join(Application, Application.id == ApplicationEvent.application_id)
            .where(ApplicationEvent.id == event_id, Application.user_id == self.user.id)
        ).first()
        return (row[0], row[1]) if row else None

    def _kit_missing(self, event_id: str) -> str | None:
        """Why a kit can't be included at all (gone, or never saved), else None."""
        found = self._event(event_id)
        if found is None:
            return NOT_FOUND
        row = self.db.get(InterviewKit, found[0].id)
        if row is None or row.user_id != self.user.id:
            return "This interview has no saved kit yet."
        return None

    def _kit(self, choice: PacketItemIn, parts: list[str], budget: _Budget) -> PacketItemOut | str:
        from app.services.kits import Kits

        if (missing := self._kit_missing(choice.id)) is not None:
            return missing
        found = self._event(choice.id)
        assert found is not None
        ev, app = found
        k = Kits(self.db, self.user).get(app.id, ev.id)  # as the kit page reads it, now
        on = f", {_long_day(k.on_date)}" if k.on_date else ""
        provenance = (
            f"Your interview-day kit for {k.event_title} ({k.role_title} at {k.employer}{on}), revision "
            f"{k.revision}; read {_long_day(datetime.now(UTC))}"
        )
        sections: list[PacketSection | None] = []
        notes: list[str] = []
        if "checklist" in parts:
            lines = []
            for c in k.checklist:
                if c.hidden:
                    continue
                if c.origin == "action" and c.action is not None:
                    total, done = c.action.occurrences_total, c.action.occurrences_done
                    extra = (
                        f" (accepted improvement, weekly: {done} of {total} marked done)"
                        if c.action.recurrence == "weekly"
                        else " (accepted improvement)"
                    )
                    lines.append(f"[{'x' if c.done else ' '}] {budget.own(c.text)}{extra}")
                elif c.origin == "action":
                    lines.append(f"[ ] {c.text}")  # "An improvement that's no longer available"
                else:
                    lines.append(f"[{'x' if c.done else ' '}] {budget.own(c.text)}")
            sections.append(budget.section("your_kit", "Checklist", "\n".join(lines), provenance))
        if "questions" in parts:
            asks = [f"- {budget.own(q.text)}" for q in k.questions if not q.excluded]
            sections.append(budget.section("your_kit", "Questions to ask", "\n".join(asks), provenance))
        if "meeting_link" in parts and k.meeting_link:
            sections.append(
                budget.section("your_kit", "Meeting link", budget.own(k.meeting_link), provenance)
            )
        if "interviewers" in parts and k.interviewers:
            names = [
                f"- {budget.own(i.name) or 'Name not recorded'}"
                + (f" ({budget.own(i.role)})" if i.role else "")
                for i in k.interviewers
            ]
            sections.append(budget.section("your_kit", "Interviewers", "\n".join(names), provenance))
        if "notes" in parts:
            sections.append(budget.section("your_kit", "Your private notes", budget.own(k.notes), provenance))
        present = {
            "meeting_link": bool(k.meeting_link),
            "interviewers": bool(k.interviewers),
            "notes": bool(k.notes.strip()),
        }
        notes = [PRIVATE_LEFT_OUT[p] for p in KIT_PRIVATE_PARTS if present[p] and p not in parts]
        kept = [x for x in sections if x]
        if not kept:
            return "Nothing to include from it with the parts chosen (they're empty)."
        title = f"Kit for {k.event_title}: {k.role_title} at {k.employer}"
        return PacketItemOut(type="kit", id=ev.id, title=title, sections=kept, notes=notes)

    def kits(self) -> list[PacketKitChoice]:
        """Your saved interview-day kits, the most recent interview first (at most 50)."""
        rows = self.db.execute(
            select(InterviewKit, ApplicationEvent, Application)
            .join(ApplicationEvent, ApplicationEvent.id == InterviewKit.event_id)
            .join(Application, Application.id == ApplicationEvent.application_id)
            .where(InterviewKit.user_id == self.user.id, Application.user_id == self.user.id)
            .order_by(ApplicationEvent.on_date.desc(), InterviewKit.updated_at.desc())
            .limit(50)
        ).all()
        return [
            PacketKitChoice(
                event_id=ev.id,
                application_id=app.id,
                event_title=ev.title,
                role_title=app.role_title,
                employer=app.employer,
                on_date=ev.on_date,
                has_meeting_link=bool(kit.meeting_link),
                has_interviewers=bool(kit.interviewers),
                has_notes=bool((kit.notes or "").strip()),
            )
            for kit, ev, app in rows
        ]
