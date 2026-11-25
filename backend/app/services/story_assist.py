"""The story bank's built-in writing help: rules, not a model, and nothing leaves the server.

It can only remove words (filler, hedges, repeated sentences) or ask questions. It never adds a
word, a number, an employer, a qualification or a claim: every proposal is checked to contain
only words that were already in the learner's text, and a proposal that fails the check is
dropped. Uncertain facts become questions for the learner."""

from __future__ import annotations

import re

from app.schemas.stories import REQUIRED_SECTIONS, StoryProposal

METHOD = "Built-in writing check: fixed rules, not AI. Your story isn't sent anywhere."

PROMPTS = {
    "situation": "Situation: where were you, and what was going on? One or two sentences is enough.",
    "task": "Task: what were you responsible for, or what needed to happen?",
    "action": "Action: what did you do, step by step?",
    "result": "Result: what changed because of what you did? A number isn't required.",
}

# Filler that rarely carries meaning. Removing it never changes a fact.
FILLER = [
    r"\bbasically\b,?\s*",
    r"\bactually\b,?\s*",
    r"\breally\s+",
    r"\bvery\s+",
    r"\bjust\s+",
    r"\bliterally\s+",
    r"\bkind of\s+",
    r"\bsort of\s+",
    r"\bat the end of the day,?\s*",
    r"\bto be honest,?\s*",
    r"\bin order to\b",
]
# Hedges that undersell what the learner did (clarity). Still only removals.
HEDGES = [
    r"\bI think\s+(?:that\s+)?",
    r"\bI guess\s+",
    r"\bI believe\s+(?:that\s+)?",
    r"\bsomewhat\s+",
    r"\ba bit\s+",
]
VAGUE = [
    "helped with",
    "was involved in",
    "worked on",
    "dealt with",
    "took care of",
    "handled things",
    "stuff",
    "things like that",
]

_WORD = re.compile(r"[A-Za-z0-9']+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def _only_removes(original: str, proposed: str) -> bool:
    """Every word in the proposal was already in the original (and so every number)."""
    have = {w.lower() for w in words(original)}
    return all(w.lower() in have for w in words(proposed))


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    # Capitalise a sentence whose first word was removed.
    text = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text.strip())
    return text


def _apply(text: str, patterns: list[str], replace_to: dict[str, str] | None = None) -> tuple[str, list[str]]:
    removed: list[str] = []
    out = text
    for pat in patterns:
        found = re.findall(pat, out, flags=re.IGNORECASE)
        if found:
            removed.extend(f.strip(" ,") for f in found)
            replacement = (replace_to or {}).get(pat, "")
            out = re.sub(pat, replacement, out, flags=re.IGNORECASE)
    return _tidy(out), removed


def _dedupe_sentences(text: str) -> tuple[str, int]:
    seen: set[str] = set()
    kept: list[str] = []
    dropped = 0
    for sentence in _SENTENCE.split(text.strip()):
        key = re.sub(r"\W+", " ", sentence.lower()).strip()
        if key and key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(sentence)
    return " ".join(kept), dropped


def _describe(removed: list[str]) -> str:
    unique = list(dict.fromkeys(r.lower() for r in removed if r))
    return "Removed " + ", ".join(f"“{r}”" for r in unique[:6]) + (" and more" if len(unique) > 6 else "")


def shorten(sections: dict[str, str]) -> list[StoryProposal]:
    proposals = []
    for field, text in sections.items():
        if not text.strip():
            continue
        out, removed = _apply(text, FILLER, {r"\bin order to\b": "to"})
        out, dropped = _dedupe_sentences(out)
        changes = [_describe(removed)] if removed else []
        if dropped:
            changes.append(f"Removed {dropped} repeated sentence{'s' if dropped != 1 else ''}")
        if changes and out != text.strip() and _only_removes(text, out):
            changes.append(f"{len(words(text))} → {len(words(out))} words")
            proposals.append(StoryProposal(field=field, original=text, proposed=out, changes=changes))
    return proposals


def clarity(sections: dict[str, str]) -> tuple[list[StoryProposal], list[str]]:
    proposals: list[StoryProposal] = []
    questions: list[str] = []
    for field, text in sections.items():
        if not text.strip():
            continue
        out, removed = _apply(text, HEDGES)
        if removed and out != text.strip() and _only_removes(text, out):
            proposals.append(
                StoryProposal(
                    field=field,
                    original=text,
                    proposed=out,
                    changes=[_describe(removed) + ": say what you did plainly"],
                )
            )
        for sentence in _SENTENCE.split(text.strip()):
            n = len(words(sentence))
            if n > 35:
                start = " ".join(words(sentence)[:6])
                questions.append(
                    f"{field.capitalize()}: the sentence starting “{start}…” is {n} words long. Could it be two?"
                )
        lowered = text.lower()
        for phrase in VAGUE:
            if phrase in lowered:
                questions.append(
                    f"{field.capitalize()}: “{phrase}” can hide what you did. What exactly did you do?"
                )
    return proposals, questions


def check(sections: dict[str, str]) -> list[str]:
    """Questions about missing or unclear STAR elements. Never a judgment of the learner."""
    questions = []
    for field in REQUIRED_SECTIONS:
        if len(words(sections.get(field, ""))) < 4:
            questions.append(PROMPTS[field])
    action = sections.get("action", "")
    if (
        words(action)
        and not re.search(r"\b(I|I'm|I've|I'd|me|my)\b", action)
        and re.search(r"\b(we|our|us|the team)\b", action, re.I)
    ):
        questions.append(
            "Action: this describes what the team did. Which parts did you do yourself? (Team work is fine; just be clear about your part.)"
        )
    for field in ("situation", "task", "action", "result"):
        n = len(words(sections.get(field, "")))
        if n > 150:
            questions.append(
                f"{field.capitalize()} is {n} words. In an interview, this part usually takes a few sentences."
            )
    if not words(sections.get("reflection", "")):
        questions.append("Optional: what did you learn, or what would you do differently next time?")
    return questions


def is_complete(sections: dict[str, str]) -> list[str]:
    """The required sections that are still empty."""
    return [f for f in REQUIRED_SECTIONS if not sections.get(f, "").strip()]
