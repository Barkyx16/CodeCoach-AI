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
- Bounded: at most PACKET_ITEMS items and MAX_CHARS characters; anything cut short says so.
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
from app.models import ExperienceEntry, Note, PracticeAnswer, User
from app.schemas.careers import AnswerOut
from app.schemas.packet import (
    DEFAULT_PARTS,
    PacketIn,
    PacketItemIn,
    PacketItemOut,
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
        for choice in body.items:
            key = (choice.type, choice.id)
            if key in seen:
                unavailable.append(
                    PacketUnavailable(type=choice.type, id=choice.id, reason="Already in the packet.")
                )
                continue
            seen.add(key)
            parts = list(dict.fromkeys(choice.parts)) or list(DEFAULT_PARTS[choice.type])
            made = (
                self._question(choice, parts, budget)
                if choice.type == "question"
                else self._note(choice, parts, budget)
                if choice.type == "note"
                else self._story(choice, parts, budget)
            )
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
