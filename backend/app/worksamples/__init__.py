"""Work-sample practice (Volume 10, prompt 5; docs/WORK_SAMPLES.md).

A fictional brief asks for a short professional artifact (an incident status update, a customer
explanation, a project handoff note) from facts supplied in the brief. It's a different thing from
an interview answer: the learner writes the work itself, for a named audience, using only the facts
given. The briefs are files (app/seed/worksamples/*.json); app/content/validate.py refuses a brief
whose own reference artifact fails its checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).resolve().parents[1] / "seed" / "worksamples"
MAX_SECTION_CHARS = 4000


@dataclass(frozen=True)
class Section:
    id: str
    label: str
    hint: str


@dataclass(frozen=True)
class Brief:
    id: str
    version: int
    format: str
    format_label: str
    careers: tuple[str, ...]
    title: str
    scenario: str
    audience: str
    purpose: str
    facts: tuple[dict[str, str], ...]
    required: tuple[dict[str, Any], ...]
    claims_to_avoid: tuple[dict[str, Any], ...]
    avoid: tuple[dict[str, str], ...]
    sections: tuple[Section, ...]
    min_words: int
    max_words: int
    reference: dict[str, str]
    review_status: str
    scope_note: str

    @property
    def section_ids(self) -> list[str]:
        """The parts the artifact is written in: the brief's sections, or one plain message."""
        return [s.id for s in self.sections] or ["message"]

    def snapshot(self) -> dict[str, Any]:
        """What an attempt was written against, kept with it."""
        return {
            "version": self.version,
            "title": self.title,
            "format_label": self.format_label,
            "audience": self.audience,
            "purpose": self.purpose,
            "facts": [dict(f) for f in self.facts],
            "required": [
                {"id": r["id"], "label": r["label"], "guidance": r["guidance"]} for r in self.required
            ],
            "sections": [{"id": s.id, "label": s.label} for s in self.sections],
            "reference": dict(self.reference),
        }


def parse(data: dict[str, Any]) -> Brief:
    return Brief(
        id=data["id"],
        version=int(data["version"]),
        format=data["format"],
        format_label=data["format_label"],
        careers=tuple(data["careers"]),
        title=data["title"],
        scenario=data["scenario"],
        audience=data["audience"],
        purpose=data["purpose"],
        facts=tuple(data["facts"]),
        required=tuple(data["required"]),
        claims_to_avoid=tuple(data.get("claims_to_avoid", [])),
        avoid=tuple(data.get("avoid", [])),
        sections=tuple(Section(**s) for s in data.get("sections", [])),
        min_words=int(data["limits"]["min_words"]),
        max_words=int(data["limits"]["max_words"]),
        reference=dict(data["reference"]),
        review_status=data["review_status"],
        scope_note=data["scope_note"],
    )


def load(directory: Path = SEED_DIR) -> tuple[Brief, ...]:
    return tuple(parse(json.loads(p.read_text())) for p in sorted(directory.glob("*.json")))


BRIEFS = load()
BY_ID = {b.id: b for b in BRIEFS}
