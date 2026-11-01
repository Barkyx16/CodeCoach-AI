"""Judge + worker + admission control, with a fake runner returning crafted sandbox results.
(The real gVisor path is covered by tests/test_judge_sandbox.py and runner/tests.)"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import ProgressEvent, ProgressEventType, Submission, SubmissionStatus
from app.services.judge.harness import result_prefix
from app.services.judge.judge import clean_compile_output
from app.services.judge.runner_client import RunnerResult, RunnerUnavailable
from app.worker import JudgeWorker
from tests.conftest import auth_headers, register

TOKEN = "r" * 40

# Expected outputs for the problem under test, filled in by each test once its app exists, and
# read by the fake runner's script to produce "correct" driver output.
EXPECTED: list = []


class FakeRunner:
    """Answers like the real runner. `script(files, nonce)` returns (status, stdout, extra)."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def run(self, files, nonce, time_limit_s):
        self.calls.append({"files": files, "nonce": nonce, "time_limit_s": time_limit_s})
        out = self.script(files, nonce)
        if isinstance(out, Exception):
            raise out
        status, stdout, extra = out
        return RunnerResult(
            status=status,
            exit_code=extra.get("exit_code", 0),
            stdout=stdout,
            stderr=extra.get("stderr", ""),
            compile_output=extra.get("compile_output"),
            run_started=status != "compile_error",
            output_truncated=status == "output_limit",
            duration_ms=900,
        )


def lines(nonce, outputs):
    """Driver output where test i returned outputs[i] (or raised, if a dict with 'exception')."""
    rows = []
    for i, out in enumerate(outputs):
        if out is None:
            continue
        if isinstance(out, dict) and "exception" in out:
            rows.append(result_prefix(nonce) + json.dumps({"index": i, "ok": False, **out, "ms": 0.2}))
        else:
            rows.append(result_prefix(nonce) + json.dumps({"index": i, "ok": True, "output": out, "ms": 0.2}))
    return "\n".join(rows)


def expected_outputs(client, slug):
    from app.models import Problem

    with client.app.state.session_factory() as db:
        p = db.scalar(select(Problem).where(Problem.slug == slug))
        return [t.expected_output for t in p.test_cases], [t.visibility.value for t in p.test_cases]


@pytest.fixture
def judged(make_client):
    """App with execution enabled + a worker bound to a fake runner."""

    def _make(script, **settings):
        c = make_client(execution_enabled=True, runner_token=TOKEN, **settings)
        runner = FakeRunner(script)
        worker = JudgeWorker(c.app.state.session_factory, runner, c.app.state.settings)
        headers = auth_headers(register(c))
        return c, runner, worker, headers

    return _make


def submit(c, headers, slug="two-sum", code="class Solution { /* learner code */ }"):
    return c.post("/api/v1/submissions", headers=headers, json={"problem_slug": slug, "source_code": code})


def test_execution_requires_a_runner_token(make_settings):
    with pytest.raises(ValueError, match="RUNNER_TOKEN"):
        make_settings(execution_enabled=True, runner_token=None)


def test_passing_submission(judged):
    c, runner, worker, h = judged(lambda files, nonce: ("ok", lines(nonce, EXPECTED[0]), {}))
    EXPECTED[:] = [expected_outputs(c, "two-sum")[0]]
    sub = submit(c, h).json()
    assert (
        sub["status"] == "QUEUED"
        and sub["execution_enabled"] is True
        and sub["status_detail"] == "Waiting for a judge…"
    )
    assert worker.process_one() is True
    done = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()
    assert done["status"] == "PASSED" and done["is_terminal"]
    r = done["result"]
    assert r["passed_count"] == r["total_count"] == 7
    assert r["hidden_passed"] == r["hidden_total"] == 4
    assert len(r["public_results"]) == 3 and all(x["passed"] for x in r["public_results"])
    assert r["stderr_excerpt"] is None
    # what went into the sandbox: learner code + generated driver, a fresh nonce, the time limit
    call = runner.calls[0]
    assert call["files"]["Solution.java"] == "class Solution { /* learner code */ }"
    assert "new Solution().twoSum" in call["files"]["Main.java"]
    assert len(call["nonce"]) == 32 and call["time_limit_s"] == 15.0
    # solving shows up in progress
    p = c.get("/api/v1/me/progress", headers=h).json()
    assert p["solved"] == 1 and p["acceptance_rate"] == 1.0


def test_failed_tests_reveal_public_details_only(judged):
    def script(files, nonce):
        outs = list(EXPECTED[0])
        outs[0] = [9, 9]  # public test 0 wrong
        outs[5] = [0, 0]  # hidden test wrong
        return ("ok", lines(nonce, outs), {"stderr": "HIDDEN-INPUT-PRINTED-BY-LEARNER"})

    c, _, worker, h = judged(script)
    EXPECTED[:] = [expected_outputs(c, "two-sum")[0]]
    sub = submit(c, h).json()
    worker.process_one()
    done = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()
    assert done["status"] == "FAILED"
    r = done["result"]
    assert r["passed_count"] == 5 and r["hidden_passed"] == 3 and r["hidden_total"] == 4
    first = r["public_results"][0]
    assert (
        first["passed"] is False and first["expected_output"] == [0, 1] and first["actual_output"] == [9, 9]
    )
    raw = json.dumps(done)
    assert "HIDDEN-INPUT-PRINTED-BY-LEARNER" not in raw  # run-phase output is never returned
    # Hidden inputs never appear in the response.
    from app.models import Problem

    with c.app.state.session_factory() as db:
        p = db.scalar(select(Problem).where(Problem.slug == "two-sum"))
        for t in p.test_cases:
            if t.visibility.value == "hidden":
                assert json.dumps(t.input) not in raw


def test_forged_lines_without_the_nonce_are_ignored(judged):
    def script(files, nonce):
        forged = lines("0" * 32, EXPECTED[0])  # all-correct answers with the wrong nonce
        return ("ok", forged, {"exit_code": 0})

    c, _, worker, h = judged(script)
    EXPECTED[:] = [expected_outputs(c, "two-sum")[0]]
    sub = submit(c, h).json()
    worker.process_one()
    done = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()
    assert done["status"] == "RUNTIME_ERROR" and done["result"]["passed_count"] == 0


@pytest.mark.parametrize(
    ("status", "outputs", "expected"),
    [
        ("timeout", "first-two", "TIME_LIMIT"),
        ("memory_limit", "first-two", "MEMORY_LIMIT"),
        ("output_limit", "first-two", "RUNTIME_ERROR"),
        ("ok", "first-two", "RUNTIME_ERROR"),  # program exited before finishing all tests
        ("ok", "stack-overflow", "RUNTIME_ERROR"),
    ],
)
def test_verdict_mapping(judged, status, outputs, expected):
    def script(files, nonce):
        outs = list(EXPECTED[0])
        if outputs == "first-two":
            outs = outs[:2] + [None] * (len(outs) - 2)
        elif outputs == "stack-overflow":
            outs[3] = {"exception": "StackOverflowError", "message": ""}
        return (status, lines(nonce, outs), {})

    c, _, worker, h = judged(script)
    EXPECTED[:] = [expected_outputs(c, "two-sum")[0]]
    sub = submit(c, h).json()
    worker.process_one()
    done = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()
    assert done["status"] == expected
    if outputs == "first-two":
        assert done["result"]["public_results"][2]["missing"] is True


def test_expected_exceptions_pass_and_messages_are_shown(judged):
    def script(files, nonce):
        outs = list(EXPECTED[0])
        outs[0] = {"exception": "ArithmeticException", "message": "/ by zero"}  # public test crashes
        return ("ok", lines(nonce, outs), {})

    c, _, worker, h = judged(script)
    EXPECTED[:] = [expected_outputs(c, "find-largest-number")[0]]
    sub = submit(c, h, slug="find-largest-number").json()
    worker.process_one()
    r = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()["result"]
    assert r["public_results"][0]["exception"] == "ArithmeticException"
    assert r["public_results"][0]["exception_message"] == "/ by zero"
    assert r["public_results"][0]["passed"] is False


def test_compile_errors_are_shown_without_sandbox_paths(judged):
    msg = "/tmp/src/Solution.java:3: error: ';' expected\n        return 1\n                ^\n1 error\n"
    c, _, worker, h = judged(lambda f, n: ("compile_error", "", {"exit_code": 91, "compile_output": msg}))
    sub = submit(c, h).json()
    worker.process_one()
    done = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()
    assert done["status"] == "COMPILE_ERROR"
    assert done["result"]["stderr_excerpt"].startswith("Solution.java:3: error")
    assert "/tmp/src" not in done["result"]["stderr_excerpt"]
    assert done["status_detail"] == "Your code didn't compile."


def test_compile_output_is_capped():
    assert len(clean_compile_output("x" * 10_000)) < 4100


def test_infrastructure_failures_retry_then_fail_gracefully(judged):
    c, runner, worker, h = judged(lambda f, n: RunnerUnavailable("connection refused"))
    sub = submit(c, h).json()
    worker.process_one()
    mid = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()
    assert mid["status"] == "QUEUED" and "Retrying" in mid["status_detail"]
    worker.process_one()
    done = c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()
    assert done["status"] == "INTERNAL_ERROR" and "wasn't your fault" in done["status_detail"]
    assert len(runner.calls) == 2  # judge_max_attempts
    assert worker.process_one() is False


def test_sandbox_errors_are_infrastructure_not_learner_failures(judged):
    c, _, worker, h = judged(lambda f, n: ("sandbox_error", "", {"exit_code": 125}), judge_max_attempts=1)
    sub = submit(c, h).json()
    worker.process_one()
    assert c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()["status"] == "INTERNAL_ERROR"


def test_jobs_are_claimed_oldest_first(judged):
    order = []
    c, _, worker, h = judged(
        lambda f, n: (order.append(f["Solution.java"]), ("ok", "", {}))[1], max_pending_per_user=5
    )
    for i in range(3):
        submit(c, h, code=f"class Solution {{ /* {i} */ }}")
    while worker.process_one():
        pass
    assert order == [f"class Solution {{ /* {i} */ }}" for i in range(3)]


def test_stale_running_jobs_are_recovered(judged):
    c, _, worker, h = judged(lambda f, n: ("ok", "", {}))
    sub = submit(c, h).json()
    with c.app.state.session_factory() as db:
        claimed = worker.claim(db)
        assert claimed.id == sub["id"]
    with c.app.state.session_factory() as db:  # the worker "died"; age the job
        s = db.get(Submission, sub["id"])
        s.judge_started_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()
        assert worker.recover_stale(db) == 1
    assert c.get(f"/api/v1/submissions/{sub['id']}", headers=h).json()["status"] == "QUEUED"


def test_admission_control(judged):
    c, _, worker, h = judged(lambda f, n: ("ok", "", {}), max_pending_per_user=1)
    assert submit(c, h).status_code == 202
    second = submit(c, h)
    assert second.status_code == 429 and second.json()["error"]["code"] == "submission_pending"


def test_rate_limit_per_minute(judged):
    c, _, worker, h = judged(
        lambda f, n: ("ok", "", {}), submission_rate_limit_per_minute=2, max_pending_per_user=10
    )
    assert [submit(c, h).status_code for _ in range(3)] == [202, 202, 429]


def test_global_queue_depth(judged):
    c, _, worker, h = judged(lambda f, n: ("ok", "", {}), max_queue_depth=1)
    other = auth_headers(register(c, email="other@example.com"))
    assert submit(c, h).status_code == 202
    busy = submit(c, other)
    assert busy.status_code == 503 and busy.json()["error"]["code"] == "judge_busy"


def test_solved_event_only_on_pass(judged):
    c, _, worker, h = judged(lambda f, n: ("ok", "", {}))
    submit(c, h)
    worker.process_one()
    with c.app.state.session_factory() as db:
        assert (
            db.scalar(select(ProgressEvent).where(ProgressEvent.event_type == ProgressEventType.SOLVED))
            is None
        )
        s = db.scalar(select(Submission))
        assert s.status == SubmissionStatus.RUNTIME_ERROR and s.attempts == 1 and s.judged_at is not None
