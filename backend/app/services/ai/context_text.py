"""The words of a learner's private context exactly as the coach receives them (docs/COACH_CONTEXT.md).

Rendered here, once, for both the outside provider's prompt and the preview the learner approves,
so what's shown is what's sent, byte for byte."""

from __future__ import annotations

import json

from app.services.ai.static_analysis import Analysis


def analysis_text(a: Analysis) -> str:
    """CodeCoach's own checks of the code: derived from it, never written by the learner."""
    findings = [
        {"severity": f.severity, "category": f.category, "detail": f.detail, "line": f.line}
        for f in a.findings
    ]
    return (
        f"Heuristic complexity estimate: time {a.estimated_time}, space {a.estimated_space}\n"
        f"Static findings (heuristic, may contain false positives): {json.dumps(findings)}"
    )


NO_VERDICT = "none given (this code may not have been judged)"


def verdict_text(judge_status: str | None) -> str:
    """The judge's verdict as the coach reads it. Left out (or never judged) reads the same, so
    leaving it out says nothing about whether there was one."""
    return judge_status or NO_VERDICT
