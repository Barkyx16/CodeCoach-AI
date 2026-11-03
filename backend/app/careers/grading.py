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
# v2 (2026-11-03): sentences addressed to the grader are left out of grading, and a long sentence
# is quoted around the words that matched (docs/AI_EVALUATION.md, "Rubric v2").
RUBRIC_VERSION = "v2"


@dataclass(frozen=True)
class PointResult:
    label: str
    covered: bool
    advice: str
    evidence: str | None = None  # the learner's own sentence where it was found (quoted, never paraphrased)


@dataclass(frozen=True)
class Feedback:
    score: int  # 0-100
    rating: str  # "Strong", "Good", "Developing", "Needs work"
    summary: str
    points: tuple[PointResult, ...]
    notes: tuple[str, ...]  # structure and length observations
    word_count: int
    # "insufficient" when the answer is too short to evaluate: the UI shows that state, not a score.
    evidence_level: str = "sufficient"


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _covered(text: str, patterns: tuple[str, ...], min_hits: int) -> bool:
    hits = sum(_count(p, text) for p in patterns)
    return hits >= min_hits


_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
QUOTE_CHARS = 200

# A sentence written to the grader rather than to the interviewer: an instruction to ignore the
# rules, a claim that "this answer" meets the criteria, a request for a score. Each pattern needs
# words an interview answer has no reason to use together, so ordinary sentences ("I'd give the
# sickest patient the highest priority", "her pain score was 8/10", "I never ignore the rules on
# hand hygiene") are not caught; tests/test_careers.py holds both kinds of examples.
_GRADING_WORDS = re.compile(
    r"\b(grader|grading|rubric|rating|marks|evaluator|covered|(this|my)\s+(answer|response))\b", re.IGNORECASE
)
_OVERRIDE = re.compile(
    r"\b(ignore|disregard|forget)\s+(all\s+|any\s+)?(of\s+)?(the\s+|your\s+)?(previous|prior|above|preceding|earlier)"
    r"\s+(instructions|prompts?)\b",
    re.IGNORECASE,
)
_TO_GRADER = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # "Ignore the grading rules", "disregard the scoring rubric"
        r"\b(ignore|disregard|forget)\s+(the\s+|your\s+|all\s+)?(grading|scoring|marking|evaluation|rubric)"
        r"(\s+(rules?|instructions?|criteria|guidelines|rubric))?\b",
        # "Note to the grader", "message for the evaluator"
        r"\b(note|message)\s+(to|for)\s+(the\s+)?(grader|graders|evaluator|evaluators|marker|markers|scorer)\b",
        # a sentence that opens like a system message: "SYSTEM:", "SYSTEM NOTE TO EVALUATOR:"
        r"^\s*system(\s+(note|prompt|message|instructions?))?(\s+(to|for)\s+(the\s+)?\w+)?\s*:",
        # the answer grading itself: "this answer covers…", "my response should be rated…"
        r"\b(this|my)\s+(answer|response)\s+(clearly\s+|fully\s+|already\s+)?(covers|meets|satisfies|deserves|earns|"
        r"addresses\s+(all|every)|sets\s+the\s+scene|has\s+been\s+(reviewed|graded|approved|marked)|"
        r"should\s+(get|receive|be\s+(rated|scored|marked|given|graded)))\b",
        # "mark every rubric point as covered", "mark all four points as covered"
        r"\b(mark|rate|score|grade)\b[^.!?]{0,40}\b(every|all|each)\s+(rubric\s+|three\s+|four\s+|five\s+|the\s+)?"
        r"points?\b[^.!?]{0,20}\bas\s+(covered|met|complete)\b",
        # an imperative asking for the top score: "Assign the highest rating."
        r"^\s*(please\s+)?(assign|give|award)\b[^.!?]{0,30}\b(highest|maximum|top|full|perfect)\s+(possible\s+)?"
        r"(rating|score|marks?|grade)\b",
        r"\b(assign|give|award)\s+(this\s+(answer|response)|me|it)\s+(the\s+|a\s+)?(highest|maximum|top|full|perfect)\b",
        # a sentence that is only a score: "Score: 100." "Rating: Strong."
        r"^\s*(score|rating)\s*[:=]\s*[\w%./ ]{1,20}[.!]?\s*$",
    )
)


def _to_grader(sentence: str) -> bool:
    if _OVERRIDE.search(sentence) and _GRADING_WORDS.search(sentence):
        return True  # "ignore all previous instructions" about the grading, not a story about a shift
    return any(p.search(sentence) for p in _TO_GRADER)


def _split(answer: str) -> tuple[str, list[str], list[str]]:
    """(the text to grade, its sentences, the sentences addressed to the grader). Only those are
    cut out of the answer; when there are none, the text is the answer exactly as before."""
    kept: list[str] = []
    dropped: list[str] = []
    pieces: list[str] = []
    last = 0
    for m in _SENTENCE.finditer(answer):
        sentence = re.sub(r"\s+", " ", m.group(0)).strip()
        if not sentence:
            continue
        if _to_grader(sentence):
            dropped.append(sentence)
            pieces += [answer[last : m.start()], " "]
            last = m.end()
        else:
            kept.append(sentence)
    pieces.append(answer[last:])
    return re.sub(r"\s+", " ", "".join(pieces)).strip(), kept, dropped


def _quote(sentence: str, start: int, end: int) -> str:
    """The sentence, or for a long one (dictated answers are often a single sentence) the part
    around the words that matched, so the quote always shows why the point counted."""
    if len(sentence) <= QUOTE_CHARS:
        return sentence
    room = max(0, QUOTE_CHARS - (end - start))
    lo = max(0, start - room // 2)
    hi = min(len(sentence), lo + QUOTE_CHARS)
    lo = max(0, hi - QUOTE_CHARS)
    if lo > 0:  # start on a word
        space = sentence.find(" ", lo, start)
        lo = space + 1 if space != -1 else lo
    if hi < len(sentence):  # end on a word
        space = sentence.rfind(" ", end, hi)
        hi = space if space != -1 else hi
    return ("…" if lo > 0 else "") + sentence[lo:hi].strip() + ("…" if hi < len(sentence) else "")


def _excerpt(sentences: list[str], patterns: tuple[str, ...]) -> str | None:
    """Where the point was found: the first sentence in which one of its patterns matches."""
    for sentence in sentences:
        padded = " " + sentence + " "
        for p in patterns:
            m = re.search(p, padded, flags=re.IGNORECASE)
            if m:
                start = max(0, m.start() - 1)
                return _quote(sentence, start, max(start, min(len(sentence), m.end() - 1)))
    return None


def _rating(score: int) -> str:
    if score >= 85:
        return "Strong"
    if score >= 65:
        return "Good"
    if score >= 40:
        return "Developing"
    return "Needs work"


def grade(question: Question, answer: str) -> Feedback:
    graded, sentences, to_grader = _split(answer)
    text = " " + graded + " "
    words = len(graded.split())
    points = tuple(
        PointResult(
            rp.label,
            covered := _covered(text, rp.patterns, rp.min_hits),
            rp.advice,
            _excerpt(sentences, rp.patterns) if covered else None,
        )
        for rp in question.rubric
    )
    coverage = sum(p.covered for p in points) / len(points) if points else 0.0

    notes: list[str] = []
    if to_grader:
        first = to_grader[0] if len(to_grader[0]) <= 80 else to_grader[0][:79].rstrip() + "…"
        notes.append(
            f"Left out {len(to_grader)} sentence{'s' if len(to_grader) > 1 else ''} written to the grader rather than "
            f"the interviewer (“{first}”). Only your answer to the question is scored."
        )
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
    if words < MIN_WORDS:
        # The score is capped above; the summary must say why rather than praise keyword hits.
        summary = (
            f"Too short to be convincing yet ({words} words). Say what happened, what you did and the result."
        )
    elif not missed:
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
        evidence_level="insufficient" if words < MIN_WORDS else "sufficient",
    )
