"""Offline feedback on a written interview answer.

This is the free, no-API-key coach. It is honest about what it is: it checks whether an answer
covers what interviewers listen for (the question's rubric), how it's structured, and whether it's
a sensible length. It does not judge whether the content is *true* or *wise*; with an Anthropic key
the Claude provider adds that kind of judgment. The UI says which coach produced the feedback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.careers.questions import NUMBER, Question, irregular_actions

MIN_WORDS, GOOD_MIN, GOOD_MAX, MAX_WORDS = 40, 120, 350, 600
# Bump when the scoring rules change, so scores from different rule sets are never compared as equals.
# v2 (2026-11-03): sentences addressed to the grader are left out of grading, and a long sentence
# is quoted around the words that matched (docs/AI_EVALUATION.md, "Rubric v2").
# v3 (2026-11-04): content, not delivery: the rubric reads the answer with apostrophes and filler
# sounds taken out, numbers said as words count as numbers, filler sounds aren't counted as words,
# and an action is any first-person past-tense verb that isn't thinking, feeling or trying. Quotes
# are exact spans of the answer (docs/AI_EVALUATION.md, "Rubric v3").
# v4 (2026-11-04): a point is shown only by statements: a list of terms, a fragment, or the
# question's own guidance repeated back names a point without showing it (docs/AI_EVALUATION.md,
# "Rubric v4").
RUBRIC_VERSION = "v4"


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
    shows: bool = True  # a statement in the learner's own words, not a list, fragment or copied guidance


# --- statements, lists and copied guidance (rubric v4) -------------------------------------------
# A point is shown by something the answer says, not by naming it. Two kinds of text name without
# saying: a list of terms or a fragment ("Strengths: communication, teamwork, empathy." "Patient
# care."), and the question's own guidance repeated back (its prompt, rubric points, advice, outline
# or tips). Both still count as words; neither earns a point or is quoted as evidence.
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)
_BULLET = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+")
_SUBJECT = re.compile(r"\b(?:i|we|he|she|they|you)\b\s+[a-z]", re.IGNORECASE)
_AUXILIARY = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|have|has|had|do|does|did|will|would|can|could|should|shall|may|"
    r"might|must|im|ive|id|youre|theyre|isnt|wasnt|dont|didnt|doesnt|cant|wont|couldnt|wouldnt|shouldnt|"
    r"hadnt|havent|hasnt|arent|werent)\b",
    re.IGNORECASE,
)
_PAST = re.compile(rf"\b(?:[a-z]{{3,}}ed|{irregular_actions()})\b", re.IGNORECASE)


def _is_list(text: str) -> bool:
    """Three or more comma-separated items averaging three words or fewer: terms, not a sentence.
    A list in brackets inside a sentence ("Find quick wins (training, tips, cheat sheets).") doesn't
    make the sentence a list."""
    text = re.sub(r"\([^)]*\)", " ", text)
    items = [i for i in text.split(",") if i.strip()]
    if len(items) < 3 or _SUBJECT.match(text.strip()):
        return False
    return sum(len(_WORD.findall(i)) for i in items) / len(items) <= 3


def _is_statement(text: str) -> bool:
    words = _WORD.findall(text)
    if not words or _is_list(text):
        return False
    if len(words) <= 3:  # a fragment, unless it says who did what ("I escalated." "Pressure improved.")
        return bool(_SUBJECT.search(text) or _AUXILIARY.search(text) or _PAST.search(text))
    return True


_CONTRACTIONS = {
    "doesnt": "does not",
    "dont": "do not",
    "didnt": "did not",
    "isnt": "is not",
    "wasnt": "was not",
    "arent": "are not",
    "werent": "were not",
    "cant": "can not",
    "cannot": "can not",
    "wont": "will not",
    "wouldnt": "would not",
    "couldnt": "could not",
    "shouldnt": "should not",
    "havent": "have not",
    "hasnt": "has not",
    "youd": "you would",
    "youll": "you will",
    "youre": "you are",
    "theyre": "they are",
}
_GLUE = frozenset({"and", "the", "a", "an"})


def _tokens(text: str) -> list[str]:
    """Words for comparing with the question's guidance: contractions spelled out and the little
    words a copy most often changes ("and", "the") left out."""
    out: list[str] = []
    for w in _WORD.findall(_APOSTROPHE.sub("", text).lower()):
        out += [x for x in _CONTRACTIONS.get(w, w).split() if x not in _GLUE]
    return out


def _reference(question: Question) -> set[tuple[str, ...]]:
    """The word triples of the question's own guidance."""
    text = " ".join(
        [
            question.prompt,
            *(r.label for r in question.rubric),
            *(r.advice for r in question.rubric),
            *question.outline,
            *question.tips,
        ]
    )
    words = _tokens(text)
    return {tuple(words[i : i + 3]) for i in range(len(words) - 2)}


def _is_copied(text: str, reference: set[tuple[str, ...]]) -> bool:
    """Mostly the question's own guidance: most of its word triples come from the prompt, rubric,
    advice, outline or tips. Shared single words don't count: a concise answer naturally uses the
    rubric's everyday words ("let them try, then check their notes")."""
    words = _tokens(text)
    triples = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
    return bool(triples) and sum(t in reference for t in triples) / len(triples) >= 0.6


def _shows(text: str, reference: set[tuple[str, ...]] | None) -> bool:
    """Does this sentence (or bullet) say something in the learner's own words? A heading and what
    follows it are judged apart ("Steps: first, then, finally." "Uses the specifics of the job: care
    planning."): the unit shows something if either part is a statement that isn't copied guidance."""
    if reference is None:
        return True
    body = _BULLET.sub("", text)
    parts = body.split(":", 1) if ":" in body else [body]
    return any(_is_statement(part) and not _is_copied(part, reference) for part in parts)


def _split(
    answer: str, reference: set[tuple[str, ...]] | None = None
) -> tuple[str, list[_Sentence], list[str], str]:
    """(the text the rubric reads, its sentences, the sentences addressed to the grader, and the
    text with lists, fragments and copied guidance blanked as well). Only those are cut out of the
    answer; the rest is read whole, so sentence boundaries never matter."""
    kept: list[_Sentence] = []
    dropped: list[str] = []
    pieces: list[str] = []
    shown: list[str] = []
    last = last_shown = 0
    for m in _SENTENCE.finditer(answer):
        norm = _normalize(m.group(0), m.start())
        if not norm.text:
            continue
        if _to_grader(norm.text):
            dropped.append(re.sub(r"\s+", " ", m.group(0)).strip())
            pieces += [answer[last : m.start()], " "]
            last = m.end()
            shown += [answer[last_shown : m.start()], " "]
            last_shown = m.end()
            continue
        raw = m.group(0)
        start = m.start() + (len(raw) - len(raw.lstrip()))
        end = m.end() - (len(raw) - len(raw.rstrip()))
        first = next((ch for ch in norm.text if ch.isalpha()), "")
        said = " ".join(_WORD.findall(norm.text.lower()))
        if said and any(" ".join(_WORD.findall(k.norm.text.lower())) == said for k in kept):
            shows = False  # the same sentence again ("I checked. I checked.") shows nothing new
        elif kept and first.islower() and len(_WORD.findall(norm.text)) <= 3:
            # "my 2 a.m. assessment" is split after "a.m.": a short piece that carries on in lower
            # case belongs to the sentence before it, and is judged with it.
            shows = kept[-1].shows
        else:
            shows = _shows(norm.text, reference)
        kept.append(_Sentence(start, end, norm, shows))
        if not shows:
            shown += [answer[last_shown : m.start()], " "]
            last_shown = m.end()
    pieces.append(answer[last:])
    shown.append(answer[last_shown:])
    return _normalize("".join(pieces)).text, kept, dropped, _normalize("".join(shown)).text


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
    """Where the point was found: the first statement in which one of its patterns matches."""
    for sentence in sentences:
        if not sentence.shows:
            continue
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
    graded, sentences, to_grader, shown = _split(answer, _reference(question))
    text, shown_text = " " + graded + " ", " " + shown + " "
    words = len(graded.split())  # filler sounds aren't words of the answer
    fillers = len(_FILLER.findall(answer))
    found = []
    named_only = []  # points the answer names (in a list, a fragment or copied guidance) but doesn't show
    for rp in question.rubric:
        covered = _covered(shown_text, rp.patterns, rp.min_hits)
        if not covered and _covered(text, rp.patterns, rp.min_hits):
            named_only.append(rp.label)
        quote = _excerpt(answer, sentences, rp.patterns) if covered else None
        found.append(
            PointResult(
                rp.label, covered, rp.advice, quote[0] if quote else None, quote[1] if quote else None
            )
        )
    points = tuple(found)
    coverage = sum(p.covered for p in points) / len(points) if points else 0.0

    notes: list[str] = []
    if named_only:
        example = next((answer[x.start : x.end] for x in sentences if not x.shows), "")
        example = example if len(example) <= 60 else example[:59].rstrip() + "…"
        notes.append(
            f"Some of your answer names {'a point' if len(named_only) == 1 else 'points'} without showing "
            f"{'it' if len(named_only) == 1 else 'them'} (“{example}”). A list of terms, or the question's guidance "
            "said back, doesn't show what you did: tell it as an example, with what happened, what you did and how "
            "it turned out."
        )
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
