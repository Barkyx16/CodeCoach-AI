"""Deterministic mock interviewer and rubric scorer (no API key needed).

It looks for concrete signals in what the candidate says and writes (clarifying questions,
named data structures, stated Big-O, mentioned edge cases) and follows a realistic interview
arc. It is transparent by design: every follow-up and every rubric score is traceable to a rule
below, and evaluations are labelled confidence "low" because keyword signals are a rough proxy.
"""

from __future__ import annotations

import re

from app.models import InterviewPhase
from app.schemas.interview import (
    RUBRIC_DIMENSIONS,
    InterviewerReply,
    InterviewEvaluation,
    RubricScore,
)
from app.services.ai.base import InterviewContext, ProviderResult

INTERVIEWER_MODEL = "rule-based-interviewer"

# A phase auto-advances after this many candidate turns, so a session can never get stuck.
MAX_TURNS_PER_PHASE = 3

_CLARIFY_SIGNALS = re.compile(
    r"\?|\b(empty|null|negative|duplicate|duplicates|constraint|range|size|sorted|assume|overflow|"
    r"unicode|case|bounds|limit|zero|only one|exactly one|large)\b",
    re.I,
)
_APPROACH_SIGNALS = re.compile(
    r"\b(hash ?map|hashmap|hash ?set|hashset|map|set|dictionary|two pointers?|pointer|stack|queue|"
    r"binary search|sort|sorting|iterate|loop|pass|dynamic programming|dp|memo|sliding window|window|"
    r"recurs\w*|kadane|prefix|greedy|counter|count|array)\b",
    re.I,
)
_BRUTE_FORCE = re.compile(
    r"\b(brute|nested loop|every pair|all pairs|double loop|o\(n\^?2\)|n squared)\b", re.I
)
_BIG_O = re.compile(r"O\(\s*([^)]+?)\s*\)", re.I)
_TEST_SIGNALS = re.compile(
    r"\b(test|edge|example|empty|single|one element|negative|duplicate|large|null|zero|trace|walk through)\b",
    re.I,
)


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def normalize_big_o(expr: str) -> str:
    """'O( N ^ 2 )' -> 'n^2', 'O(n log n)' -> 'nlogn', 'O(1)' -> '1'."""
    e = expr.lower().replace(" ", "").replace("²", "^2").replace("**", "^")
    e = e.replace("n*n", "n^2").replace("log(n)", "logn").replace("n*logn", "nlogn")
    return e


def stated_complexities(text: str) -> list[str]:
    return [normalize_big_o(m.group(1)) for m in _BIG_O.finditer(text)]


def _candidate_text(ctx: InterviewContext, phase: InterviewPhase | None = None) -> str:
    return "\n".join(
        t.content for t in ctx.transcript if t.role == "candidate" and (phase is None or t.phase == phase)
    )


def _last_candidate(ctx: InterviewContext) -> str:
    for t in reversed(ctx.transcript):
        if t.role == "candidate":
            return t.content
    return ""


class OfflineInterviewer:
    """Mixed into OfflineCoach; kept separate for readability and testing."""

    name = "offline"

    # --- turns ------------------------------------------------------------------------

    def interview_turn(self, ctx: InterviewContext) -> ProviderResult[InterviewerReply]:
        reply = self._opening(ctx) if ctx.is_opening else self._follow_up(ctx)
        return ProviderResult(content=reply, provider=self.name, model=INTERVIEWER_MODEL)

    def _opening(self, ctx: InterviewContext) -> InterviewerReply:
        minutes = max(1, round(ctx.seconds_remaining / 60))
        return InterviewerReply(
            message=(
                f'Hi, thanks for joining. Today we\'ll work on "{ctx.problem.title}" and we have about '
                f"{minutes} minutes. Take a moment to read the problem. Before writing any code, tell me how "
                "you understand it and ask any clarifying questions about the inputs or edge cases."
            ),
            advance_phase=False,
        )

    def _follow_up(self, ctx: InterviewContext) -> InterviewerReply:
        last = _last_candidate(ctx)
        forced = ctx.candidate_turns_in_phase >= MAX_TURNS_PER_PHASE
        handler = {
            InterviewPhase.CLARIFY: self._clarify,
            InterviewPhase.APPROACH: self._approach,
            InterviewPhase.CODING: self._coding,
            InterviewPhase.COMPLEXITY: self._complexity,
            InterviewPhase.WRAP_UP: self._wrap_up,
        }[ctx.phase]
        reply = handler(ctx, last)
        if forced and not reply.advance_phase:
            return InterviewerReply(
                message="Let's keep moving so we have time for everything. "
                + self._phase_intro(ctx.phase.next),
                advance_phase=True,
            )
        return reply

    @staticmethod
    def _phase_intro(phase: InterviewPhase | None) -> str:
        return {
            InterviewPhase.APPROACH: "How would you approach this? Talk me through the idea before coding.",
            InterviewPhase.CODING: "Go ahead and code it up in the editor. Narrate as you go, and send me a message when you have a version.",
            InterviewPhase.COMPLEXITY: "What's the time and space complexity of your solution, and why?",
            InterviewPhase.WRAP_UP: "Let's test it. Walk me through how your code handles a couple of edge cases.",
            None: "That's a good place to stop. Click Finish to get your feedback.",
        }[phase]

    def _clarify(self, ctx: InterviewContext, last: str) -> InterviewerReply:
        if _CLARIFY_SIGNALS.search(last):
            constraint = ctx.problem.constraints[0] if ctx.problem.constraints else "the stated constraints"
            return InterviewerReply(
                message=f"Good questions. You can rely on the constraints, e.g. {constraint}. "
                + self._phase_intro(InterviewPhase.APPROACH),
                advance_phase=True,
            )
        return InterviewerReply(
            message="Before you start: is there anything about the input you'd want to confirm? "
            "For example, can it be empty, contain duplicates, or be very large?",
            advance_phase=False,
        )

    def _approach(self, ctx: InterviewContext, last: str) -> InterviewerReply:
        expected = ctx.problem.expected_time or "a better complexity"
        if _BRUTE_FORCE.search(last) and expected not in ("O(n^2)",):
            return InterviewerReply(
                message=f"That would work. Can you do better? What is the brute force repeating that you could remember instead? We're aiming for {expected}.",
                advance_phase=False,
            )
        if _APPROACH_SIGNALS.search(last) and len(last) >= 40:
            return InterviewerReply(
                message="That sounds reasonable. " + self._phase_intro(InterviewPhase.CODING),
                advance_phase=True,
            )
        return InterviewerReply(
            message="Can you be more concrete? Which data structure would you use, and what would one pass through the input look like?",
            advance_phase=False,
        )

    def _coding(self, ctx: InterviewContext, last: str) -> InterviewerReply:
        a = ctx.analysis
        if not ctx.code.strip() or a.is_unchanged_starter:
            return InterviewerReply(
                message="I don't see code in the editor yet. Write a first version, even a rough one, then tell me when it's ready.",
                advance_phase=False,
            )
        edge = next((f for f in a.findings if f.category == "edge-case"), None)
        if edge and ctx.candidate_turns_in_phase < 2:
            return InterviewerReply(
                message=f"Looking at your code: what happens with the smallest possible input? ({edge.detail})",
                advance_phase=False,
            )
        return InterviewerReply(
            message="Thanks for walking me through it. " + self._phase_intro(InterviewPhase.COMPLEXITY),
            advance_phase=True,
        )

    def _complexity(self, ctx: InterviewContext, last: str) -> InterviewerReply:
        stated = stated_complexities(last)
        if not stated:
            return InterviewerReply(
                message="Can you state it in Big-O terms, for both time and space?", advance_phase=False
            )
        expected = normalize_big_o((ctx.problem.expected_time or "").strip("O()"))
        actual = normalize_big_o(ctx.analysis.estimated_time.strip("O()"))
        if expected and stated[0] != expected and stated[0] != actual:
            return InterviewerReply(
                message=f"Let's double-check that. How many times does your code touch each element? (You said O({stated[0]}).)",
                advance_phase=False,
            )
        return InterviewerReply(
            message="Right. " + self._phase_intro(InterviewPhase.WRAP_UP), advance_phase=True
        )

    def _wrap_up(self, ctx: InterviewContext, last: str) -> InterviewerReply:
        if _TEST_SIGNALS.search(last):
            return InterviewerReply(
                message="Nice, that's a thorough walkthrough. We're at time, thanks! Click Finish to see your feedback.",
                advance_phase=True,
            )
        return InterviewerReply(
            message="Which specific inputs would you test? Think about the smallest input and an unusual one.",
            advance_phase=False,
        )

    # --- evaluation ---------------------------------------------------------------------

    def evaluate_interview(self, ctx: InterviewContext) -> ProviderResult[InterviewEvaluation]:
        a = ctx.analysis
        said = _candidate_text(ctx)
        candidate_turns = [t for t in ctx.transcript if t.role == "candidate"]
        words = [len(t.content.split()) for t in candidate_turns]
        avg_words = sum(words) / len(words) if words else 0.0
        reached = {t.phase for t in ctx.transcript}

        scores: dict[str, RubricScore] = {}

        # Problem solving: concrete approach + reaching code + not a brute force when better exists.
        approach_text = _candidate_text(ctx, InterviewPhase.APPROACH)
        ps = 1 + int(bool(_APPROACH_SIGNALS.search(approach_text))) + int(InterviewPhase.CODING in reached)
        has_code = bool(ctx.code.strip()) and not a.is_unchanged_starter
        expected_time = ctx.problem.expected_time
        if has_code and expected_time and a.estimated_time == expected_time:
            ps += 1
        scores["problem_solving"] = RubricScore(
            dimension="problem_solving",
            score=min(4, ps),
            evidence=(
                f"Final code is about {a.estimated_time} (target {expected_time})."
                if has_code
                else "No working code was written during the session."
            ),
        )

        # Communication: how much reasoning was said out loud, plus clarifying questions.
        comm = 1 if avg_words < 8 else 2 if avg_words < 20 else 3 if avg_words < 45 else 4
        asked = "?" in _candidate_text(ctx, InterviewPhase.CLARIFY)
        if asked and comm < 4:
            comm += 1
        scores["communication"] = RubricScore(
            dimension="communication",
            score=comm,
            evidence=f"About {round(avg_words)} words per answer across {len(candidate_turns)} answer{'' if len(candidate_turns) == 1 else 's'}"
            + ("; asked clarifying questions." if asked else "; no clarifying questions asked."),
        )

        # Code quality: static analysis of the final code.
        if not has_code:
            cq, ev = 1, "No code beyond the starter template."
        else:
            sev = {f.severity for f in a.findings}
            cq = 1 if "high" in sev else 2 if "medium" in sev else 3 if "low" in sev else 4
            top = next(
                iter(sorted(a.findings, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f.severity])), None
            )
            ev = top.detail if top else "No issues found by the static checks."
        scores["code_quality"] = RubricScore(dimension="code_quality", score=cq, evidence=ev)

        # Complexity analysis: did they state it, and was it right?
        stated = stated_complexities(said)
        expected = normalize_big_o((expected_time or "").strip("O()"))
        actual = normalize_big_o(a.estimated_time.strip("O()"))
        if not stated:
            ca, ev = 1, "Time/space complexity was never stated in Big-O terms."
        elif expected in stated or actual in stated:
            ca, ev = (
                (4 if len(stated) >= 2 else 3),
                f"Stated {', '.join('O(' + s + ')' for s in stated[:2])}, consistent with the solution.",
            )
        else:
            ca, ev = 2, f"Stated O({stated[0]}), which doesn't match the code (about {a.estimated_time})."
        scores["complexity_analysis"] = RubricScore(dimension="complexity_analysis", score=ca, evidence=ev)

        # Testing: edge cases and examples mentioned.
        mentions = len(_TEST_SIGNALS.findall(said))
        te = 1 if mentions == 0 else 2 if mentions < 3 else 3 if mentions < 6 else 4
        scores["testing"] = RubricScore(
            dimension="testing",
            score=te,
            evidence=f"Mentioned tests or edge cases {_times(mentions)}."
            if mentions
            else "Didn't mention any tests or edge cases.",
        )

        ordered = [scores[d] for d in RUBRIC_DIMENSIONS]
        avg = sum(s.score for s in ordered) / len(ordered)
        overall = (
            "strong" if avg >= 3.5 else "solid" if avg >= 2.75 else "developing" if avg >= 2 else "needs_work"
        )
        best = max(ordered, key=lambda s: s.score)
        worst = min(ordered, key=lambda s: s.score)
        label = {d: d.replace("_", " ") for d in RUBRIC_DIMENSIONS}
        ending = {
            "time_expired": " Time ran out before the interview was finished.",
            "abandoned": " The interview was ended early.",
        }.get(ctx.end_reason or "", "")
        return ProviderResult(
            content=InterviewEvaluation(
                scores=ordered,
                overall=overall,
                summary=f"Strongest area: {label[best.dimension]}. Biggest opportunity: {label[worst.dimension]}.{ending}",
                strengths=[s.evidence for s in ordered if s.score >= 3]
                or ["You completed a full practice session."],
                improvements=[_IMPROVE[s.dimension] for s in ordered if s.score <= 2]
                or ["Try a harder problem or a shorter time limit."],
                confidence="low",
            ),
            provider=self.name,
            model=INTERVIEWER_MODEL,
        )


_IMPROVE = {
    "problem_solving": "Name a concrete data structure and the single pass you'd make before coding.",
    "communication": "Think out loud: explain why, not just what, and ask clarifying questions first.",
    "code_quality": "Handle edge cases explicitly and use descriptive names before calling the code done.",
    "complexity_analysis": "Always state time and space complexity in Big-O and justify each one.",
    "testing": "Walk through the smallest input, a typical one and an unusual one before saying you're done.",
}
