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


# --- hints ------------------------------------------------------------------------------------


def hint_level_text(level: int, name: str) -> str:
    """The hint level asked for, as the coach reads it (the level's guidance after it is CodeCoach's
    fixed instructions, not shown)."""
    return f"Requested hint level: {level} ({name})."


# --- failure explanations ---------------------------------------------------------------------


def failure_verdict_text(status: str) -> str:
    return f"Judge verdict: {status}"


def failure_counts_text(public_passed: int, public_total: int, hidden_passed: int, hidden_total: int) -> str:
    """Pass counts: the only thing ever sent about hidden tests."""
    return (
        f"Public tests passed: {public_passed}/{public_total}. "
        f"Hidden tests passed: {hidden_passed}/{hidden_total} (hidden inputs are secret)."
    )


def failing_test_text(
    index: int,
    input: dict | None,
    expected: object | None,
    actual: object | None,
    exception: str | None,
    message: str | None,
    line: int | None,
    missing: bool,
) -> str:
    """The first failing PUBLIC test with the program's output, exactly as the coach reads it."""
    return json.dumps(
        {
            "test": index + 1,
            "input": input,
            "expected": expected,
            "actual": actual,
            "exception": exception,
            "exception_message": message,
            "exception_line": line,
            "did_not_finish": missing,
        }
    )


# --- the coding interviewer -------------------------------------------------------------------


def transcript_line(phase: str, role: str, content: str) -> str:
    """One turn of an interview's conversation, as the interviewer reads it."""
    return f"[{phase}] {role.upper()}: {content}"


NO_MESSAGES = "(no messages yet)"


def transcript_text(lines: list[str]) -> str:
    return "\n".join(lines) or NO_MESSAGES


def interview_phase_text(phase: str, guide: str, candidate_turns_in_phase: int) -> str:
    """Where the interview is, as the interviewer reads it before writing its next message."""
    return (
        f"Current phase: {phase} ({guide}). The candidate has sent "
        f"{candidate_turns_in_phase} message(s) in this phase."
    )


def ending_text(end_reason: str | None) -> str:
    """How the interview ended, as the feedback reads it."""
    return f"How it ended: {end_reason or 'finished'}."
