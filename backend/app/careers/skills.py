"""Which skills a career question practises: a stable, explainable mapping used by History filters,
Analytics and recommendations.

A question's skills are the tags that name one of its career's skills or tools (e.g. "patient
assessment", "electronic health records"). Questions without one (people-focused, scenario or
motivation questions) map to one professional competency by kind. Nothing is inferred beyond
that, and one career's skills never count toward another's.
"""

from __future__ import annotations

from functools import lru_cache

from app.careers import CATALOG
from app.careers.questions import Question, generated_questions

COMPETENCY_BY_KIND = {
    "behavioral": "Working with people",
    "situational": "Judgment under pressure",
    "leadership": "Leadership",
    "motivation": "Motivation and fit",
    "knowledge": "Core knowledge",
}


def question_skills(q: Question) -> tuple[str, ...]:
    profile = CATALOG.get(q.track)
    named = set(profile.skills) | set(profile.tools) if profile else set()
    own = tuple(t for t in q.tags if t in named)
    return own or (COMPETENCY_BY_KIND.get(q.kind, "Core knowledge"),)


@lru_cache(maxsize=256)
def career_skills(track: str) -> tuple[str, ...]:
    """Every skill a career's questions can practise, in a stable order (skills, tools, competencies)."""
    profile = CATALOG.get(track)
    if profile is None:
        return ()
    seen: dict[str, None] = {}
    for q in generated_questions(track):  # the taxonomy, retired questions included
        for s in question_skills(q):
            seen.setdefault(s, None)
    order = {s: i for i, s in enumerate((*profile.skills, *profile.tools, *COMPETENCY_BY_KIND.values()))}
    return tuple(sorted(seen, key=lambda s: order.get(s, len(order))))


@lru_cache(maxsize=256)
def questions_by_skill(track: str) -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {}
    for q in generated_questions(track):  # the taxonomy, retired questions included
        for s in question_skills(q):
            out.setdefault(s, set()).add(q.id)
    return {k: frozenset(v) for k, v in out.items()}
