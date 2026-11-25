"""Short communication drills: one objective each, a career-aware prompt, and feedback that only
describes what's in the learner's words.

Five types to start. Each says what helpful feedback looks like before the learner begins, and a
target duration only where length is part of the point (an introduction); nothing rewards speed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.careers import CATALOG, DEFAULT_TRACK

RUBRIC_VERSION = 1


@dataclass(frozen=True)
class Drill:
    id: str
    title: str
    objective: str
    looks_for: tuple[str, ...]  # what helpful feedback checks, shown before starting
    target_seconds: int | None  # only when length is the point


DRILLS: tuple[Drill, ...] = (
    Drill(
        "intro",
        "Introduce yourself briefly",
        "Say who you are, what you do or are working towards, and one thing that makes you a good fit, in about a minute.",
        (
            "Says what you do or are working towards",
            "Mentions one concrete strength or experience",
            "Ends by connecting to this kind of role",
        ),
        60,
    ),
    Drill(
        "example",
        "Answer with a concrete example",
        "Answer a short question with one specific example from your experience, not a general statement.",
        (
            "Answers the question directly",
            "Gives one specific situation",
            "Says what you did and what happened",
        ),
        None,
    ),
    Drill(
        "explain",
        "Explain it to a non-specialist",
        "Explain an idea from your work so someone outside your field would understand it.",
        (
            "Starts with the main point",
            "Uses everyday words or explains the terms you use",
            "Gives an example or comparison",
        ),
        None,
    ),
    Drill(
        "clarify",
        "Ask a clarifying question",
        "Before answering an open-ended request, ask one or two questions that would change how you answer.",
        (
            "Asks a question rather than answering straight away",
            "The question is specific to the request",
            "Says why the answer matters",
        ),
        None,
    ),
    Drill(
        "followup",
        "Respond to a follow-up",
        "Answer a follow-up that asks for more detail than you first gave.",
        ("Adds a detail you hadn't given", "Stays on the follow-up's point", "Keeps it brief"),
        None,
    ),
)
BY_ID = {d.id: d for d in DRILLS}


def prompt_for(drill: Drill, track: str) -> str:
    """The drill's prompt for a career, built from the career's own profile."""
    profile = CATALOG.get(track) or CATALOG[DEFAULT_TRACK]
    skill = profile.skills[0] if profile.skills else "your work"
    situation = profile.situations[0] if profile.situations else "a busy day"
    if drill.id == "intro":
        return f"Introduce yourself for {profile.article} {profile.role} interview."
    if drill.id == "example":
        return f"Tell me about a time {skill} really mattered in your work, studies or volunteering."
    if drill.id == "explain":
        return f"Explain {skill} to a friend who has never worked as {profile.article} {profile.role}."
    if drill.id == "clarify":
        return f"The interviewer says: “Tell me how you'd handle {situation}.” Before answering, what would you ask?"
    return f"You said you handled {situation} well. The interviewer asks: “What exactly did you do first, and why?”"
