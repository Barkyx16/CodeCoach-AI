"""Drill feedback: observations grounded in the learner's own words, never a judgment of them.

- Measurements are only what was measured: the word count of the text, and, for a spoken answer,
  how long the microphone was on (pauses included; nothing is recorded). A reading-time figure is labelled as an estimate and never
  stands in for spoken time.
- Filler sounds ("um", "uh") are left out of the counts and never criticised, whether speech
  recognition wrote them down or they were typed: the same words get the same evaluation however
  they were entered. Neither are pauses, accents or choosing to type.
- Nothing rewards a shorter or faster answer.
"""

from __future__ import annotations

import re

from app.drills import RUBRIC_VERSION, Drill

FILLERS = re.compile(r"\b(um+|uh+|erm+|hmm+|mm+)\b[,.]?\s*", re.I)
GENERAL = [
    "hard worker",
    "team player",
    "people person",
    "always",
    "never",
    "everyone",
    "everything",
    "very good at",
    "really good at",
    "passionate",
    "perfectionist",
]
_WORD = re.compile(r"[A-Za-z0-9']+")
_SENT = re.compile(r"(?<=[.!?])\s+")


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def clean_transcript(text: str) -> tuple[str, int]:
    """Text without recognised filler sounds, and how many were set aside."""
    found = len(FILLERS.findall(text))
    return re.sub(r"\s{2,}", " ", FILLERS.sub("", text)).strip(), found


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I) is not None


def observations(drill: Drill, prompt: str, text: str) -> list[dict]:
    """Each: {point (what helpful feedback looks for), present (bool), detail (from their words)}."""
    t = text
    first = _SENT.split(t.strip())[0] if t.strip() else ""
    prompt_terms = {w.lower() for w in words(prompt) if len(w) > 4}
    shared = sorted({w.lower() for w in words(t) if w.lower() in prompt_terms})
    checks: list[tuple[str, bool, str]] = []
    if drill.id == "intro":
        checks = [
            (
                drill.looks_for[0],
                _has(r"\b(I'?m|I am|I work|I've been|I studied|I'm studying|I'm training|my role)\b", t),
                "Says what you do",
            ),
            (
                drill.looks_for[1],
                _has(r"\b(experience|years?|led|helped|built|cared|managed|trained|worked on|handled)\b", t),
                "Names a strength or experience",
            ),
            (
                drill.looks_for[2],
                _has(
                    r"\b(this role|this job|this position|that's why|which is why|so I|looking for|want to)\b",
                    t,
                ),
                "Connects it to the role",
            ),
        ]
    elif drill.id == "example":
        checks = [
            (
                drill.looks_for[0],
                bool(shared) or _has(r"\b(yes|one time|for example)\b", first),
                "Answers the question",
            ),
            (
                drill.looks_for[1],
                _has(r"\b(last (week|month|year)|once|one time|when I|in (19|20)\d\d|on my|during)\b", t),
                "A specific situation",
            ),
            (
                drill.looks_for[2],
                _has(r"\bI (did|asked|checked|called|built|fixed|explained|took|made|decided|led)\b", t)
                and _has(r"\b(result|so|then|after|because of|which meant)\b", t),
                "Your action and what happened",
            ),
        ]
    elif drill.id == "explain":
        sentences = [s for s in _SENT.split(t.strip()) if s]
        avg = sum(len(words(s)) for s in sentences) / max(1, len(sentences))
        checks = [
            (
                drill.looks_for[0],
                len(words(first)) <= 30,
                "The first sentence carries the main point"
                if len(words(first)) <= 30
                else f"The first sentence is {len(words(first))} words long",
            ),
            (drill.looks_for[1], avg <= 22, f"Sentences average {round(avg)} words"),
            (
                drill.looks_for[2],
                _has(r"\b(like|for example|imagine|such as|think of|similar to)\b", t),
                "An example or comparison",
            ),
        ]
    elif drill.id == "clarify":
        checks = [
            (drill.looks_for[0], "?" in t, "Asks a question"),
            (
                drill.looks_for[1],
                "?" in t and bool(shared or _has(r"\b(which|what kind|how many|who|when|where)\b", t)),
                "The question is specific",
            ),
            (
                drill.looks_for[2],
                _has(r"\b(because|so that|so I|depends|that way|which would)\b", t),
                "Says why it matters",
            ),
        ]
    else:  # followup
        checks = [
            (
                drill.looks_for[0],
                _has(r"\b(first|then|\d+|specifically|exactly)\b", t),
                "Adds a specific detail",
            ),
            (drill.looks_for[1], bool(shared), "Stays on the follow-up's point"),
            (drill.looks_for[2], len(words(t)) <= 120, f"{len(words(t))} words"),
        ]
    return [{"point": p, "present": ok, "detail": d} for p, ok, d in checks]


def generalities(text: str) -> list[str]:
    """Broad claims with nothing concrete beside them. Pointed out, not penalised."""
    low = text.lower()
    found = [g for g in GENERAL if re.search(rf"\b{re.escape(g)}\b", low)]
    concrete = re.search(r"\b(for example|when I|once|last|\d+)\b", low)
    return [] if concrete else found[:3]


def evaluate(drill: Drill, prompt: str, text: str, source: str, spoken_seconds: int | None) -> dict:
    # The same for typed and spoken answers: identical words get an identical evaluation.
    cleaned, fillers = clean_transcript(text)
    n = len(words(cleaned))
    measured: dict = {"words": n}
    if source == "voice" and spoken_seconds is not None:
        measured["spoken_seconds"] = spoken_seconds  # how long the microphone was on, pauses included
    measured["reading_estimate_seconds"] = round(
        n / 150 * 60
    )  # an estimate at 150 words a minute, never spoken time
    notes = []
    if fillers:
        origin = " from speech recognition" if source == "voice" else ""
        notes.append(
            f"{fillers} filler sound{'s' if fillers != 1 else ''}{origin} {'were' if fillers != 1 else 'was'} left out of the counts. They aren't marked down."
        )
    if drill.target_seconds:
        notes.append(f"The aim is about {drill.target_seconds} seconds; that's a guide, not a score.")
    return {
        "rubric_version": RUBRIC_VERSION,
        "observations": observations(drill, prompt, cleaned),
        "generalities": generalities(cleaned),
        "measured": measured,
        "notes": notes,
        "limitations": "Built-in rules that look for the points above in your words. They can miss a good answer phrased differently, and they say nothing about your accent, voice, pauses or whether you typed.",
    }


def compare(old: dict, new: dict) -> list[str]:
    """What changed between two attempts at the same drill under the same rubric version."""
    if old.get("rubric_version") != new.get("rubric_version"):
        return ["These attempts were checked with different rubric versions, so they aren't compared."]
    before = {o["point"]: o["present"] for o in old.get("observations", [])}
    out = []
    for o in new.get("observations", []):
        was = before.get(o["point"])
        if was is False and o["present"]:
            out.append(f"Now there: {o['point'].lower()}.")
        elif was is True and not o["present"]:
            out.append(f"Not there this time: {o['point'].lower()}.")
    if not out:
        out.append("The same points are there as last time.")
    return out
