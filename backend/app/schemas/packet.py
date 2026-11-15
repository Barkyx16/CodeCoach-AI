"""A private practice packet (Volume 11, prompt 8; docs/PACKET.md): material you choose, in the order
you choose, assembled for a preview that is exactly what you download. Not a backup, a report, a
certificate or anything shared."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import APIModel

PACKET_ITEMS = 20  # at most, per packet

ItemType = Literal["question", "note", "story", "action", "kit"]
QUESTION_PARTS = ("question", "your_answer", "feedback")
NOTE_PARTS = ("note", "reflection", "excerpt")
STORY_PARTS = ("situation", "task", "action", "result", "reflection", "short_version", "long_version")
# An accepted improvement (Volume 13, prompt 7): what you planned and where it came from; its
# schedule (weeks scheduled and marked done, read live); your own notes on it.
ACTION_PARTS = ("improvement", "schedule", "notes")
# One interview's kit: its checklist and questions to ask by default; the meeting link, the
# interviewers' names and your private notes only when chosen, part by part.
KIT_PARTS = ("checklist", "questions", "meeting_link", "interviewers", "notes")
KIT_PRIVATE_PARTS = ("meeting_link", "interviewers", "notes")
PARTS: dict[str, tuple[str, ...]] = {
    "question": QUESTION_PARTS,
    "note": NOTE_PARTS,
    "story": STORY_PARTS,
    "action": ACTION_PARTS,
    "kit": KIT_PARTS,
}
DEFAULT_PARTS: dict[str, tuple[str, ...]] = {
    "question": ("question",),
    "note": ("note",),
    "story": ("situation", "task", "action", "result"),
    "action": ("improvement", "schedule"),
    "kit": ("checklist", "questions"),
}
PACKET_KITS = 1  # one interview's kit per packet


class PacketItemIn(APIModel):
    type: ItemType
    id: str = Field(
        min_length=1,
        max_length=200,
        description="A question as track/question_id; a note, story or accepted improvement id; a kit by its "
        "interview event's id",
    )
    parts: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Which parts to include (empty: the usual ones). question: question, your_answer, feedback. "
        "note: note, reflection, excerpt. story: situation, task, action, result, reflection, short_version, "
        "long_version. action: improvement, schedule, notes. kit: checklist, questions, and only when chosen "
        "meeting_link, interviewers, notes",
    )

    @model_validator(mode="after")
    def _known_parts(self) -> "PacketItemIn":
        unknown = [p for p in self.parts if p not in PARTS[self.type]]
        if unknown:
            raise ValueError(f"Unknown parts for a {self.type}: {', '.join(unknown)}")
        return self


class PacketIn(APIModel):
    title: str = Field(default="My practice packet", min_length=1, max_length=120)
    items: list[PacketItemIn] = Field(
        min_length=1,
        max_length=PACKET_ITEMS,
        description="In the order they'll appear. Never empty: nothing is chosen for you",
    )
    keep_contact_details: bool = Field(
        default=False,
        description="Keep email addresses and phone numbers in your own text (removed by default)",
    )


SectionKind = Literal[
    "question", "your_answer", "automated_feedback", "your_note", "your_story", "your_plan", "your_kit"
]


class PacketSection(APIModel):
    kind: SectionKind = Field(
        description="question: authored material from the library; your_*: what you wrote or planned (an "
        "accepted improvement is a plan, never an achievement); automated_feedback: what the coach said about an "
        "answer (not a grade from a person)"
    )
    heading: str
    text: str
    provenance: str = Field(description="Where it comes from, its version and date, as recorded")
    shortened: bool = Field(
        default=False, description="Cut short to keep the packet bounded (it says so in the text)"
    )


class PacketItemOut(APIModel):
    type: ItemType
    id: str
    title: str
    sections: list[PacketSection]
    notes: list[str] = Field(default_factory=list, description="Parts you chose that aren't there, and why")


class PacketUnavailable(APIModel):
    type: ItemType
    id: str
    reason: str


class PacketOut(APIModel):
    title: str
    assembled_at: datetime
    items: list[PacketItemOut]
    unavailable: list[PacketUnavailable] = Field(
        description="Chosen but not included: deleted, retired, repeated, or not found (another account's "
        "id is just not found)"
    )
    redacted: int = Field(description="Email addresses and phone numbers removed from your own text")
    shortened: bool = Field(description="Something was cut short to keep the packet bounded")
    digest: str = Field(
        description="A fingerprint of exactly this content, shown with the preview and in the file"
    )


class PacketKitChoice(APIModel):
    """A saved interview-day kit you can put in a packet (docs/PACKET.md)."""

    event_id: str
    application_id: str
    event_title: str
    role_title: str
    employer: str
    on_date: date | None
    has_meeting_link: bool
    has_interviewers: bool
    has_notes: bool
