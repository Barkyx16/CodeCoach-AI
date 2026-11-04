"""How the coach behaves when Claude fails, checked with a client that fails on purpose.

Each scenario makes the real `AnthropicCoach` meet one failure the SDK can produce (a timeout, a
lost connection, a 429 or 5xx, a refusal, a cut-off or invalid structured reply) or a reply that
is valid but unusable (nonsense, a failure explanation with no evidence or invented evidence)
inside the real
`CoachService.call_with_fallback`. The learner must get a schema-valid answer from the offline
coach, labelled as a fallback, and nothing may escape as an error.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
from pydantic import TypeAdapter, ValidationError

from app.config import Settings
from app.schemas.ai import CodeReview, Complexity, FailureExplanation, HintContent
from app.services.ai.anthropic_provider import AnthropicCoach
from app.services.ai.base import FailureContext, HintContext, ReviewContext
from app.services.ai.service import CoachService
from app.services.ai.static_analysis import analyze

_REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status(cls: type[anthropic.APIStatusError], code: int) -> anthropic.APIStatusError:
    return cls(f"HTTP {code}", response=httpx.Response(code, request=_REQ), body=None)


def _cut_off(schema: type) -> ValidationError:
    """What `messages.parse` raises when the reply's JSON is cut off: the SDK validates the text
    against the schema while building the response."""
    try:
        TypeAdapter(schema).validate_json('{"summary": "Your loop looks')
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a validation error")


def _schema_violation(schema: type) -> ValidationError:
    """What `messages.parse` raises for a reply that is valid JSON but misses required fields and
    carries a value the schema doesn't allow (an unknown confidence level)."""
    try:
        TypeAdapter(schema).validate_python({"confidence": "certain", "level": 9})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a validation error")


def _reply(stop_reason: str, parsed: Any = None) -> Callable[[dict], SimpleNamespace]:
    return lambda kw: SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop_reason,
        model=kw["model"],
        usage=SimpleNamespace(input_tokens=0, output_tokens=0),
    )


def _nonsense(schema: type) -> Callable[[dict], SimpleNamespace]:
    """A reply that matches the schema and says nothing usable: required text empty, a complexity
    that isn't Big-O notation."""
    parsed = {
        HintContent: lambda: HintContent(hint="   ", focus_area="", encouragement=""),
        CodeReview: lambda: CodeReview(
            summary="",
            complexity=Complexity(time="banana", space="?"),
            issues=[],
            strengths=[],
            next_step="",
            confidence="high",
        ),
        FailureExplanation: lambda: FailureExplanation(
            cause="other", headline="", explanation="", evidence="", next_steps=[], confidence="high"
        ),
    }[schema]()
    return _reply("end_turn", parsed)


def _explanation(evidence: str) -> FailureExplanation:
    return FailureExplanation(
        cause="wrong-answer",
        headline="The loop stops one element early.",
        explanation="The bound skips the last index.",
        evidence=evidence,
        next_steps=["Check the loop bound against the array length."],
        confidence="medium",
    )


SCENARIOS: dict[str, Callable[[type], Any]] = {
    "timeout": lambda schema: anthropic.APITimeoutError(request=_REQ),
    "connection_lost": lambda schema: anthropic.APIConnectionError(request=_REQ),
    "rate_limited_429": lambda schema: _status(anthropic.RateLimitError, 429),
    "server_error_500": lambda schema: _status(anthropic.InternalServerError, 500),
    "overloaded_529": lambda schema: _status(anthropic.APIStatusError, 529),
    "refusal": lambda schema: _reply("refusal"),
    "cut_off_max_tokens": lambda schema: _reply("max_tokens"),
    "no_parsed_output": lambda schema: _reply("end_turn"),
    "cut_off_json": _cut_off,
    "missing_fields_and_invalid_value": _schema_violation,
    "invalid_response_body": lambda schema: anthropic.APIResponseValidationError(
        response=httpx.Response(200, request=_REQ), body=None
    ),
    "schema_valid_nonsense": _nonsense,
    # Only failure explanations cite evidence; for the other actions these don't apply (None).
    "missing_required_evidence": lambda schema: (
        _reply("end_turn", _explanation("")) if schema is FailureExplanation else None
    ),
    "invented_evidence": lambda schema: (
        _reply("end_turn", _explanation('The hidden test "[9, 9, 9]" returned "[0, 0]".'))
        if schema is FailureExplanation
        else None
    ),
}


class FailingMessages:
    def __init__(self, outcome: Any) -> None:
        self.outcome, self.calls = outcome, 0

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls += 1
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome(kwargs)


def _contexts() -> dict[str, tuple[type, Callable[[Any], Any]]]:
    from evals.run import problem_contexts

    p = problem_contexts()["two-sum"]
    code = p.starter_code
    a = analyze(code)
    return {
        "hint": (
            HintContent,
            lambda coach: coach.hint(HintContext(problem=p, code=code, level=1, analysis=a)),
        ),
        "review": (
            CodeReview,
            lambda coach: coach.review(ReviewContext(problem=p, code=code, analysis=a, judge_status=None)),
        ),
        "explain_failure": (
            FailureExplanation,
            lambda coach: coach.explain_failure(
                FailureContext(
                    problem=p,
                    code=code,
                    analysis=a,
                    status="FAILED",
                    compile_output=None,
                    failing_case=None,
                    public_passed=0,
                    public_total=3,
                    hidden_passed=0,
                    hidden_total=5,
                )
            ),
        ),
    }


def run_faults(make_coach: Callable[[Any], Any] | None = None) -> dict:
    make_coach = make_coach or (
        # No real waiting between retries here: the retry policy is what's checked, not the clock.
        lambda client: AnthropicCoach(api_key=None, model="fault-check", client=client, sleep=lambda s: None)
    )
    rows = []
    for scenario, build in SCENARIOS.items():
        for action, (schema, call) in _contexts().items():
            outcome = build(schema)
            if outcome is None:
                continue  # the scenario doesn't apply to this action
            messages = FailingMessages(outcome)
            service = CoachService(
                db=None, settings=Settings(), provider=make_coach(SimpleNamespace(messages=messages))
            )  # type: ignore[arg-type]
            row: dict = {"scenario": scenario, "action": action}
            start = time.perf_counter()
            try:
                result = service.call_with_fallback(call)
            except Exception as exc:  # noqa: BLE001 - this is what the check is looking for
                row.update(passed=False, problem=f"{type(exc).__name__} escaped instead of falling back")
            else:
                problems = []
                if result.provider != "offline (fallback)":
                    problems.append(f"answered by {result.provider!r}, expected the offline fallback")
                try:
                    schema.model_validate(result.content.model_dump())
                except ValidationError:
                    problems.append("the fallback answer doesn't match the schema")
                row.update(passed=not problems, problem="; ".join(problems) or None, provider=result.provider)
            row["calls_to_provider"] = messages.calls
            row["ms"] = round((time.perf_counter() - start) * 1000, 2)
            rows.append(row)
    coach = AnthropicCoach(api_key="sk-ant-not-a-real-key", model="m")  # constructs, never connects
    bounded = coach._client
    return {
        "scenarios": len(SCENARIOS),
        "checks": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "failed": [r for r in rows if not r["passed"]],
        "rows": rows,
        "client_limits": {
            "timeout_s": float(bounded.timeout),  # type: ignore[arg-type]
            "max_retries": bounded.max_retries,  # the SDK's own; 0: the coach retries, counted
            "max_attempts": coach.max_attempts,
            "deadline_s": coach.deadline_s,
        },
    }
