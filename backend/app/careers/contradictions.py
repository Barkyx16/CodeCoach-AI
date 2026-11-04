"""Explicit contradictions in a written answer (rubric v5).

Deliberately narrow. Two kinds are recognised, both stated in the answer's own words:

- did and did not: the learner says they did an action and, elsewhere in their own voice, that
  they did not do that same action ("I asked the healthcare assistant to take over the
  observations" ... "I did not ask anyone for help at all"). Same verb, same tense or mode (did /
  would / do), and either a sweeping negation ("anyone", "at all", "never") or a shared word in
  what the two statements are about.
- retraction: "Actually", "To be honest", "In fact", "Or really" before a statement that takes
  back something said before: the same verb negated, "never ... like that / that placement"
  about the statement just before it, or "skip the reports" about an earlier statement that
  mentions the reports.

Punctuation is ignored, so a dictated answer with no full stops or commas is read like the typed
one (the rule since rubric v3). The answer is cut into units at "and", "but", "so", "because",
"then" ..., before "I" and before "Actually"; a statement's account is its unit with the units
around it that have no "I" of their own ("For example, last month" | "I assessed a man ...").

Everything else is left alone, on purpose: quoted speech, hypotheticals ("if", "would have"),
statements about what someone else did, negated thoughts or feelings ("I wasn't worried"),
changes over time ("at first I didn't ..., but when ... I did"), two separate occasions
("on another shift"), and conflicts that need the meaning of words ("I never interrupt" ...
"I cut across them", two different first steps, "count the plans" ... "not track any figures").
docs/AI_EVALUATION.md ("Rubric v5") lists what isn't recognised.

Each finding has a status:
- "conflict": neither statement counts as evidence. A point either of them shows is what the
  contradiction is about: nothing in the two accounts counts for it until the learner says which is
  right. Other points are graded as before. Both statements are quoted with a neutral question;
- "unclear": one of the statements is hedged ("I think", "I'm not sure"): both are quoted and the
  learner is asked, but nothing is taken off;
- "corrected": the learner corrected a slip ("sorry, I mean", "or rather"): the corrected words
  don't count and the correction does. No note: they already fixed it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.careers.questions import irregular_actions

if TYPE_CHECKING:  # pragma: no cover
    from app.careers.grading import _Sentence


@dataclass(frozen=True)
class Conflict:
    kind: str  # "did_and_did_not" or "retraction"
    status: str  # "conflict", "unclear" or "corrected" (see the module docstring)
    # The two statements, as spans of the answer: answer[first[0]:first[1]] is the earlier one.
    first: tuple[int, int]
    second: tuple[int, int]
    # Spans of the answer that stop counting as evidence: both statements for a conflict, the
    # corrected words for a self-correction, nothing when unclear.
    void: tuple[tuple[int, int], ...]
    # For a conflict: what each statement says with its lead-in ("For example, last month I
    # assessed ...", "Actually, I never ..."). A point shown there is what the contradiction is about.
    about: tuple[tuple[int, int], ...] = ()
    # ... and each statement's whole account (with what carries on from it): such a point gets no
    # credit from anything in it. Other points are graded as before.
    scope: tuple[tuple[int, int], ...] = ()


# --- reading statements ------------------------------------------------------------------------

_ADV = (
    r"(?:(?:also|then|just|really|actually|personally|first|finally|still|even|only|always|usually|"
    r"often|later|eventually|instead|ever|already|straight away|[a-z]+ly)\s+){0,2}"
)
_PAST_FORM = rf"(?:[a-z]{{2,}}ed|{irregular_actions()})"
_NEGATION = (
    r"did not|didnt|do not|dont|would not|wouldnt|will not|wont|have not|havent|had not|hadnt|"
    r"would never|will never|have never|had never|never"
)
_NEG = re.compile(rf"\b(?P<subj>i|id|ive|ill)\s+{_ADV}(?P<neg>{_NEGATION})\s+{_ADV}(?P<v>[a-z]+)")
_AFF_PAST = re.compile(rf"\b(?:i|ive)\s+{_ADV}(?:have\s+)?(?P<v>{_PAST_FORM})\b")
_AFF_PLAN = re.compile(rf"\b(?:i would|i will|id|ill)\s+{_ADV}(?P<v>[a-z]+)\b")
_AFF_HABIT = re.compile(rf"\bi\s+{_ADV}(?P<v>[a-z]+)\b")
_JOINED = re.compile(r"^(?:and|then|or)\s+(?:then\s+)?(?P<v>[a-z]{3,})\b")
_GERUND = re.compile(r"\bby\s+(?P<v>[a-z]{3,}ing)\b")
_NOT_ONLY = re.compile(r"\b(?:not|nt|never)\s+(?:only|just)\b")
_NOT_VERBS = frozenset(
    [
        "am",
        "was",
        "were",
        "be",
        "been",
        "being",
        "is",
        "are",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "dont",
        "didnt",
        "not",
        "never",
        "can",
        "could",
        "should",
        "would",
        "will",
        "must",
        "may",
        "might",
        "shall",
        "also",
        "really",
        "just",
    ]
)

# Not actions: being, having, thinking, feeling, wanting, trying ("I wasn't worried", "I didn't
# think", "I didn't need to"), and verbs whose negation says it was done ("I didn't hesitate").
_STATES = frozenset(
    [
        "be",
        "have",
        "think",
        "know",
        "feel",
        "want",
        "need",
        "wish",
        "hope",
        "worry",
        "mind",
        "care",
        "like",
        "love",
        "hate",
        "believe",
        "expect",
        "mean",
        "seem",
        "remember",
        "forget",
        "see",
        "hear",
        "understand",
        "try",
        "plan",
        "intend",
        "guess",
        "suppose",
        "wonder",
        "realise",
        "realize",
        "learn",
        "notice",
        "prefer",
        "enjoy",
        "get",
        "let",
        "do",
        "make",
        "hesitate",
        "fail",
        "stop",
        "wait",
        "matter",
        "happen",
        "panic",
    ]
)

_IRREGULAR = {
    "went": "go",
    "gone": "go",
    "told": "tell",
    "gave": "give",
    "given": "give",
    "took": "take",
    "taken": "take",
    "made": "make",
    "brought": "bring",
    "sent": "send",
    "wrote": "write",
    "written": "write",
    "spoke": "speak",
    "spoken": "speak",
    "met": "meet",
    "ran": "run",
    "rang": "ring",
    "rung": "ring",
    "sat": "sit",
    "stood": "stand",
    "put": "put",
    "set": "set",
    "led": "lead",
    "kept": "keep",
    "found": "find",
    "held": "hold",
    "drove": "drive",
    "driven": "drive",
    "taught": "teach",
    "began": "begin",
    "begun": "begin",
    "paid": "pay",
    "left": "leave",
    "said": "say",
    "sought": "seek",
    "caught": "catch",
    "fed": "feed",
    "built": "build",
    "spent": "spend",
    "chose": "choose",
    "chosen": "choose",
    "broke": "break",
    "broken": "break",
    "split": "split",
    "cut": "cut",
    "shut": "shut",
    "did": "do",
    "done": "do",
    "saw": "see",
    "seen": "see",
    "got": "get",
    "heard": "hear",
    "felt": "feel",
    "knew": "know",
    "known": "know",
    "thought": "think",
    "read": "read",
    "let": "let",
    "been": "be",
    "was": "be",
    "were": "be",
    "had": "have",
    "lost": "lose",
    "understood": "understand",
    "forgot": "forget",
    "forgotten": "forget",
}


def _lemmas(word: str) -> frozenset[str]:
    """Possible base forms of a verb ("asked", "asking" -> "ask"; "stopped" -> "stop")."""
    w = word.lower()
    if w in _IRREGULAR:
        return frozenset({_IRREGULAR[w]})
    out = {w}
    if w.endswith("ied"):
        out.add(w[:-3] + "y")
    if w.endswith("ed"):
        out |= {w[:-2], w[:-1]}
        if len(w) > 4 and w[-3] == w[-4]:
            out.add(w[:-3])
    if w.endswith("ing") and len(w) > 5:
        out |= {w[:-3], w[:-3] + "e"}
        if w[-4] == w[-5]:
            out.add(w[:-4])
    return frozenset(x for x in out if len(x) >= 3)


def _is_past(word: str) -> bool:
    return re.fullmatch(_PAST_FORM, word) is not None


# --- context -------------------------------------------------------------------------------------

_HYPOTHETICAL = re.compile(
    r"\b(?:if|unless|suppose|supposing|imagine|imagining|whether|otherwise|in case|what if|had i|were i)\b"
    r"|\b(?:would|could|should|might|must)(?:nt| not)? have\b"
)
# A change of circumstances or a different occasion: the two statements can both be true.
# Ordinary sequence words ("before", "after", "first", "then") are not on the list: they order the
# steps of one event rather than separate two.
_TIME_OR_OCCASION = re.compile(
    r"(?:^|[,;]\s*|\b(?:but|and|then|until|only)\s+)when\b"  # "but when she deteriorated", not "tell them when"
    r"|\b(?:at first|initially|to begin with|later|afterwards|after that|eventually|until|till|by the time|"
    r"whenever|again|anymore|any more|no longer|yet|this time|that time|next time|"
    r"(?:the next|the following) (?:day|shift|morning|night|week|month|time)|the first time|the second time|another|a different|the other day|earlier|ago|"
    r"previously|last time|on one (?:shift|day|night|occasion))\b"
)
_HEDGE = re.compile(
    r"\b(?:i think|i believe|i guess|maybe|perhaps|probably|not sure|cant remember|cannot remember|"
    r"dont remember|do not remember|dont recall|do not recall|if i remember|might)\b"
)
_REPORTED = re.compile(
    r"\b(?:said|say|says|told|tell|tells|explained|replied|answered|wrote|admitted|insisted)\s+"
    r"(?:(?:me|her|him|them|us|everyone|the \w+|my \w+|his \w+|their \w+)\s+)?(?:that\s+)?$"
)
_SWEEPING = re.compile(r"\b(?:anyone|anybody|anything|nobody|nothing|no one|at all)\b(?!\s+(?:else|except))")
_CORRECTION = re.compile(
    r"\b(?:sorry|i mean|i meant|or rather|correction|let me rephrase|scratch that|no wait)\b"
)
_MARKER = r"(?:actually|to be honest|honestly|in fact|in truth|truthfully|to tell the truth|the truth is)"
# Before the statement it opens: "Actually, I never ...", "To be honest, though, I wouldn't ...",
# "Or really I would only ...".
_RETRACTION = re.compile(rf"\b{_MARKER}\b|\bor really\b")
_UNDO = re.compile(
    r"\b(?:i|id|i would|ill|i will)\s+(?:just\s+)?(?:skip|skipped|drop|dropped|ignore|ignored|leave out|left out)"
    r"\s+(?:the\s+)?(?P<noun>[a-z]{3,})"
)
# "never been in a situation like that", "I never did that", "that never happened"
_ANAPHOR = re.compile(
    r"\blike (?:that|this)\b|\b(?:did|do|done) (?:that|this|it)\b|\b(?:that|this|it) (?:never )?happened\b"
)
_DEMONSTRATIVE = re.compile(r"\b(?:that|this|those|these)\s+(?P<noun>[a-z]{3,})\b")
_STOPWORDS = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "onto",
        "over",
        "then",
        "they",
        "them",
        "their",
        "there",
        "what",
        "when",
        "were",
        "was",
        "have",
        "had",
        "has",
        "her",
        "his",
        "him",
        "she",
        "you",
        "your",
        "our",
        "out",
        "about",
        "after",
        "before",
        "because",
        "could",
        "would",
        "should",
        "will",
        "just",
        "also",
        "very",
        "only",
        "some",
        "any",
        "all",
        "one",
        "two",
        "who",
        "how",
        "why",
        "where",
        "which",
        "while",
        "than",
        "too",
        "not",
        "never",
        "really",
        "first",
        "finally",
        "next",
    ]
)
# Words that start a clause without being a verb: "and the doctor", "and his wife".
_NOT_JOINED = frozenset(
    [
        "the",
        "a",
        "an",
        "his",
        "her",
        "my",
        "their",
        "our",
        "your",
        "its",
        "this",
        "that",
        "these",
        "those",
        "it",
        "he",
        "she",
        "they",
        "we",
        "you",
        "i",
        "so",
        "because",
        "which",
        "who",
        "when",
        "where",
        "what",
        "why",
        "how",
        "if",
        "as",
        "at",
        "in",
        "on",
        "for",
        "with",
        "to",
        "from",
        "by",
        "of",
        "not",
        "all",
        "some",
        "any",
        "no",
        "every",
        "each",
        "both",
        "either",
        "neither",
        "one",
        "two",
        "three",
        "there",
        "here",
        "then",
        "also",
        "only",
        "just",
        "even",
        "still",
    ]
)
# Quoted speech in the answer itself: "...", “...”, ‘...’ and '...' (an apostrophe inside a word,
# as in "didn't", doesn't open or close a quote).
_QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|‘[^‘]*?’(?!\w)|(?<!\w)'(?=\w)(?:[^']|'(?=\w))*'(?!\w)")
_SUBJECT = re.compile(r"\b(?:i|id|ive|ill)\b")
_CONJUNCTION = re.compile(r"\b(?:and|but|so|because|although|though|while|whereas|or|yet|then)\b")
_MARKER_START = re.compile(rf"\b{_MARKER}\b(?=\s+(?:though\s+)?(?:i|id|ive|ill|that|this|it)\b)")
_EXAMPLE_START = re.compile(r"\bfor (?:example|instance)\b")
# "I think I asked", "I mean I didn't", "she told me that I", "if I had": the second "I" stays in
# the unit.
_SAYING = frozenset(
    [
        "think",
        "thought",
        "believe",
        "guess",
        "mean",
        "meant",
        "suppose",
        "remember",
        "know",
        "knew",
        "said",
        "says",
        "say",
        "told",
        "tell",
        "tells",
        "explained",
        "sure",
    ]
)
_KEEP_BEFORE_I = _SAYING | frozenset(
    [
        "if",
        "when",
        "unless",
        "whether",
        "and",
        "but",
        "so",
        "because",
        "although",
        "though",
        "while",
        "whereas",
        "or",
        "yet",
        "then",
    ]
)
_SAID_TO = frozenset(["that", "me", "her", "him", "them", "us", "everyone"])
_PUNCT = str.maketrans({ch: " " for ch in '.,;:!?()[]"“”‘’—–-…/'})


@dataclass(frozen=True)
class _Unit:
    start: int  # span in the working text
    end: int
    subject: bool  # has an "I" of its own


@dataclass(frozen=True)
class _Statement:
    unit: int
    lemmas: frozenset[str]
    negated: bool
    mode: str  # "past", "plan" (would / will) or "habit" (present)
    at: int  # where the statement starts (its "I"), in the working text
    end: int  # where its verb ends


class _Reading:
    """The answer as the contradiction rule reads it: the sentences the rubric reads, lower case,
    with punctuation as spaces, cut into units; positions map back to the answer."""

    def __init__(self, answer: str, sentences: Sequence[_Sentence]) -> None:
        chars: list[str] = []
        index: list[int] = []
        for s in sentences:
            if not s.shows:
                continue  # lists, fragments and copied guidance say nothing either way
            if chars:
                chars.append(" ")
                index.append(index[-1])
            chars += s.norm.text.lower()
            index += s.norm.index
        self.answer = answer
        self.text = "".join(chars).translate(_PUNCT)
        self.index = index
        self.units = self._cut()

    def _cut(self) -> list[_Unit]:
        text = self.text
        cuts = {0}
        cuts |= {m.start() for m in _CONJUNCTION.finditer(text)}
        cuts |= {m.start() for m in _MARKER_START.finditer(text)}
        cuts |= {m.start() for m in _EXAMPLE_START.finditer(text)}
        for m in _SUBJECT.finditer(text):
            before = text[max(0, m.start() - 40) : m.start()].split()
            keep = bool(before) and (
                before[-1] in _KEEP_BEFORE_I
                or (before[-1] in _SAID_TO and len(before) > 1 and before[-2] in _SAYING | _SAID_TO)
            )
            if not keep:
                cuts.add(m.start())
        bounds = sorted(cuts) + [len(text)]
        units = []
        for lo, hi in zip(bounds, bounds[1:], strict=False):
            while lo < hi and text[lo] == " ":
                lo += 1
            while hi > lo and text[hi - 1] == " ":
                hi -= 1
            if hi > lo:
                units.append(_Unit(lo, hi, bool(_SUBJECT.search(text, lo, hi))))
        return units

    def unit_text(self, k: int) -> str:
        return self.text[self.units[k].start : self.units[k].end]

    def joined(self, k: int) -> bool:
        """Does unit k carry on from the one before ("and he was grateful", "because ...")?"""
        return bool(_CONJUNCTION.match(self.text, self.units[k].start))

    def account(self, k: int) -> tuple[int, int]:
        """Unit k with its lead-in ("For example, last month", "Actually", "At first") and what
        carries on from it ("and the doctor ...", "because ..."), up to the next "I"."""
        lo = hi = k
        while lo > 0 and not self.units[lo - 1].subject and not self.joined(lo - 1):
            lo -= 1
        while hi + 1 < len(self.units) and not self.units[hi + 1].subject and self.joined(hi + 1):
            hi += 1
        return lo, hi

    def span(self, lo: int, hi: int) -> tuple[int, int]:
        """A span of the working text as a span of the answer."""
        return self.index[lo], self.index[max(lo, hi - 1)] + 1

    def units_span(self, first: int, last: int) -> tuple[int, int]:
        return self.span(self.units[first].start, self.units[last].end)

    def quote_span(self, first: int, last: int) -> tuple[int, int]:
        """The units as quoted to the learner: without a leading "and" or "though", trailing
        punctuation, or anything after the sentence they start in ends."""
        text = self.text
        lo, hi = self.units[first].start, self.units[last].end
        lead = _LEADING.match(text, lo)
        if lead and lead.end() < hi:
            lo = lead.end()
        a, b = self.span(lo, hi)
        stop = re.search(r"[.!?;](?=\s|$)", self.answer[a:b])
        if stop and a + stop.start() > a:
            b = a + stop.start()
        while b > a and (self.answer[b - 1].isspace() or self.answer[b - 1] in ",;:—–("):
            b -= 1
        return a, b


_LEADING = re.compile(r"(?:(?:and|but|so|or|yet|then|though|although|because|while)\s+)+")


def _neg_mode(subj: str, neg: str, verb: str) -> str:
    if neg in ("would not", "wouldnt", "will not", "wont", "would never", "will never"):
        return "plan"
    if neg in ("do not", "dont"):
        return "habit"
    if neg == "never":
        if subj == "ive":
            return "past"
        if subj in ("id", "ill"):
            return "past" if _is_past(verb) else "plan"
        return "past" if _is_past(verb) else "habit"
    return "past"


def _statements(r: _Reading) -> list[_Statement]:
    """First-person statements of an action, unit by unit."""
    out: list[_Statement] = []
    mode_before: str | None = None  # the mode of the last affirmed "I" statement
    for k, u in enumerate(r.units):
        clause, lo = r.unit_text(k), u.start
        taken: set[int] = set()
        found: list[_Statement] = []
        for m in _NEG.finditer(clause):
            taken.add(m.start())
            if _NOT_ONLY.search(clause, m.start("neg")):
                continue
            mode = _neg_mode(m["subj"], m["neg"], m["v"])
            found.append(_Statement(k, _lemmas(m["v"]), True, mode, lo + m.start(), lo + m.end()))
        for pattern, mode in ((_AFF_PAST, "past"), (_AFF_PLAN, "plan"), (_AFF_HABIT, "habit")):
            for m in pattern.finditer(clause):
                if m.start() in taken or m["v"] in _NOT_VERBS:
                    continue
                if mode == "habit" and _is_past(m["v"]):
                    continue
                taken.add(m.start())
                here = "past" if mode == "plan" and _is_past(m["v"]) else mode  # "I'd asked": had asked
                found.append(_Statement(k, _lemmas(m["v"]), False, here, lo + m.start(), lo + m.end()))
        if not u.subject and mode_before:
            jm = _JOINED.match(clause)
            # "I checked the pump and asked the clerk", "I would sit down and listen": the same "I".
            if jm and jm["v"] not in _NOT_JOINED and jm["v"] not in _NOT_VERBS and not jm["v"].endswith("ly"):
                joined = "past" if _is_past(jm["v"]) else mode_before
                if joined == mode_before:
                    found.append(
                        _Statement(k, _lemmas(jm["v"]), False, joined, lo + jm.start("v"), lo + jm.end("v"))
                    )
        for st in [x for x in found if not x.negated][:1]:
            for m in _GERUND.finditer(clause):  # "I would gather information by asking the team"
                found.append(_Statement(k, _lemmas(m["v"]), False, st.mode, lo + m.start(), lo + m.end()))
        affirmed = [x for x in found if not x.negated]
        if affirmed:
            mode_before = affirmed[-1].mode
        elif u.subject:
            mode_before = None
        out += found
    return out


def _object(r: _Reading, st: _Statement) -> str | None:
    """What the statement is about: the first content word after its verb ("asked the surgeon for
    the date" -> "surgeon")."""
    for w in re.findall(r"[a-z]{3,}", r.text[st.end : r.units[st.unit].end]):
        if w not in _STOPWORDS and w not in _NOT_JOINED:
            return w.rstrip("s")
    return None


def _words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", text) if w not in _STOPWORDS}


def find(answer: str, sentences: Sequence[_Sentence]) -> tuple[Conflict, ...]:
    """The explicit contradictions in an answer, given the sentences the rubric reads (text
    addressed to the grader is already gone). Lists, fragments and copied guidance are skipped."""
    r = _Reading(answer, sentences)
    if not r.units:
        return ()
    quoted = [m.span() for m in _QUOTED.finditer(answer)]

    def account_text(k: int) -> str:
        lo, hi = r.account(k)
        return r.text[r.units[lo].start : r.units[hi].end]

    def changed(k: int) -> bool:  # "at first", "but when ...", "on another shift": both can be true
        lo, hi = r.account(k)
        # Without punctuation, "On another shift" can end the unit before: look at that one too.
        return any(_TIME_OR_OCCASION.search(r.unit_text(j)) for j in range(max(0, lo - 1), hi + 1))

    def around(k: int) -> str:  # the account and the unit before it, for "that placement", "the reports"
        lo, hi = r.account(k)
        return r.text[r.units[max(0, lo - 1)].start : r.units[hi].end]

    def hedged(k: int) -> bool:
        nxt = r.unit_text(k + 1) if k + 1 < len(r.units) else ""
        return bool(_HEDGE.search(account_text(k)) or _HEDGE.search(nxt))

    def lead(st: _Statement) -> str:
        return r.text[r.units[r.account(st.unit)[0]].start : st.at]

    def opened(k: int) -> int:  # the unit with the "Actually" that opens statement k, else k
        start = k
        while start > r.account(k)[0] and not _RETRACTION.search(r.unit_text(start)):
            start -= 1
        return start if _RETRACTION.search(r.unit_text(start)) else k

    stmts: list[_Statement] = []
    for st in _statements(r):
        if any(a <= r.index[st.at] < b for a, b in quoted):
            continue  # someone else's words
        if _HYPOTHETICAL.search(account_text(st.unit)):
            continue  # if ..., would have ...
        if _REPORTED.search(r.text[max(0, st.at - 40) : st.at]):
            continue  # "I told her I didn't ...": what was said, not what was done
        stmts.append(st)

    found: list[Conflict] = []
    seen: set[tuple[int, int]] = set()

    def add(kind: str, status: str, a: int, b: int, quote_b: tuple[int, int], void: list) -> None:
        if (a, b) in seen or a == b:
            return
        seen.add((a, b))
        conflict = status == "conflict"
        found.append(
            Conflict(
                kind,
                status,
                r.quote_span(a, a),
                quote_b,
                tuple(void) if status != "unclear" else (),
                tuple(r.units_span(r.account(k)[0], k) for k in (a, b)) if conflict else (),
                tuple(r.units_span(*r.account(k)) for k in (a, b)) if conflict else (),
            )
        )

    # did and did not (a retraction too when "Actually" and the like come before the later one)
    for j, later in enumerate(stmts):
        for earlier in stmts[:j]:
            if earlier.negated == later.negated or earlier.mode != later.mode or earlier.unit == later.unit:
                continue
            common = earlier.lemmas & later.lemmas
            if not common or common & _STATES:
                continue
            a, b = earlier.unit, later.unit
            between = any(r.units[k].subject for k in range(a + 1, b))
            just_before = r.answer[max(0, r.index[later.at] - 30) : r.index[later.at]].lower()
            if not between and _CORRECTION.search(just_before.replace("'", "").replace("’", "")):
                add("did_and_did_not", "corrected", a, b, r.quote_span(b, b), [r.units_span(a, a)])
                continue  # "I called him, sorry, I mean I didn't call him": the correction stands
            neg, aff = (earlier, later) if earlier.negated else (later, earlier)
            about = _object(r, neg)
            if not (_SWEEPING.search(r.unit_text(neg.unit)) or (about and about == _object(r, aff))):
                continue  # "I called the registrar" and "I didn't call the doctor": different things
            if changed(a) or changed(b):
                continue
            kind = "retraction" if _RETRACTION.search(lead(later)) else "did_and_did_not"
            status = "unclear" if hedged(a) or hedged(b) else "conflict"
            add(kind, status, a, b, r.quote_span(opened(b), b), [r.units_span(a, a), r.units_span(b, b)])

    # retractions without the same verb: "Actually I never ... that placement", "I'd skip the reports"
    affirmed_units = sorted({x.unit for x in stmts if not x.negated})
    for k in range(len(r.units)):
        text = r.unit_text(k)
        denial, undo = _NEG.search(text), _UNDO.search(text)
        taken_back = next((x for x in stmts if x.unit == k and (x.negated or undo)), None)
        if (
            taken_back is None
            or not (denial or undo)
            or not _RETRACTION.search(lead(taken_back))
            or changed(k)
        ):
            continue
        if any(c.second[0] <= r.index[taken_back.at] < c.second[1] for c in found):
            continue  # already found through the same verb
        target: int | None = None
        if denial:
            prev = [u for u in affirmed_units if u < k]
            demo = _DEMONSTRATIVE.search(text, denial.end("neg"))
            if prev and (
                _ANAPHOR.search(text, denial.end("neg"))
                or (demo and demo["noun"].rstrip("s") in _words(around(prev[-1])))
            ):
                target = prev[-1]
        elif undo:
            noun = undo["noun"].rstrip("s")
            target = next((u for u in reversed(affirmed_units) if u < k and noun in _words(around(u))), None)
        if target is None:
            continue
        status = "unclear" if hedged(target) or hedged(k) else "conflict"
        quote = r.quote_span(opened(k), k)  # with its "Actually"
        add("retraction", status, target, k, quote, [r.units_span(target, target), r.units_span(k, k)])
    return tuple(sorted(found, key=lambda c: (c.first, c.second)))
