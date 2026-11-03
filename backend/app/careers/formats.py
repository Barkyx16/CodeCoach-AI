"""Interview formats for question rounds, panel roles and follow-up rules.

Formats reuse the question bank, the rubric grader and the round engine; only which questions
are picked, who asks them and whether a follow-up is asked differ.

- mixed:       the original five-question round (one of each kind). No follow-ups.
- behavioral:  five "tell me about a time" questions (behavioral, leadership, motivation).
- situational: five "what would you do" scenarios.
- technical:   five professional-knowledge questions.
- panel:       a simulated panel with authored roles (only careers with a reviewed panel).

Follow-ups are chosen from what the answer actually missed, mapped to a small set of details
(e.g. the result, what you personally did). A detail that any earlier answer in the session
already supplied, or that was already asked about, is never asked for again. At most one
follow-up per question and MAX_FOLLOWUPS per session; no model is called.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.careers import CATALOG
from app.careers.questions import Question, questions_for

FormatId = Literal["mixed", "behavioral", "situational", "technical", "panel"]
FORMAT_VERSION = "formats v1"
MAX_FOLLOWUPS = 2

KIND_LABEL = {
    "knowledge": "Professional knowledge",
    "behavioral": "A time you did it (behavioral)",
    "situational": "What would you do (scenario)",
    "leadership": "Leading or influencing others",
    "motivation": "Why this work",
}


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    objective: str
    kinds: tuple[str, ...]  # question kinds this role asks, in preference order
    probes: tuple[str, ...]  # details this role follows up on, in priority order


@dataclass(frozen=True)
class FormatDef:
    id: FormatId
    title: str
    practices: str
    kinds: tuple[str, ...]
    probes: tuple[str, ...]
    followups: bool


FORMATS: dict[str, FormatDef] = {
    "mixed": FormatDef(
        "mixed",
        "Mixed interview",
        "One of each kind of question: why this work, knowledge, a scenario, a time you did it, leading others.",
        (),
        (),
        False,
    ),
    "behavioral": FormatDef(
        "behavioral",
        "Behavioral interview",
        "Real examples from your experience, told with situation, task, action and result.",
        ("behavioral", "leadership", "motivation"),
        ("ownership", "result", "numbers", "learning"),
        True,
    ),
    "situational": FormatDef(
        "situational",
        "Situational interview",
        "How you'd handle realistic situations: what you'd do first, who you'd involve and how you'd follow up.",
        ("situational",),
        ("priority", "communication", "followthrough", "reasoning"),
        True,
    ),
    "technical": FormatDef(
        "technical",
        "Technical / professional interview",
        "What you know about the work and how you'd explain and apply it.",
        ("knowledge",),
        ("reasoning", "example", "numbers"),
        True,
    ),
    "panel": FormatDef(
        "panel",
        "Panel interview (simulated)",
        "Three simulated interviewers take turns, each with their own focus. One speaks at a time.",
        (),
        (),
        True,
    ),
}

# Reviewed panel configurations. Roles are generic job titles, never a real employer or person.
PANELS: dict[str, tuple[Role, ...]] = {
    "software-engineer": (
        Role(
            "hiring_manager",
            "Engineering manager",
            "Ownership, motivation and how you work with a team",
            ("motivation", "behavioral", "leadership"),
            ("ownership", "result", "learning"),
        ),
        Role(
            "peer",
            "Senior engineer (peer)",
            "How you reason about technical problems",
            ("knowledge", "situational"),
            ("reasoning", "example", "numbers"),
        ),
        Role(
            "partner",
            "Product manager (cross-functional partner)",
            "Communication, priorities and trade-offs with other teams",
            ("situational", "behavioral"),
            ("communication", "priority", "result"),
        ),
    ),
    "registered-nurse": (
        Role(
            "hiring_manager",
            "Nurse manager",
            "Motivation, accountability and teamwork on the unit",
            ("motivation", "behavioral", "leadership"),
            ("ownership", "result", "learning"),
        ),
        Role(
            "peer",
            "Charge nurse (peer)",
            "Clinical judgment and safe practice",
            ("knowledge", "situational"),
            ("priority", "reasoning", "followthrough"),
        ),
        Role(
            "partner",
            "Physician colleague (interdisciplinary partner)",
            "Clear, structured communication and escalation",
            ("situational", "behavioral"),
            ("communication", "priority", "result"),
        ),
    ),
}
# Who asks each of the five panel questions: opens and closes with the hiring manager.
PANEL_ORDER = ("hiring_manager", "peer", "partner", "peer", "hiring_manager")

PROBE_QUESTION = {
    "ownership": "What did you personally do there, as opposed to the team?",
    "result": "What was the outcome, and how did you know it worked?",
    "numbers": "Can you put a number on it: time, people, errors, cost or anything you measured?",
    "learning": "Looking back, what would you do differently next time?",
    "priority": "What would you do first, and why that first?",
    "communication": "Who would you keep informed, and how would you tell them?",
    "followthrough": "How would you follow up afterwards to make sure it was resolved?",
    "reasoning": "Why that approach rather than the alternatives?",
    "example": "Can you give a concrete example from your own work?",
}
# Detail detectors: deliberately simple and disclosed. A detail counts as supplied when the
# answer contains one of these patterns.
DETAIL_PATTERNS = {
    "ownership": r"\bI (?:led|did|decided|made|wrote|built|called|checked|took|asked|started|set|fixed|found|owned|stayed|moved|spoke|told|reviewed|organi[sz]ed)\b",
    "result": r"\b(as a result|result|outcome|which meant|so that|led to|reduced|improved|resolved|stable|fixed|recovered|succeeded|increased|decreased)\b",
    "numbers": r"\d",
    "learning": r"\b(learn(?:ed|t)|next time|differently|now I|since then|lesson)\b",
    "priority": r"\b(first|priorit|before anything|immediately|right away|most urgent)\b",
    "communication": r"\b(told|inform|updat|call(?:ed)?|explain|email|message|escalat|let .* know|handoff|sbar)\b",
    "followthrough": r"\b(follow(?:ed)? up|afterwards|check(?:ed)? back|reassess|monitor|document)\b",
    "reasoning": r"\b(because|so that|trade-?off|instead of|rather than|the reason|chose|weigh)\b",
    "example": r"\b(for example|for instance|once|last (?:year|month|week|winter|summer)|at my last|in my (?:last|previous))\b",
}


def details_in(text: str) -> set[str]:
    return {k for k, pattern in DETAIL_PATTERNS.items() if re.search(pattern, text, re.IGNORECASE)}


def choose_probe(answer: str, probes: tuple[str, ...], supplied: set[str], asked: set[str]) -> str | None:
    """The first detail in priority order that this answer lacks, that no earlier answer in the
    session supplied, and that hasn't been asked about yet."""
    present = details_in(answer)
    for p in probes:
        if p not in present and p not in supplied and p not in asked:
            return p
    return None


def panel_roles(track: str) -> tuple[Role, ...] | None:
    return PANELS.get(track)


def _pool(track: str, difficulty: str) -> list[Question]:
    return [q for q in questions_for(track) if q.difficulty == difficulty]


def availability(track: str, fmt: str, difficulty: str) -> tuple[bool, str | None]:
    """(available, reason) for a format at a level. Only formats the bank can fill are offered."""
    if track not in CATALOG:
        return False, "Unknown career"
    pool = _pool(track, difficulty)
    level = difficulty.capitalize()
    if fmt == "mixed":
        return (len(pool) >= 5, None if len(pool) >= 5 else f"Not enough {level} questions")
    if fmt == "panel":
        roles = panel_roles(track)
        if roles is None:
            return False, (
                f"There's no reviewed panel for {CATALOG[track].title} yet, so a panel would only be generic "
                "questions. Try a single-interviewer format."
            )
        for role in roles:
            if not any(q.kind in role.kinds for q in pool):
                return False, f"Not enough {level} questions for the {role.title.lower()}; try another level."
        return True, None
    d = FORMATS[fmt]
    n = sum(q.kind in d.kinds for q in pool)
    if n < 5:
        other = [
            lv
            for lv in ("easy", "medium", "hard")
            if lv != difficulty and sum(q.kind in d.kinds for q in _pool(track, lv)) >= 5
        ]
        hint = f" Try {' or '.join(x.capitalize() for x in other)}." if other else ""
        return False, f"{CATALOG[track].title} has {n} {level} questions of this kind (5 needed).{hint}"
    return True, None


def pick_format(
    track: str, fmt: str, difficulty: str, answered: set[str], shuffled: list[Question]
) -> tuple[list[Question], list[str | None]]:
    """Five questions for a format, unanswered first, and who asks each (panel only).
    `shuffled` is the level's pool in random order (the caller owns the randomness)."""
    ranked = sorted(shuffled, key=lambda q: q.id in answered)
    if fmt == "panel":
        roles = {r.id: r for r in panel_roles(track) or ()}
        picked: list[Question] = []
        speakers: list[str | None] = []
        for role_id in PANEL_ORDER:
            role = roles[role_id]
            q = next(
                (x for kind in role.kinds for x in ranked if x.kind == kind and x not in picked),
                None,
            )
            if q is not None:
                picked.append(q)
                speakers.append(role_id)
        return picked, speakers
    kinds = FORMATS[fmt].kinds
    chosen = [q for q in ranked if q.kind in kinds][:5]
    return chosen, [None] * len(chosen)


def probes_for(fmt: str, track: str, speaker: str | None) -> tuple[str, ...]:
    if fmt == "panel" and speaker:
        role = next((r for r in panel_roles(track) or () if r.id == speaker), None)
        return role.probes if role else ()
    return FORMATS[fmt].probes
