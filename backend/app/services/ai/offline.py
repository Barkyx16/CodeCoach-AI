"""Offline coach: curated hint ladder + static analysis. Needs no API key, is fully
deterministic, and is what the test-suite and the public demo run on by default."""

from __future__ import annotations

from app.schemas.ai import CodeReview, Complexity, HintContent, ReviewIssue
from app.services.ai.base import HintContext, ProviderResult, ReviewContext
from app.services.ai.interviewer_offline import OfflineInterviewer

_FOCUS = {
    1: "getting unstuck",
    2: "choosing an approach",
    3: "structuring the algorithm",
    4: "understanding the full solution",
}


class OfflineCoach(OfflineInterviewer):
    name = "offline"
    model = "curated-hints+static-analysis"

    def hint(self, ctx: HintContext) -> ProviderResult[HintContent]:
        hints = ctx.problem.curated_hints
        text = hints[min(ctx.level, len(hints)) - 1]
        a = ctx.analysis
        if a.is_unchanged_starter or not ctx.code.strip():
            encouragement = "Start small: get the simplest correct version working first, then improve it."
        elif any(f.category == "edge-case" for f in a.findings):
            encouragement = "Your core logic is taking shape. Next, pressure-test it on the smallest inputs."
        else:
            encouragement = "You already have real code down. Use this to check your direction."
        return ProviderResult(
            content=HintContent(
                hint=text, focus_area=_FOCUS.get(ctx.level, "approach"), encouragement=encouragement
            ),
            provider=self.name,
            model=self.model,
        )

    def review(self, ctx: ReviewContext) -> ProviderResult[CodeReview]:
        a = ctx.analysis
        issues = [
            ReviewIssue(
                severity=f.severity,
                category=f.category,
                detail=f.detail,
                suggestion=f.suggestion,
                line_hint=f.line,
            )
            for f in sorted(a.findings, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f.severity])
        ]
        strengths: list[str] = []
        if not a.is_unchanged_starter:
            if ctx.problem.expected_time and a.estimated_time == ctx.problem.expected_time:
                strengths.append(
                    f"Loop structure is consistent with the target {ctx.problem.expected_time} time."
                )
            if not any(i.category == "edge-case" for i in issues):
                strengths.append("No unguarded first-element access was detected.")
            if not any(i.category in ("style", "readability") for i in issues):
                strengths.append("Code is free of the common style issues this reviewer checks for.")

        if a.is_unchanged_starter:
            summary = "This is still the starter code, so there is nothing to review yet."
            next_step = "Write a first attempt, even a brute-force one, then ask for a review."
        elif not issues:
            summary = (
                "No problems detected by static checks. This reviewer cannot prove "
                "correctness; the test judge is the source of truth."
            )
            next_step = "Walk through the smallest edge cases by hand, then submit."
        else:
            top = issues[0]
            summary = f"{len(issues)} {'thing' if len(issues) == 1 else 'things'} to look at. Most important: {top.detail}"
            next_step = top.suggestion

        if ctx.judge_status:
            summary += f" (Judge verdict: {ctx.judge_status}.)"

        return ProviderResult(
            content=CodeReview(
                summary=summary,
                complexity=Complexity(time=a.estimated_time, space=a.estimated_space),
                issues=issues,
                strengths=strengths,
                next_step=next_step,
                confidence="low" if a.is_unchanged_starter or not issues else "medium",
            ),
            provider=self.name,
            model=self.model,
        )
