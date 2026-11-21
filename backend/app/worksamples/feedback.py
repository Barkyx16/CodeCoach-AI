"""Checking a work sample against its brief (docs/WORK_SAMPLES.md).

Fixed rules, not AI, and every note points at the learner's own text or at the brief:
- **Required fields** (deterministic): every section has text, and the length is within limits.
- **Required points**: each is covered when the text says it, in any wording the brief's matcher
  accepts (several phrasings per point); a covered point quotes the learner's sentence.
- **Details not in the brief**: every specific in the text (a time, an amount, a percentage, a
  date, a reference, a phone number, any number of two or more digits) is compared with the
  specifics in the supplied facts, after normalising (6pm and 18:00 are the same time, $84.20 and
  84.20 the same amount). One the facts don't contain is named: invented case details don't count
  as evidence, however confident they sound.
- **Claims the facts don't support** (authored per brief, such as "fixed" when it isn't): named
  with the sentence, unless negated nearby ("not fixed yet" is fine).
- **Audience**: words the brief marks as wrong for its reader; **clarity**: sentences over 35 words.

What it can't do: judge tone beyond those lists, or whether a sentence is true in a way the facts
don't settle. Different structures and styles pass when they cover the points with the facts.
"""

from __future__ import annotations

import re
from typing import Any

from app.worksamples import Brief

RULES_VERSION = 1
LONG_SENTENCE = 35
_NEGATIONS = {
    "not",
    "no",
    "never",
    "yet",
    "isn't",
    "hasn't",
    "haven't",
    "aren't",
    "wasn't",
    "won't",
    "don't",
    "doesn't",
    "cannot",
    "can't",
    "without",
}
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("phone", re.compile(r"\b\d{4}\s\d{3}\s\d{4}\b")),
    ("reference", re.compile(r"\b[A-Z]{2,}-\d{2,}\b")),
    ("time", re.compile(r"\b(\d{1,2}):(\d{2})\s?(am|pm)?\b|\b(\d{1,2})\s?(am|pm)\b", re.I)),
    (
        "date",
        re.compile(
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTHS})\b|\b({_MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b",
            re.I,
        ),
    ),
    ("percent", re.compile(r"\b(\d+(?:\.\d+)?)\s?%")),
    ("money", re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s?(k\b)?", re.I)),
    ("number", re.compile(r"\b(\d[\d,]*(?:\.\d+)?)(k\b)?", re.I)),
]
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[\w'’$%.-]+")


def words(text: str) -> int:
    return len([w for w in _WORD.findall(text) if any(c.isalnum() for c in w)])


def _number(raw: str, k: str | None = None) -> str:
    value = float(raw.replace(",", ""))
    if k:
        value *= 1000
    return f"{value:g}"


def specifics(text: str) -> list[tuple[str, str]]:
    """(normalised key, as written) for each specific detail in the text."""
    found: list[tuple[str, str]] = []
    spans: list[tuple[int, int]] = []

    def free(m: re.Match[str]) -> bool:
        return not any(m.start() < e and s < m.end() for s, e in spans)

    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if not free(m):
                continue
            key: str | None = None
            if kind == "phone":
                key = "phone:" + re.sub(r"\s", "", m.group(0))
            elif kind == "reference":
                key = "ref:" + m.group(0).upper()
            elif kind == "time":
                if m.group(1) is not None:
                    h, mins, ampm = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
                else:
                    h, mins, ampm = int(m.group(4)), 0, m.group(5).lower()
                if ampm == "pm" and h < 12:
                    h += 12
                if ampm == "am" and h == 12:
                    h = 0
                key = f"time:{h * 60 + mins}"
            elif kind == "date":
                day = m.group(1) or m.group(4)
                month = (m.group(2) or m.group(3)).lower()
                key = f"date:{int(day)} {month}"
            elif kind == "percent":
                key = "pct:" + _number(m.group(1))
            elif kind == "money":
                key = "num:" + _number(m.group(1), m.group(2))
            elif kind == "number":
                digits = re.sub(r"\D", "", m.group(1).split(".")[0])
                if len(digits) < 2 and not m.group(2):
                    continue  # single digits ("3 to 5 days", "1 of 2") aren't case details
                key = "num:" + _number(m.group(1), m.group(2))
            if key:
                spans.append((m.start(), m.end()))
                found.append((key, m.group(0).strip()))
    return found


def _sentences(sections: dict[str, str]) -> list[str]:
    out: list[str] = []
    for text in sections.values():
        out += [s.strip() for s in _SENTENCE.split(text) if s.strip()]
    return out


def _has(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def _negated(sentence: str, phrase: str) -> bool:
    lower = sentence.lower()
    at = lower.find(phrase.lower())
    before = re.findall(r"[\w']+", lower[:at])[-4:]
    return any(w in _NEGATIONS or w.endswith("n't") for w in before)


def evaluate(brief: Brief, sections: dict[str, str]) -> dict[str, Any]:
    text = "\n".join(sections.get(s, "") for s in brief.section_ids)
    sentences = _sentences({s: sections.get(s, "") for s in brief.section_ids})
    n = words(text)

    checks: list[dict[str, Any]] = []
    if brief.sections:
        empty = [s.label for s in brief.sections if words(sections.get(s.id, "")) == 0]
        checks.append(
            {
                "id": "sections",
                "ok": not empty,
                "text": f"All {len(brief.sections)} sections have text."
                if not empty
                else "Empty: " + ", ".join(empty) + ".",
            }
        )
    checks.append(
        {
            "id": "length",
            "ok": brief.min_words <= n <= brief.max_words,
            "text": f"{n} words (the brief asks for {brief.min_words} to {brief.max_words}).",
        }
    )

    points: list[dict[str, Any]] = []
    for point in brief.required:
        groups: list[list[str]] = point["match"]
        is_covered = all(any(_has(text, p) for p in group) for group in groups)
        quote = None
        if is_covered:
            quote = next(
                (s for s in sentences if all(any(_has(s, p) for p in group) for group in groups)),
                next((s for s in sentences if any(_has(s, p) for p in groups[0])), None),
            )
        points.append(
            {
                "id": point["id"],
                "label": point["label"],
                "covered": is_covered,
                "quote": quote,
                "guidance": point["guidance"],
            }
        )

    allowed = {key for fact in brief.facts for key, _ in specifics(fact["text"])}
    unsupported: list[dict[str, Any]] = []
    for sentence in sentences:
        for key, shown in specifics(sentence):
            if key not in allowed and shown not in [u["text"] for u in unsupported]:
                unsupported.append(
                    {
                        "text": shown,
                        "sentence": sentence,
                        "why": "This detail isn't in the brief. Use only the facts given; if something isn't known, say so.",
                    }
                )

    claims: list[dict[str, Any]] = []
    for rule in brief.claims_to_avoid:
        for sentence in sentences:
            hit = next((p for p in rule["phrases"] if _has(sentence, p) and not _negated(sentence, p)), None)
            if hit:
                claims.append({"phrase": hit, "sentence": sentence, "why": rule["why"]})
                break

    jargon: list[dict[str, Any]] = []
    for item in brief.avoid:
        term = item["term"]
        pattern = re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.I)
        found = next((s for s in sentences if pattern.search(s)), None)
        if found:
            jargon.append({"term": term, "sentence": found, "why": item["why"]})

    long_sentences: list[dict[str, Any]] = [
        {"sentence": s, "words": words(s)} for s in sentences if words(s) > LONG_SENTENCE
    ]

    covered: list[dict[str, Any]] = [p for p in points if p["covered"]]
    missing: list[dict[str, Any]] = [p for p in points if not p["covered"]]
    if claims:
        revision = f"Change “{claims[0]['phrase']}”: {claims[0]['why']}"
    elif unsupported:
        revision = f"Check “{unsupported[0]['text']}”: it isn't in the brief. Use only the facts given."
    elif missing:
        revision = f"Add {missing[0]['label'].lower()}: {missing[0]['guidance']}"
    elif not all(c["ok"] for c in checks):
        revision = (
            next(c["text"] for c in checks if not c["ok"]) + " Adjust the length or fill the empty section."
        )
    elif jargon:
        revision = f"Replace “{jargon[0]['term']}”: {jargon[0]['why']}"
    elif long_sentences:
        revision = "Split the longest sentence: shorter sentences are easier to act on."
    else:
        revision = "Nothing essential is missing. Try reading it as the audience would, and cut anything they don't need."
    return {
        "rules_version": RULES_VERSION,
        "checks": checks,
        "points": points,
        "covered": len(covered),
        "total": len(points),
        "unsupported": unsupported,
        "claims": claims,
        "jargon": jargon,
        "long_sentences": long_sentences,
        "revision": revision,
        "method": "Fixed checks against this brief, not AI: required parts, the points it asks for, details "
        "compared with the supplied facts, and words it marks for this audience. They can't judge tone "
        "beyond that; a different structure or style is fine when it covers the points with the facts.",
    }
