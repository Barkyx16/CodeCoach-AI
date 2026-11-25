"""The live-provider evaluation, prepared and tested without calling Claude (Volume 4 brief 06 /
prompt 08): a dry-run plan, credential checks that never show the key, budgets that hold through
retries and concurrency, every outcome counted by reason, unknown prices left unknown, partial
runs labelled, and no credentials in the report. Every client here is a fake: default CI makes
zero live calls."""

import inspect
import json
import re
import threading
import time
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.schemas.ai import CodeReview, Complexity
from app.services.ai.anthropic_provider import AnthropicCoach
from evals import run as runner
from evals.run import BudgetExhausted, Metered, dispatch, evaluate_reviews, main, plan, problem_contexts

SECRET = "sk-ant-api03-NOT-A-REAL-KEY-7731"
_REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
REVIEW = CodeReview(
    summary="Clear loop.",
    complexity=Complexity(time="O(n)", space="O(1)"),
    issues=[],
    strengths=["readable"],
    next_step="Test an empty array.",
    confidence="medium",
)


class Always:
    """messages.parse that always gives the same outcome; counts requests."""

    def __init__(self, outcome, delay: float = 0.0):
        self.outcome, self.delay, self.calls = outcome, delay, 0
        self._lock = threading.Lock()
        self.messages = self

    def with_options(self, timeout):
        return self

    def parse(self, **kwargs):
        with self._lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        if self.outcome == "refusal":
            return SimpleNamespace(parsed_output=None, stop_reason="refusal", model="m", usage=None)
        return SimpleNamespace(
            parsed_output=self.outcome,
            stop_reason="end_turn",
            model="claude-test-model",
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )


def coach(outcome, delay: float = 0.0) -> tuple[AnthropicCoach, Always]:
    client = Always(outcome, delay)
    return AnthropicCoach(
        api_key=None, model="claude-test-model", client=client, sleep=lambda s: None
    ), client


def review_samples(n: int) -> list[dict]:
    samples = json.loads((runner.EVAL_DIR / "review_set.json").read_text())["samples"]
    return samples[:n]


# --- before a run -----------------------------------------------------------------------------


def test_the_plan_sends_nothing_and_says_where_the_budgets_stop_it(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: pytest.fail("a client was built"))
    p = plan(split="dev", sections=("coding",), limit=2, max_calls=10, max_output_tokens=12_000)
    assert p["sends_requests"] is False
    assert p["answers_total"] == 2 + 2 * 2  # two reviews, two problems' hints at levels 1 and 2
    assert p["worst_case_requests"] == 6 * 3
    assert any("--max-calls 10" in x for x in p["budget_stops"])
    assert p["worst_case_output_cost_usd"].startswith("unknown")  # no prices given
    priced = plan(split="dev", sections=("coding",), limit=2, max_calls=2, prices={"output_per_mtok": 10.0})
    assert priced["worst_case_output_cost_usd"] == round(2 * 4_000 / 1e6 * 10.0, 4)  # capped by the calls


def test_the_plans_token_figures_are_the_ones_the_coach_asks_for():
    for action, limit in runner.MAX_TOKENS.items():
        source = inspect.getsource(getattr(AnthropicCoach, action))
        assert re.search(rf"max_tokens={limit:_}\b", source), action


def test_the_provider_check_never_shows_the_key(monkeypatch, capsys):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    monkeypatch.setattr("sys.argv", ["evals.run", "--check-provider"])
    with pytest.raises(SystemExit) as done:
        main()
    out = capsys.readouterr().out
    assert done.value.code == 0 and json.loads(out)["api_key_set"] is True
    assert SECRET not in out and SECRET[:12] not in out


def test_a_live_run_without_credentials_stops_before_anything_is_sent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "offline")
    monkeypatch.setattr(
        "sys.argv", ["evals.run", "--provider", "anthropic", "--allow-paid-calls", "--max-calls", "5"]
    )
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: pytest.fail("a client was built"))
    with pytest.raises(SystemExit, match="isn't configured"):
        main()


def test_concurrency_is_bounded(monkeypatch):
    monkeypatch.setattr("sys.argv", ["evals.run", "--plan", "--concurrency", "9"])
    with pytest.raises(SystemExit, match="between 1 and 4"):
        main()


# --- budgets ----------------------------------------------------------------------------------


def test_retries_never_go_past_the_call_budget():
    c, client = coach(anthropic.APITimeoutError(request=_REQ))  # every request times out and is retried
    metered = Metered(c, max_calls=4)
    with pytest.raises(BudgetExhausted):
        evaluate_reviews(metered, review_samples(3), problem_contexts())
    assert client.calls == 4 and metered.calls == 4  # the fifth request was never sent
    assert metered.usage(None)["failures_by_reason"] == {"timeout": 1}  # the first answer: 3 tries


def test_the_output_token_budget_is_reserved_before_each_request():
    # A review asks for up to 4,000 output tokens. A request that times out reports no usage, so it
    # counts at that maximum: after two, a third (8,000 + 4,000) would pass 10,000 and isn't sent.
    c, client = coach(anthropic.APITimeoutError(request=_REQ))
    metered = Metered(c, max_output_tokens=10_000)
    with pytest.raises(BudgetExhausted, match="10000 output tokens"):
        evaluate_reviews(metered, review_samples(3), problem_contexts())
    assert client.calls == 2 and metered.usage(None)["output_tokens_unreported_upper_bound"] == 8_000
    # Answers that report their usage free their reservation: many fit in the same budget.
    c2, client2 = coach(REVIEW)
    metered2 = Metered(c2, max_output_tokens=10_000)
    evaluate_reviews(metered2, review_samples(5), problem_contexts())
    assert client2.calls == 5 and metered2.output_tokens == 5 * 50 and metered2.reserved_output == 0


def test_running_several_at_once_cannot_overspend():
    c, client = coach(REVIEW, delay=0.02)
    metered = Metered(c, max_calls=5)
    p = problem_contexts()["two-sum"]
    ctx = runner.ReviewContext(
        problem=p, code=p.starter_code, analysis=runner.analyze(p.starter_code), judge_status=None
    )
    with pytest.raises(BudgetExhausted):
        dispatch(metered.review, [ctx] * 12, concurrency=4)
    assert client.calls == 5 and metered.calls == 5  # four at a time, and still never a sixth


# --- outcomes ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (anthropic.APITimeoutError(request=_REQ), "timeout"),
        ("refusal", "refusal"),
        (
            CodeReview(
                summary="",
                complexity=Complexity(time="banana", space="?"),
                issues=[],
                strengths=[],
                next_step="",
                confidence="high",
            ),
            "empty_text",
        ),
        (None, "invalid_output"),  # what parse gives for a reply that doesn't fit the schema
    ],
)
def test_every_outcome_is_counted_by_reason_and_never_credited_to_claude(outcome, reason):
    c, _ = coach(outcome)
    metered = Metered(c, max_calls=20)
    result = evaluate_reviews(metered, review_samples(2), problem_contexts())
    assert result["provider_errors"] == 2 and result["schema_validity"] == 0.0
    usage = metered.usage(None)
    assert usage["answers"] == 0 and usage["failures_by_reason"] == {reason: 2}


def test_prices_turn_into_a_cost_only_when_given_and_failed_requests_are_an_upper_bound():
    c, _ = coach(REVIEW)
    metered = Metered(c, max_calls=10)
    evaluate_reviews(metered, review_samples(2), problem_contexts())
    unknown = metered.usage(None)
    assert unknown["cost_usd"] is None and "not estimated" in unknown["cost_basis"]
    priced = metered.usage({"input_per_mtok": 1.0, "output_per_mtok": 2.0, "source": "test"})
    assert priced["cost_usd"] == round(200 / 1e6 * 1.0 + 100 / 1e6 * 2.0, 4)
    assert priced["models_seen"] == ["claude-test-model"] and priced["retries"] == 0


# --- the report ---------------------------------------------------------------------------------


def _live(monkeypatch, outcome, **kw):
    c, client = coach(outcome)
    monkeypatch.setattr(runner, "build_provider", lambda settings: c)
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    report = runner.run("anthropic", split="dev", sections=("coding",), limit=2, **kw)
    return report, client


def test_a_run_stopped_by_its_budget_is_labelled_partial_and_names_what_was_sent(monkeypatch):
    report, client = _live(monkeypatch, REVIEW, max_calls=3)
    assert not report["complete"] and any("budget of 3 calls" in r for r in report["incomplete_reasons"])
    assert report["live"]["status"].startswith("partial: 3 requests")
    assert report["usage"]["calls"] == client.calls == 3
    assert next(g for g in report["gates"] if g["id"] == "report.integrity")["status"] == "failed"


def test_failures_in_a_live_run_are_not_answers_and_the_report_holds_no_credentials(monkeypatch):
    report, _ = _live(monkeypatch, anthropic.APITimeoutError(request=_REQ), max_calls=100)
    assert report["usage"]["answers"] == 0 and report["usage"]["failures_by_reason"]["timeout"] > 0
    assert report["review"]["provider_errors"] == 2  # not answered by the offline coach instead
    text = json.dumps(report)
    assert SECRET not in text and SECRET[:12] not in text


def test_an_offline_run_says_claude_was_not_evaluated():
    report = runner.run("offline", split="dev", sections=("coding",), limit=1)
    assert report["live"] == {
        "provider_called": False,
        "status": "not evaluated: the offline coach ran; no request was sent to Claude",
    }
