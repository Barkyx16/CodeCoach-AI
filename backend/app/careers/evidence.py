"""The evidence contract for written-answer feedback (Volume 4 prompt 06).

A point the coach credits may quote the learner's answer as its evidence. The quote is the
learner's own words, from the answer that was graded (never the rubric's text or the coach's), and
it is shown only when it checks out against that answer, every time feedback is sent:

- its span, stored as code-point offsets into the answer, holds the quoted text (allowing for the
  "…" that marks a cut and for runs of whitespace);
- it isn't text addressed to the grader;
- a cut never drops a negation just before the quote ("…called the doctor" from "I never called
  the doctor"): the quote is widened back over it, still in the learner's words; and a cut that
  would leave out only the first few words of the sentence (often who did it) isn't made.

A quote that doesn't check out is omitted, and the point says so; nothing is put in its place.
Older feedback stored no spans: a quote that is still the learner's words is shown as legacy
evidence with no position (none is invented), and the grade itself is never rerun or changed.

Spans go to the browser as UTF-16 code-unit offsets, which is what JavaScript strings index by: a
character outside the Basic Multilingual Plane (an emoji, some CJK) earlier in the answer would
otherwise shift every later span by one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.careers.grading import _to_grader

EvidenceStatus = Literal["verified", "legacy", "omitted"]

ELLIPSIS = "…"
# Before a cut quote: words that reverse or deny what follows.
_NEGATION = re.compile(
    r"\b(?:not|never|no|nobody|nothing|neither|nor|cannot|without|didn'?t|don'?t|doesn'?t|wasn'?t|weren'?t|"
    r"wouldn'?t|couldn'?t|won'?t|hadn'?t|haven'?t|isn'?t|aren'?t|can'?t)\b",
    re.IGNORECASE,
)
_LOOKBACK_WORDS = 4  # how far before a cut a negation is looked for
_SHORT_PREFIX_WORDS = 8  # a cut that would leave out no more than this from the sentence start isn't made
_SENTENCE_END = re.compile(r"[.!?\n]")


@dataclass(frozen=True)
class CheckedEvidence:
    quote: str | None
    span: tuple[int, int] | None  # UTF-16 code units of the answer, [start, end)
    status: EvidenceStatus | None  # None: the point has no quote (missing, or nothing to quote)


def utf16_offset(text: str, index: int) -> int:
    """The UTF-16 code-unit offset of code-point `index` in `text`."""
    return len(text[:index].encode("utf-16-le")) // 2


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentence_start(answer: str, index: int) -> int:
    ends = [m.end() for m in _SENTENCE_END.finditer(answer, 0, index)]
    start = ends[-1] if ends else 0
    while start < index and answer[start].isspace():
        start += 1
    return start


def _keep_context(answer: str, start: int, end: int) -> int:
    """Where a cut quote should start so it keeps what it needs: the start of its sentence when only a
    few words were cut, or a negation just before the cut."""
    begin = _sentence_start(answer, start)
    words = list(re.finditer(r"\S+", answer[begin:start]))
    if len(words) <= _SHORT_PREFIX_WORDS:
        return begin
    near = begin + words[-_LOOKBACK_WORDS].start()
    hit = _NEGATION.search(answer, near, start)
    return hit.start() if hit else start


def check(
    answer: str, covered: bool, quote: str | None, span: list[int] | tuple[int, int] | None
) -> CheckedEvidence:
    """The evidence of one feedback point, as it may be shown with `answer`."""
    if not covered or not quote:
        return CheckedEvidence(None, None, None)
    body = _squash(quote.strip(ELLIPSIS))
    if not body or _to_grader(body):
        return CheckedEvidence(None, None, "omitted")
    if span is None:
        # Older feedback: no position was stored. Shown only while it is still the learner's words.
        return (
            CheckedEvidence(quote, None, "legacy")
            if body in _squash(answer)
            else CheckedEvidence(None, None, "omitted")
        )
    start, end = int(span[0]), int(span[1])
    if not (0 <= start < end <= len(answer)) or _squash(answer[start:end]) != body:
        return CheckedEvidence(None, None, "omitted")
    if quote.startswith(ELLIPSIS):
        widened = _keep_context(answer, start, end)
        if widened < start:
            start = widened
            text = answer[start:end].strip()
            quote = (
                (ELLIPSIS if start > _sentence_start(answer, start) else "")
                + text
                + (ELLIPSIS if quote.endswith(ELLIPSIS) else "")
            )
    return CheckedEvidence(quote, (utf16_offset(answer, start), utf16_offset(answer, end)), "verified")
