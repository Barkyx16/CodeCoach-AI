"""Simulated interviewer engagement: how an interviewer would likely respond to an answer's content.

This is not a person's feelings and not a hiring prediction. It reads only the text of the answer
(never voice, accent, face, pace or whether the answer was typed or spoken) and maps explicit
evidence to one of four states:

    not_enough_evidence  too little text to react to
    more_detail          the answer misses something the question needs (says what)
    following            the answer covers the basics; names the next thing to add
    explore_further      specific, well covered: the interviewer would dig deeper with a follow-up

Every result carries a one-sentence reason that refers to the answer and the evidence behind it,
so the learner can see why, and every rule is a plain function below.
"""

from __future__ import annotations

import re

from app.careers.grading import Feedback
from app.careers.questions import Question
from app.models import InterviewPhase
from app.schemas.interview import Engagement, EngagementState
from app.services.ai.interviewer_offline import (
    _APPROACH_SIGNALS,
    _BRUTE_FORCE,
    _CLARIFY_SIGNALS,
    _TEST_SIGNALS,
    stated_complexities,
)

LABELS: dict[EngagementState, str] = {
    "not_enough_evidence": "Not enough evidence yet",
    "more_detail": "Looking for more detail",
    "following": "Following your answer",
    "explore_further": "Ready to explore further",
}
MIN_WORDS = 25  # below this there is too little to react to
MIN_CODING_WORDS = 4

_STOP = set(
    [
        "about",
        "after",
        "again",
        "also",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "been",
        "before",
        "being",
        "both",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "during",
        "each",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "like",
        "more",
        "most",
        "must",
        "not",
        "of",
        "on",
        "or",
        "other",
        "our",
        "out",
        "over",
        "own",
        "same",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "way",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "yours",
        "tell",
        "time",
        "describe",
        "explain",
        "walk",
        "me",
        "give",
        "example",
        "one",
    ]
)
_NUMBER = re.compile(r"[^.?!]{0,30}\b\d[\d,.%]*\b[^.?!]{0,20}")
_EXAMPLE = re.compile(
    r"\b(for example|for instance|one time|once,|last (?:year|month|week|winter|summer|spring|fall|autumn)|"
    r"at my (?:last|previous)|in my (?:last|previous|current) (?:job|role|position|placement)|when i was)\b",
    re.I,
)
_I = re.compile(r"\bi\b", re.I)
_WE = re.compile(r"\bwe\b", re.I)


def _result(state: EngagementState, reason: str, evidence: list[str]) -> Engagement:
    return Engagement(
        state=state, label=LABELS[state], reason=f"{LABELS[state]}: {reason}", evidence=evidence
    )


def _quote(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return f"“{text[:limit].rstrip()}{'…' if len(text) > limit else ''}”"


def _topic_terms(question: Question) -> list[str]:
    """Words that show an answer is about the question: its tags, else the title's content words."""
    terms = [t.lower() for t in question.tags if t]
    if not terms:
        terms = [w for w in re.findall(r"[a-z][a-z-]{3,}", question.title.lower()) if w not in _STOP]
    return terms


def _mentions(answer: str, term: str) -> bool:
    """Words match by their first 5 letters ("assess" ~ "assessment"). Short terms need every
    content word; longer scenario descriptions need at least half of them."""
    lowered = answer.lower()
    words = [w for w in re.findall(r"[a-z]+", term.lower()) if w not in _STOP and len(w) > 2]
    if not words:
        return False
    hits = sum(w[:5] in lowered for w in words)
    return hits >= (len(words) if len(words) <= 2 else -(-len(words) // 2))


def for_career_answer(question: Question, answer: str, fb: Feedback) -> Engagement:
    words = fb.word_count
    if words < MIN_WORDS:
        return _result(
            "not_enough_evidence",
            f"the answer has {words} words, which is too little to react to. Say what happened and what you did.",
            [f"{words} words"],
        )

    evidence: list[str] = []
    terms = _topic_terms(question)
    on_topic = [t for t in terms if _mentions(answer, t)]
    if terms and not on_topic:
        topic = terms[0]
        return _result(
            "more_detail",
            f"the answer doesn't mention {topic} yet, which is what the question asks about.",
            [f"No mention of: {', '.join(terms[:3])}"],
        )
    if on_topic:
        evidence.append(f"On topic: {', '.join(on_topic[:3])}")

    number = _NUMBER.search(answer)
    example = _EXAMPLE.search(answer)
    specific = number or example
    if specific:
        evidence.append(f"Specific detail: {_quote(specific.group(0).strip())}")

    covered = [p for p in fb.points if p.covered]
    missed = [p for p in fb.points if not p.covered]
    total = len(fb.points) or 1
    evidence += [f"Covered: {p.label}" for p in covered] + [f"Missing: {p.label}" for p in missed]
    coverage = len(covered) / total

    behavioral = question.kind == "behavioral"
    i_count, we_count = len(_I.findall(answer)), len(_WE.findall(answer))
    if behavioral and (i_count < 2 or we_count > i_count):
        evidence.append(f"“I” {i_count}×, “we” {we_count}×")
        return _result(
            "more_detail",
            "you described the situation, but not clearly what you personally did. Say “I” for your own actions.",
            evidence,
        )
    if coverage >= 0.75 and specific:
        return _result(
            "explore_further",
            f"you gave a specific detail ({_quote(specific.group(0).strip(), 40)}) and covered "
            f"{len(covered)} of {total} key points, so a deeper follow-up would come next.",
            evidence,
        )
    if coverage >= 0.5:
        nxt = missed[0].label.lower() if missed else "a concrete example with a number"
        return _result(
            "following", f"you covered {len(covered)} of {total} key points. Next, add: {nxt}.", evidence
        )
    advice = missed[0].advice if missed else "Add a concrete example."
    return _result(
        "more_detail",
        f"you covered {len(covered)} of {total} key points. {advice}",
        evidence,
    )


def for_coding_message(phase: InterviewPhase | None, message: str, expected_time: str | None) -> Engagement:
    """Engagement for one candidate message in a coding interview, judged against the phase's goal."""
    words = len(message.split())
    if words < MIN_CODING_WORDS:
        return _result(
            "not_enough_evidence",
            f"“{message.strip()[:40]}” is too short to react to. Explain your thinking in a sentence or two.",
            [f"{words} words"],
        )
    phase = phase or InterviewPhase.WRAP_UP
    if phase == InterviewPhase.CLARIFY:
        m = _CLARIFY_SIGNALS.search(message)
        if m:
            return _result(
                "following",
                f"you checked the inputs ({_quote(m.group(0), 30)}), which is what this stage is for.",
                [f"Clarifying signal: {_quote(m.group(0), 30)}"],
            )
        return _result(
            "more_detail",
            "no question about the input yet. Ask about empty input, duplicates or size.",
            ["No clarifying question or edge case mentioned"],
        )
    if phase == InterviewPhase.APPROACH:
        brute = _BRUTE_FORCE.search(message)
        named = _APPROACH_SIGNALS.search(message)
        if brute and expected_time and expected_time.replace(" ", "").lower() not in ("o(n^2)", "o(n²)"):
            return _result(
                "more_detail",
                f"you described a brute-force idea ({_quote(brute.group(0), 30)}). "
                f"Say what it repeats and how to avoid it; the target is {expected_time}.",
                [f"Brute force: {_quote(brute.group(0), 30)}"],
            )
        if named:
            return _result(
                "explore_further",
                f"you named a concrete approach ({_quote(named.group(0), 30)}), "
                "so the next question would test why it works.",
                [f"Approach: {_quote(named.group(0), 30)}"],
            )
        return _result(
            "more_detail",
            "the approach isn't concrete yet. Name the data structure and the steps.",
            ["No data structure or algorithm named"],
        )
    if phase == InterviewPhase.COMPLEXITY:
        stated = stated_complexities(message)
        if stated:
            return _result(
                "explore_further",
                f"you stated O({stated[0]}); explaining why it holds would come next.",
                [f"Stated: O({s})" for s in stated],
            )
        return _result(
            "more_detail",
            "no Big-O stated yet. Give the time and space complexity and why.",
            ["No Big-O found"],
        )
    if phase == InterviewPhase.WRAP_UP:
        m = _TEST_SIGNALS.search(message)
        if m:
            return _result(
                "following",
                f"you walked through a test ({_quote(m.group(0), 30)}).",
                [f"Testing signal: {_quote(m.group(0), 30)}"],
            )
        return _result(
            "more_detail",
            "no test case walked through yet. Trace an edge case such as empty input.",
            ["No test or edge case mentioned"],
        )
    # Coding phase: narration is what an interviewer listens for.
    named = _APPROACH_SIGNALS.search(message)
    if named:
        return _result(
            "following",
            f"you're narrating your code ({_quote(named.group(0), 30)}).",
            [f"Narration: {_quote(named.group(0), 30)}"],
        )
    return _result(
        "following",
        "you shared progress. Mention the key decision in the code you just wrote.",
        ["Progress update"],
    )
