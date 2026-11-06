"""Job profiles: the facts about each career that the question engine writes questions from.

A profile is deliberately small: the skills the job is judged on, the tools it uses, the
situations people in that job actually face, who they work with, and how success is measured.
Every field is written so it reads naturally inside a sentence:

- skills:      noun phrases            ("patient assessment")
- tools:       noun phrases            ("electronic health records")
- situations:  lower-case clauses      ("a patient's vital signs drop suddenly during your shift")
- people:      plural noun phrases     ("patients' families")
- metrics:     plural noun phrases     ("medication error rates")
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobProfile:
    slug: str
    title: str
    category: str
    summary: str
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    situations: tuple[str, ...]
    people: tuple[str, ...]
    metrics: tuple[str, ...]
    role: str  # how the job reads mid-sentence: "registered nurse"
    has_coding: bool = False

    @property
    def article(self) -> str:
        return "an" if self.role[:1].lower() in "aeiou" else "a"


def job(
    slug: str,
    title: str,
    category: str,
    summary: str,
    *,
    skills: str,
    tools: str,
    situations: str,
    people: str,
    metrics: str,
    role: str | None = None,
    has_coding: bool = False,
) -> JobProfile:
    def split(text: str) -> tuple[str, ...]:
        return tuple(part.strip() for part in text.split("|") if part.strip())

    return JobProfile(
        slug=slug,
        title=title,
        category=category,
        summary=summary,
        skills=split(skills),
        tools=split(tools),
        situations=split(situations),
        people=split(people),
        metrics=split(metrics),
        role=role or title.lower(),
        has_coding=has_coding,
    )


# Every profile must have at least this many of each, so every job gets the same full set of
# questions (checked in tests).
MIN_SKILLS, MIN_TOOLS, MIN_SITUATIONS, MIN_PEOPLE, MIN_METRICS = 8, 5, 8, 4, 4
