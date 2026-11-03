"""One user action followed across the browser, the API, evaluation, the database and the judge.

These drive the real app (TestClient) and read what an operator would read: response headers,
the admin trace lookup, the Prometheus text and the structured log lines.
"""

import json
import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app import tracing
from app.models import Submission, SubmissionStatus, User
from app.worker import JudgeWorker
from tests.conftest import auth_headers, register
from tests.judge_fakes import EXPECTED, TOKEN, FakeRunner, expected_outputs, lines, submit
from tests.test_question_rounds import NURSE_ANSWER, answer, nurse, start

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT = "00f067aa0ba902b7"
TRACEPARENT = f"00-{TRACE}-{PARENT}-01"


def admin(client, email="ops@example.com"):
    headers = auth_headers(register(client, email=email))
    with client.app.state.session_factory() as db:
        db.scalar(select(User).where(User.email == email)).is_admin = True
        db.commit()
    return headers


def unraising(client):
    """The same app, answering 500 for unhandled errors instead of raising them into the test."""
    return TestClient(client.app, raise_server_exceptions=False)


def lookup(client, headers, any_id):
    return client.get(f"/api/v1/admin/traces/{any_id}", headers=headers)


def metric(client, name, **labels):
    """The value of one sample in /metrics (0 when absent)."""
    want = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))  # Prometheus sorts labels
    for line in client.get("/metrics").text.splitlines():
        if line.startswith(f"{name}{{{want}}}" if want else f"{name} "):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


# --- trace context -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header, expected",
    [
        (TRACEPARENT, (TRACE, PARENT)),
        (TRACEPARENT.upper(), (TRACE, PARENT)),
        ("01-" + TRACEPARENT[3:], None),  # unknown version
        (f"00-{'0' * 32}-{PARENT}-01", None),  # all-zero trace id
        (f"00-{TRACE}-{'0' * 16}-01", None),  # all-zero parent
        (f"00-{TRACE[:-1]}-{PARENT}-01", None),  # wrong length
        ("00-not-hex-at-all-01", None),
        ("", None),
        (None, None),
    ],
)
def test_traceparent_is_validated(header, expected):
    assert tracing.parse_traceparent(header) == expected


def test_attributes_pass_an_allowlist_and_are_short():
    cleaned = tracing.clean_attrs(
        {"action": "answer", "answer": "secret text", "email": "a@b.c", "result": "x" * 500}
    )
    assert set(cleaned) == {"action", "result"} and len(str(cleaned["result"])) == 64


def test_the_browser_trace_id_is_adopted_and_returned(client):
    r = client.get("/health", headers={"traceparent": TRACEPARENT})
    assert r.headers["x-trace-id"] == TRACE and r.headers["x-request-id"]
    other = client.get("/health", headers={"traceparent": "garbage"})
    assert len(other.headers["x-trace-id"]) == 32 and other.headers["x-trace-id"] != TRACE
    third = client.get("/health")
    assert third.headers["x-trace-id"] != other.headers["x-trace-id"]  # a new trace per request
    assert tracing.current_trace_id() is None  # nothing leaks into the caller's context


# --- one action, end to end ----------------------------------------------------------------


def test_one_answer_is_followed_through_the_api_evaluation_and_database(client):
    h = nurse(client)
    iv = start(client, h, format="behavioral").json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers={**h, "traceparent": TRACEPARENT},
        json={"question_index": 0, "answer": NURSE_ANSWER, "source": "typed"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["x-trace-id"] == TRACE
    request_id = r.headers["x-request-id"]

    ops = admin(client)
    by_trace = lookup(client, ops, TRACE).json()
    by_request = lookup(client, ops, request_id).json()
    assert by_trace == by_request and by_trace["trace_id"] == TRACE
    spans = {s["name"]: s for s in by_trace["spans"]}
    assert set(spans) >= {"http", "round.action", "evaluate", "db.commit"}
    http, action = spans["http"], spans["round.action"]
    assert http["parent_id"] == PARENT  # the browser's span is the parent
    assert http["attrs"] == {
        "method": "POST",
        "route": "/api/v1/interviews/{interview_id}/answers",
        "status": 200,
    }
    assert action["parent_id"] == http["span_id"]
    assert spans["evaluate"]["parent_id"] == action["span_id"]
    assert spans["db.commit"]["parent_id"] == action["span_id"]
    assert action["attrs"]["action"] == "answer" and action["attrs"]["format"] == "behavioral"
    assert action["attrs"]["result"] in {"advanced", "followup"}
    assert all(s["outcome"] == "ok" and s["request_id"] == request_id for s in by_trace["spans"])
    assert spans["evaluate"]["duration_ms"] <= action["duration_ms"] <= http["duration_ms"]


def test_a_repeated_submit_is_counted_once_as_a_duplicate(client):
    h = nurse(client)
    iv = start(client, h, format="behavioral").json()
    assert answer(client, h, iv["id"], 0).status_code == 200
    first = metric(client, "codecoach_round_actions_total", action="answer", outcome="advanced") + metric(
        client, "codecoach_round_actions_total", action="answer", outcome="followup"
    )
    assert first == 1
    assert answer(client, h, iv["id"], 0).status_code == 200  # the retry after a lost response
    assert metric(client, "codecoach_round_actions_total", action="answer", outcome="duplicate") == 1
    again = metric(client, "codecoach_round_actions_total", action="answer", outcome="advanced") + metric(
        client, "codecoach_round_actions_total", action="answer", outcome="followup"
    )
    assert again == 1  # not a second success


def test_an_evaluator_failure_is_an_error_on_that_step_and_counted(client, monkeypatch):
    h = nurse(client)
    iv = start(client, h).json()

    def broken(*_args, **_kwargs):
        raise RuntimeError("evaluator crashed")

    monkeypatch.setattr("app.services.question_rounds.graded_answer", broken)
    r = unraising(client).post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers={**h, "traceparent": TRACEPARENT},
        json={"question_index": 0, "answer": NURSE_ANSWER, "source": "typed"},
    )
    assert r.status_code == 500
    spans = {s["name"]: s for s in lookup(client, admin(client), TRACE).json()["spans"]}
    assert spans["evaluate"]["outcome"] == "error"
    assert spans["round.action"]["outcome"] == "error"
    assert spans["http"]["outcome"] == "error" and spans["http"]["attrs"]["status"] == 500
    assert "db.commit" not in spans  # nothing was saved
    assert metric(client, "codecoach_round_actions_total", action="answer", outcome="error") == 1


def test_a_database_failure_is_categorised_without_leaking_the_error(client, monkeypatch):
    h = nurse(client)
    iv = start(client, h).json()
    from app.services.interviews import InterviewService

    real_commit = InterviewService._commit

    def failing_commit(self):
        def boom():
            raise OperationalError("COMMIT", {}, Exception("disk I/O error"))

        monkeypatch.setattr(self.db, "commit", boom)
        real_commit(self)

    monkeypatch.setattr(InterviewService, "_commit", failing_commit)
    r = unraising(client).post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers={**h, "traceparent": TRACEPARENT},
        json={"question_index": 0, "answer": NURSE_ANSWER, "source": "typed"},
    )
    assert r.status_code == 500
    spans = {s["name"]: s for s in lookup(client, admin(client), TRACE).json()["spans"]}
    assert spans["db.commit"]["outcome"] == "db_error"
    assert spans["round.action"]["outcome"] == "db_error"
    assert metric(client, "codecoach_round_actions_total", action="answer", outcome="db_error") == 1
    assert "disk I/O" not in json.dumps(spans)


def test_rejected_actions_carry_the_error_code(client):
    h = nurse(client)
    iv = start(client, h).json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers={**h, "traceparent": TRACEPARENT},
        json={"question_index": 3, "answer": NURSE_ANSWER, "source": "typed"},  # not the current one
    )
    assert r.status_code == 409
    spans = {s["name"]: s for s in lookup(client, admin(client), TRACE).json()["spans"]}
    assert spans["round.action"]["outcome"] == "rejected"
    assert spans["round.action"]["attrs"]["error_code"] == r.json()["error"]["code"]
    assert spans["http"]["outcome"] == "rejected"


def test_no_answers_emails_or_tokens_in_logs_or_traces(client, caplog):
    marker = "Zanzibar-unique-answer-marker "
    caplog.set_level(logging.INFO, logger="codecoach")
    tokens = register(client, email="private.person@example.com", career_track="registered-nurse")
    h = auth_headers(tokens)
    iv = start(client, h).json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers={**h, "traceparent": TRACEPARENT},
        json={"question_index": 0, "answer": marker + NURSE_ANSWER, "source": "typed"},
    )
    assert r.status_code == 200
    stored = json.dumps(lookup(client, admin(client), TRACE).json())
    logged = "\n".join(
        json.dumps({k: str(v) for k, v in vars(rec).items()})
        for rec in caplog.records
        if rec.name in ("codecoach.trace", "codecoach.access")  # the telemetry loggers
    )
    span_logs = "\n".join(
        json.dumps({k: str(v) for k, v in vars(rec).items()})
        for rec in caplog.records
        if rec.name == "codecoach.trace"
    )
    for secret in (marker.strip(), "private.person@example.com", tokens["access_token"]):
        assert secret not in stored, secret
        assert secret not in logged, secret
    # Resource ids aren't span attributes; the access log keeps the request path (never a query).
    assert iv["id"] not in stored and iv["id"] not in span_logs
    assert any(getattr(rec, "span", None) == "round.action" for rec in caplog.records)  # spans are logged


def test_admins_only(client):
    h = nurse(client)
    client.get("/health", headers={"traceparent": TRACEPARENT})
    # Like the other admin routes: a plain 404 for everyone else, so the area isn't discoverable.
    assert lookup(client, h, TRACE).status_code == 404
    assert client.get(f"/api/v1/admin/traces/{TRACE}").status_code == 404
    assert lookup(client, admin(client), "0123456789abcdef0123456789abcdef").status_code == 404


def test_a_broken_trace_store_never_breaks_practice(client, monkeypatch):
    h = nurse(client)
    iv = start(client, h).json()

    def broken(_record):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(client.app.state.traces, "add_span", broken)
    assert answer(client, h, iv["id"], 0).status_code == 200
    assert metric(client, "codecoach_telemetry_dropped_total", kind="span") >= 1


def test_the_store_is_bounded():
    store = tracing.TraceStore(max_traces=3, max_spans=2)
    for i in range(10):
        trace_id = f"{i:032x}"
        for _ in range(5):
            store.add_span(
                tracing.SpanRecord(trace_id, "a" * 16, None, "x", 0.0, 1.0, "ok", request_id=f"req-{i:05d}")
            )
    assert len(store) == 3 and store.get(f"{0:032x}") is None
    assert len(store.get(f"{9:032x}")["spans"]) == 2 and store.get("req-00009")["trace_id"] == f"{9:032x}"


# --- what the browser saw ------------------------------------------------------------------


def ui_event(**overrides):
    return {
        "trace_id": TRACE,
        "action": "answer",
        "outcome": "network_error",
        "duration_ms": 812,
        "status": 0,
        **overrides,
    }


def test_browser_reports_join_the_servers_spans(client):
    h = nurse(client)
    iv = start(client, h).json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers={**h, "traceparent": TRACEPARENT},
        json={"question_index": 0, "answer": NURSE_ANSWER, "source": "typed"},
    )
    # The answer was saved, but the browser never got the response: it says so.
    sent = client.post(
        "/api/v1/telemetry/ui", headers=h, json={"events": [ui_event(request_id=r.headers["x-request-id"])]}
    )
    assert sent.status_code == 204
    trace = lookup(client, admin(client), TRACE).json()
    assert {s["name"] for s in trace["spans"]} >= {"round.action"}
    assert trace["events"] == [
        {
            "source": "browser",
            "action": "answer",
            "outcome": "network_error",
            "duration_ms": 812,
            "request_id": r.headers["x-request-id"],
            "status": 0,
            "error_code": None,
            "at": trace["events"][0]["at"],
        }
    ]
    assert metric(client, "codecoach_ui_actions_total", action="answer", outcome="network_error") == 1


@pytest.mark.parametrize(
    "bad",
    [
        {"action": "delete_account"},
        {"outcome": "great"},
        {"duration_ms": -1},
        {"duration_ms": 10_000_000},
        {"trace_id": "not-a-trace"},
        {"request_id": "../../etc"},
        {"answer": "the learner's words"},  # unknown fields are not stored either
    ],
)
def test_browser_reports_are_a_fixed_vocabulary(client, bad):
    h = nurse(client)
    r = client.post("/api/v1/telemetry/ui", headers=h, json={"events": [ui_event(**bad)]})
    if "answer" in bad:
        assert r.status_code == 204
        stored = json.dumps(lookup(client, admin(client), TRACE).json())
        assert "learner's words" not in stored
    else:
        assert r.status_code == 422


def test_browser_reports_need_an_account_are_bounded_and_can_be_switched_off(client, make_client):
    assert client.post("/api/v1/telemetry/ui", json={"events": [ui_event()]}).status_code == 401
    h = nurse(client)
    too_many = {"events": [ui_event()] * 21}
    assert client.post("/api/v1/telemetry/ui", headers=h, json=too_many).status_code == 422
    assert client.get("/api/v1/capabilities").json()["ui_telemetry"] is True
    off = make_client(ui_telemetry_enabled=False)
    oh = nurse(off, email="off@example.com")
    assert off.get("/api/v1/capabilities").json()["ui_telemetry"] is False
    assert off.post("/api/v1/telemetry/ui", headers=oh, json={"events": [ui_event()]}).status_code == 404


def test_over_the_limit_reports_are_dropped_not_refused(client):
    h = nurse(client)
    for _ in range(120):
        client.post("/api/v1/telemetry/ui", headers=h, json={"events": [ui_event()]})
    r = client.post("/api/v1/telemetry/ui", headers=h, json={"events": [ui_event()]})
    assert r.status_code == 204  # never an error the browser would retry
    assert metric(client, "codecoach_telemetry_dropped_total", kind="ui_rate_limited") == 1


# --- background work: the judge continues the trace ----------------------------------------


def test_the_judge_worker_continues_the_trace_of_the_request_that_queued_the_job(make_client):
    c = make_client(execution_enabled=True, runner_token=TOKEN)
    c.app.state.execution_health.probe = lambda: True
    EXPECTED[:] = [expected_outputs(c, "two-sum")[0]]
    runner = FakeRunner(lambda files, nonce: ("ok", lines(nonce, EXPECTED[0]), {}))
    worker = JudgeWorker(
        c.app.state.session_factory, runner, c.app.state.settings, c.app.state.traces, c.app.state.metrics
    )
    h = auth_headers(register(c))
    sub = submit(c, {**h, "traceparent": TRACEPARENT}).json()
    assert metric(c, "codecoach_judge_queued_jobs") == 1
    with c.app.state.session_factory() as db:
        assert db.get(Submission, sub["id"]).trace_id == TRACE
    assert worker.process_one() is True
    assert tracing.current_trace_id() is None  # the job's trace didn't leak into the worker
    spans = {s["name"]: s for s in lookup(c, admin(c), TRACE).json()["spans"]}
    run = spans["judge.run"]
    assert (
        run["outcome"] == "ok" and run["attrs"]["verdict"] == "PASSED" and run["attrs"]["language"] == "java"
    )
    assert run["attrs"]["attempt"] == 1 and run["attrs"]["queue_wait_ms"] >= 0
    assert (
        metric(c, "codecoach_judge_queued_jobs") == 0
        and metric(c, "codecoach_judge_oldest_queued_seconds") == 0
    )


def test_a_job_that_ran_out_of_time_is_recorded_as_a_timeout(make_client):
    c = make_client(execution_enabled=True, runner_token=TOKEN)
    c.app.state.execution_health.probe = lambda: True
    worker = JudgeWorker(
        c.app.state.session_factory,
        FakeRunner(lambda *_: ("ok", "", {})),
        c.app.state.settings,
        c.app.state.traces,
        c.app.state.metrics,
    )
    h = auth_headers(register(c))
    sub = submit(c, {**h, "traceparent": TRACEPARENT}).json()
    with c.app.state.session_factory() as db:
        row = db.get(Submission, sub["id"])
        row.status = SubmissionStatus.RUNNING
        row.attempts = 1
        row.judge_started_at = row.created_at - timedelta(hours=1)  # long past the stale limit
        db.commit()
        assert worker.recover_stale(db) == 1
    spans = {s["name"]: s for s in lookup(c, admin(c), TRACE).json()["spans"]}
    assert (
        spans["judge.recover"]["outcome"] == "timeout"
        and spans["judge.recover"]["attrs"]["result"] == "requeued"
    )
    assert metric(c, "codecoach_span_duration_seconds_count", span="judge.recover", outcome="timeout") == 1
