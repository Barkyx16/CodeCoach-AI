"""Comparing authored sample answers (Volume 10, prompt 6; docs/COMPARE_ANSWERS.md).

A lesson shows a question and two or three short sample answers, each split into numbered
sentences so a learner can select excerpts by keyboard and quotes stay anchored to this version of
the text. The learner marks excerpts as strengths or gaps with a reason, then reveals an authored
explanation tied to the lesson's rubric. Lessons are files (app/seed/comparisons/*.json), written
for teaching with fictional details: never learners' answers, never the sealed evaluation data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).resolve().parents[1] / "seed" / "comparisons"


@dataclass(frozen=True)
class Lesson:
    id: str
    version: int
    title: str
    teaching_goal: str
    question: str
    rubric: tuple[dict[str, str], ...]
    kind: str  # clear | tradeoff
    samples: tuple[dict[str, Any], ...]
    explanation: dict[str, Any]
    next_step: dict[str, str]
    review_status: str

    def sentence(self, sample_id: str, sentence_id: str) -> str | None:
        for s in self.samples:
            if s["id"] == sample_id:
                return next((x["text"] for x in s["sentences"] if x["id"] == sentence_id), None)
        return None

    def snapshot(self) -> dict[str, Any]:
        """What an attempt was made against, kept with it: the text and the explanation shown."""
        return {
            "version": self.version,
            "title": self.title,
            "question": self.question,
            "rubric": [dict(r) for r in self.rubric],
            "kind": self.kind,
            "samples": [dict(s) for s in self.samples],
            "explanation": dict(self.explanation),
        }


def parse(data: dict[str, Any]) -> Lesson:
    return Lesson(
        id=data["id"],
        version=int(data["version"]),
        title=data["title"],
        teaching_goal=data["teaching_goal"],
        question=data["question"],
        rubric=tuple(data["rubric"]),
        kind=data["kind"],
        samples=tuple(data["samples"]),
        explanation=dict(data["explanation"]),
        next_step=dict(data["next_step"]),
        review_status=data["review_status"],
    )


def load(directory: Path = SEED_DIR) -> tuple[Lesson, ...]:
    return tuple(parse(json.loads(p.read_text())) for p in sorted(directory.glob("*.json")))


LESSONS = load()
BY_ID = {lesson.id: lesson for lesson in LESSONS}
