"""Offline feedback on a written interview answer.

This is the free, no-API-key coach. It is honest about what it is: it checks whether an answer
covers what interviewers listen for (the question's rubric), how it's structured, and whether it's
a sensible length. It does not judge whether the content is *true* or *wise*; with an Anthropic key
the Claude provider adds that kind of judgment. The UI says which coach produced the feedback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.careers.questions import NUMBER, Question

MIN_WORDS, GOOD_MIN, GOOD_MAX, MAX_WORDS = 40, 120, 350, 600
# Bump when the scoring rules change, so scores from different rule sets are never compared as equals.
# v2 (2026-11-03): sentences addressed to the grader are left out of grading, and a long sentence
# is quoted around the words that matched (docs/AI_EVALUATION.md, "Rubric v2").
# v3 (2026-11-04): content, not delivery: the rubric reads the answer with apostrophes and filler
# sounds taken out, numbers said as words count as numbers, filler sounds aren't counted as words,
# and an action is any first-person past-tense verb that isn't thinking, feeling or trying. Quotes
# are exact spans of the answer (docs/AI_EVALUATION.md, "Rubric v3").
RUBRIC_VERSION = "v3"


@dataclass(frozen=True)
class PointResult:
    label: str
    covered: bool
    advice: str
    evidence: str | None = None  # the learner's own sentence where it was found (quoted, never paraphrased)
    # Where the quote's text is in the answer: answer[span[0]:span[1]] is the quote without its ellipses.
    span: tuple[int, int] | None = None


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


# Filler sounds a speech-to-text transcript keeps. Ambiguous words ("like", "so", "er", which can be
# the ER) are left alone.
_FILLER = re.compile(r"\b(?:u+m+|u+h+m*|e+r+m+|h+m+|m{2,})\b,?", re.IGNORECASE)
_APOSTROPHE = re.compile(r"['’]")


@dataclass(frozen=True)
class _Text:
    """What the rubric reads (apostrophes and filler sounds out, whitespace collapsed) and, for each
    of its characters, where it is in the answer, so quotes are taken from the answer itself."""

    text: str
    index: tuple[int, ...]


def _normalize(original: str, offset: int = 0) -> _Text:
    drop = [False] * len(original)
    for pattern in (_FILLER, _APOSTROPHE):
        for m in pattern.finditer(original):
            drop[m.start() : m.end()] = [True] * (m.end() - m.start())
    chars: list[str] = []
    index: list[int] = []
    space = True  # collapse runs of whitespace; no leading space
    for i, ch in enumerate(original):
        if drop[i]:
            continue
        if ch.isspace():
            if space:
                continue
            chars.append(" ")
            space = True
        else:
            chars.append(ch)
            space = False
        index.append(offset + i)
    if chars and chars[-1] == " ":
        chars.pop()
        index.pop()
    return _Text("".join(chars), tuple(index))


@dataclass(frozen=True)
class _Sentence:
    start: int  # span in the answer, surrounding whitespace excluded
    end: int
    norm: _Text


def _split(answer: str) -> tuple[str, list[_Sentence], list[str]]:
    """(the text the rubric reads, its sentences, the sentences addressed to the grader). Only those
    are cut out of the answer; the rest is read whole, so sentence boundaries never matter."""
    kept: list[_Sentence] = []
    dropped: list[str] = []
    pieces: list[str] = []
    last = 0
    for m in _SENTENCE.finditer(answer):
        norm = _normalize(m.group(0), m.start())
        if not norm.text:
            continue
        if _to_grader(norm.text):
            dropped.append(re.sub(r"\s+", " ", m.group(0)).strip())
            pieces += [answer[last : m.start()], " "]
            last = m.end()
        else:
            raw = m.group(0)
            start = m.start() + (len(raw) - len(raw.lstrip()))
            end = m.end() - (len(raw) - len(raw.rstrip()))
            kept.append(_Sentence(start, end, norm))
    pieces.append(answer[last:])
    return _normalize("".join(pieces)).text, kept, dropped


def _quote(answer: str, sentence: _Sentence, start: int, end: int) -> tuple[str, tuple[int, int]]:
    """The sentence, or for a long one (dictated answers are often a single sentence) the part
    around the words that matched, so the quote always shows why the point counted. Positions are in
    the answer; the quote is the answer's own text between them."""
    lo, hi = sentence.start, sentence.end
    if hi - lo > QUOTE_CHARS:
        room = max(0, QUOTE_CHARS - (end - start))
        lo = max(sentence.start, start - room // 2)
        hi = min(sentence.end, lo + QUOTE_CHARS)
        lo = max(sentence.start, hi - QUOTE_CHARS)
        if lo > sentence.start:  # start on a word
            space = answer.find(" ", lo, start)
            lo = space + 1 if space != -1 else lo
        if hi < sentence.end:  # end on a word
            space = answer.rfind(" ", end, hi)
            hi = space if space != -1 else hi
    body = answer[lo:hi]
    lo += len(body) - len(body.lstrip())
    hi -= len(body) - len(body.rstrip())
    text = ("…" if lo > sentence.start else "") + answer[lo:hi] + ("…" if hi < sentence.end else "")
    return text, (lo, hi)


def _excerpt(
    answer: str, sentences: list[_Sentence], patterns: tuple[str, ...]
) -> tuple[str, tuple[int, int]] | None:
    """Where the point was found: the first sentence in which one of its patterns matches."""
    for sentence in sentences:
        padded = " " + sentence.norm.text + " "
        for p in patterns:
            m = re.search(p, padded, flags=re.IGNORECASE)
            if m:
                n = len(sentence.norm.text)
                a = min(max(0, m.start() - 1), n - 1)
                b = min(max(a + 1, m.end() - 1), n)
                return _quote(answer, sentence, sentence.norm.index[a], sentence.norm.index[b - 1] + 1)
    return None


def _not_counting(fillers: int) -> str:
    return " (not counting “um” and “uh”)" if fillers else ""


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
    words = len(graded.split())  # filler sounds aren't words of the answer
    fillers = len(_FILLER.findall(answer))
    found = []
    for rp in question.rubric:
        covered = _covered(text, rp.patterns, rp.min_hits)
        quote = _excerpt(answer, sentences, rp.patterns) if covered else None
        found.append(
            PointResult(
                rp.label, covered, rp.advice, quote[0] if quote else None, quote[1] if quote else None
            )
        )
    points = tuple(found)
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
            f"Only {words} words{_not_counting(fillers)}. Spoken answers usually run one to two minutes "
            f"(about {GOOD_MIN}-{GOOD_MAX} words)."
        )
    elif words < GOOD_MIN:
        length_score = 0.6
        notes.append(
            f"{words} words{_not_counting(fillers)}: a little short. Add a concrete detail or example "
            f"(aim for {GOOD_MIN}-{GOOD_MAX})."
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
        # "I'm", "I've", "I'd" and their dictated forms ("im", "ive", "id") all count as "I".
        i_count, we_count = _count(r"\bi(?:m|ve|d|ll)?\b", text), _count(r"\bwe(?:re|ve|d|ll)?\b", text)
        if we_count > i_count and we_count >= 3:
            notes.append("You say “we” more than “I”. Interviewers need to hear what you did.")
        if not re.search(NUMBER, text, flags=re.IGNORECASE):
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
