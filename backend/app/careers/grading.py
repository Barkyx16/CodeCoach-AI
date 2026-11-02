"""Offline feedback on a written interview answer.

This is the free, no-API-key coach. It is honest about what it is: it checks whether an answer
covers what interviewers listen for (the question's rubric), how it's structured, and whether it's
a sensible length. It does not judge whether the content is *true* or *wise*; with an Anthropic key
the Claude provider adds that kind of judgment. The UI says which coach produced the feedback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.careers.questions import Question

MIN_WORDS, GOOD_MIN, GOOD_MAX, MAX_WORDS = 40, 120, 350, 600
# Bump when the scoring rules change, so scores from different rule sets are never compared as equals.
RUBRIC_VERSION = "v1"


@dataclass(frozen=True)
class PointResult:
    label: str
    covered: bool
    advice: str


@dataclass(frozen=True)
class Feedback:
    score: int  # 0-100
    rating: str  # "Strong", "Good", "Developing", "Needs work"
    summary: str
    points: tuple[PointResult, ...]
    notes: tuple[str, ...]  # structure and length observations
    word_count: int


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _covered(text: str, patterns: tuple[str, ...], min_hits: int) -> bool:
    hits = sum(_count(p, text) for p in patterns)
    return hits >= min_hits


def _rating(score: int) -> str:
    if score >= 85:
        return "Strong"
    if score >= 65:
        return "Good"
    if score >= 40:
        return "Developing"
    return "Needs work"


def grade(question: Question, answer: str) -> Feedback:
    text = " " + re.sub(r"\s+", " ", answer.strip()) + " "
    words = len(answer.split())
    points = tuple(
        PointResult(rp.label, _covered(text, rp.patterns, rp.min_hits), rp.advice) for rp in question.rubric
    )
    coverage = sum(p.covered for p in points) / len(points) if points else 0.0

    notes: list[str] = []
    if words < MIN_WORDS:
        length_score = 0.0
        notes.append(
            f"Only {words} words. Spoken answers usually run one to two minutes (about {GOOD_MIN}-{GOOD_MAX} words)."
        )
    elif words < GOOD_MIN:
        length_score = 0.6
        notes.append(
            f"{words} words: a little short. Add a concrete detail or example (aim for {GOOD_MIN}-{GOOD_MAX})."
        )
    elif words <= GOOD_MAX:
        length_score = 1.0
    elif words <= MAX_WORDS:
        length_score = 0.7
        notes.append(f"{words} words: on the long side. Cut background and keep the actions and result.")
    else:
        length_score = 0.4
        notes.append(f"{words} words: too long for an interview answer. Aim for under {GOOD_MAX}.")

    if question.kind in ("behavioral", "general") or any(
        "Situation" in p.label or "scene" in p.label for p in points
    ):
        i_count, we_count = _count(r"\bi\b", text), _count(r"\bwe\b", text)
        if we_count > i_count and we_count >= 3:
            notes.append("You say “we” more than “I”. Interviewers need to hear what you did.")
        if not re.search(r"\d", text):
            notes.append("No numbers yet. A figure (time, %, count) makes your result concrete.")
    filler = _count(r"\b(basically|literally|you know|kind of|sort of)\b", text)
    if filler >= 3:
        notes.append(
            "Several filler phrases (“basically”, “kind of”). Cutting them makes you sound more confident."
        )

    score = round(100 * (0.8 * coverage + 0.2 * length_score))
    if words < MIN_WORDS:
        score = min(score, 35)  # a few keywords shouldn't score well
    missed = [p for p in points if not p.covered]
    if not missed:
        summary = "You covered everything interviewers listen for in this question."
    elif len(missed) == 1:
        summary = f"Solid. One thing to add: {missed[0].label.lower()}."
    else:
        summary = f"You covered {len(points) - len(missed)} of {len(points)} key points. Start with: {missed[0].label.lower()}."
    return Feedback(
        score=score,
        rating=_rating(score),
        summary=summary,
        points=points,
        notes=tuple(notes),
        word_count=words,
    )
