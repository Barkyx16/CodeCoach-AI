"""Truthful execution capabilities, Run gating, idempotent submissions and runner URL safety."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import check_runner_url
from app.models import Submission, SubmissionStatus
from app.services.judge.runner_client import HttpRunner, RunnerAuthError, RunnerUnavailable
from tests.conftest import auth_headers, register
from tests.judge_fakes import TOKEN

CODE = "class Solution { public int[] twoSum(int[] n, int t) { return new int[]{0, 1}; } }"


def judged_client(make_client, probe):
    c = make_client(execution_enabled=True, runner_token=TOKEN)
    c.app.state.execution_health.probe = probe
    return c


def execution(client):
    return client.get("/api/v1/capabilities").json()["execution"]


def test_no_judge_is_reported_as_not_configured_with_setup_help(client):
    e = execution(client)
    assert e["state"] == "not_configured" and e["submit_mode"] == "saved_only" and not e["run_available"]
    assert "can't run here" in e["message"]
    assert "docs/REMOTE_JUDGE.md" in e["setup_help"] and "judge-check" in e["setup_help"]


def test_setup_help_is_hidden_in_production(client):
    client.app.state.settings.environment = "production"
    try:
        assert execution(client)["setup_help"] is None
    finally:
        client.app.state.settings.environment = "test"


def test_ready_only_after_an_authenticated_probe_succeeds(make_client):
    calls = []
    c = judged_client(make_client, lambda: calls.append(1) or True)
    e = execution(c)
    assert (
        e["state"] == "ready" and e["submit_mode"] == "judged" and e["run_available"] and e["reason"] == "ok"
    )
    execution(c)
    assert len(calls) == 1  # cached briefly; the endpoint stays cheap


@pytest.mark.parametrize(
    ("probe", "reason"),
    [
        (lambda: False, "judge_not_ready"),
        (lambda: (_ for _ in ()).throw(RunnerUnavailable("down")), "judge_unreachable"),
        (lambda: (_ for _ in ()).throw(RunnerAuthError("bad token")), "judge_misconfigured"),
    ],
)
def test_a_configured_but_broken_judge_is_temporarily_unavailable(make_client, probe, reason):
    c = judged_client(make_client, probe)
    e = execution(c)
    assert e["state"] == "unavailable" and e["reason"] == reason
    assert e["submit_mode"] == "queued_until_available" and not e["run_available"]
    assert "RUNNER" not in e["message"] and "http" not in e["message"]  # no internals for learners
    h = auth_headers(register(c))
    run = c.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": CODE, "mode": "run"}
    )
    assert run.status_code == 503 and run.json()["error"]["code"] == "judge_unavailable"
    sub = c.post("/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": CODE})
    assert sub.status_code == 202 and sub.json()["status"] == "QUEUED"  # waits for the judge


def test_a_stalled_queue_is_reported(make_client):
    c = judged_client(make_client, lambda: True)
    h = auth_headers(register(c))
    c.post("/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": CODE})
    db = c.app.state.session_factory()
    db.query(Submission).update({"created_at": datetime.now(UTC) - timedelta(minutes=5)})
    db.commit()
    db.close()
    e = execution(c)
    assert e["state"] == "unavailable" and e["reason"] == "queue_delayed" and e["run_available"]
    assert "worker" in e["setup_help"]


def test_a_retried_submission_with_the_same_request_id_is_judged_once(make_client):
    c = judged_client(make_client, lambda: True)
    h = auth_headers(register(c))
    body = {"problem_slug": "two-sum", "source_code": CODE, "client_request_id": "req-0123456789"}
    first = c.post("/api/v1/submissions", headers=h, json=body).json()
    again = c.post("/api/v1/submissions", headers=h, json=body).json()
    assert again["id"] == first["id"]
    reused = c.post("/api/v1/submissions", headers=h, json={**body, "source_code": CODE + " "})
    assert reused.status_code == 409 and reused.json()["error"]["code"] == "idempotency_key_reused"
    db = c.app.state.session_factory()
    assert db.query(Submission).count() == 1
    db.close()
    # Another user's identical key is independent.
    other = auth_headers(register(c, email="bob@example.com"))
    assert c.post("/api/v1/submissions", headers=other, json=body).json()["id"] != first["id"]


def test_concurrent_retries_create_one_submission(make_client):
    c = judged_client(make_client, lambda: True)
    h = auth_headers(register(c))
    body = {"problem_slug": "two-sum", "source_code": CODE, "client_request_id": "race-0123456789"}
    with ThreadPoolExecutor(4) as pool:
        ids = set(
            pool.map(lambda _: c.post("/api/v1/submissions", headers=h, json=body).json().get("id"), range(4))
        )
    assert len(ids) == 1 and None not in ids
    db = c.app.state.session_factory()
    assert db.query(Submission).filter(Submission.status == SubmissionStatus.QUEUED).count() == 1
    db.close()


def test_request_ids_are_validated(make_client):
    c = judged_client(make_client, lambda: True)
    h = auth_headers(register(c))
    for bad in ("short", "has spaces in it", "x" * 65):
        r = c.post(
            "/api/v1/submissions",
            headers=h,
            json={"problem_slug": "two-sum", "source_code": CODE, "client_request_id": bad},
        )
        assert r.status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8100",
        "http://127.0.0.1:8100",
        "http://[::1]:8100",
        "http://runner:8100",
        "https://judge.example.com",
    ],
)
def test_runner_urls_that_are_allowed(url):
    check_runner_url(url)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://judge.example.com:8100", "must use https://"),
        ("http://10.0.0.5:8100", "must use https://"),
        ("ftp://judge.example.com", "http(s) URL"),
        ("https://user:pw@judge.example.com", "must not contain credentials"),
    ],
)
def test_runner_urls_that_are_refused(url, message):
    with pytest.raises(ValueError, match=message.replace("(", r"\(").replace(")", r"\)")):
        check_runner_url(url)


def test_settings_refuse_a_plain_http_remote_judge(make_settings):
    with pytest.raises(ValueError, match="https"):
        make_settings(execution_enabled=True, runner_token=TOKEN, runner_url="http://judge.example.com:8100")


def test_the_status_probe_is_authenticated_and_never_skips_tls_verification():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401)
        return httpx.Response(200, json={"ready": True})

    ok = HttpRunner("https://judge.example.com", TOKEN, transport=httpx.MockTransport(handler))
    assert ok.status() is True and seen == [f"Bearer {TOKEN}"]
    bad = HttpRunner(
        "https://judge.example.com", "wrong-token-" + "x" * 30, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RunnerAuthError):
        bad.status()
    down = HttpRunner(
        "https://judge.example.com", TOKEN, transport=httpx.MockTransport(lambda r: httpx.Response(503))
    )
    with pytest.raises(RunnerUnavailable):
        down.status()
    real = HttpRunner("https://judge.example.com", TOKEN)
    assert real._client._transport._pool._ssl_context.verify_mode.name == "CERT_REQUIRED"  # type: ignore[attr-defined]


class _FakeProbeRunner:
    def __init__(self, status):
        self._status = status

    def status(self):
        if isinstance(self._status, Exception):
            raise self._status
        return self._status


def test_judge_check_reports_failures_plainly(make_settings):
    from app.services.judge.check import judge_check

    lines: list[str] = []
    assert judge_check(make_settings(), out=lines.append) == 2 and "not configured" in lines[0]
    s = make_settings(execution_enabled=True, runner_token=TOKEN)
    for status, expected in [
        (RunnerAuthError("bad"), "rejected RUNNER_TOKEN"),
        (RunnerUnavailable("down"), "can't be reached"),
        (False, "can't start sandboxes"),
    ]:
        lines.clear()
        assert judge_check(s, runner=_FakeProbeRunner(status), out=lines.append) == 1  # type: ignore[arg-type]
        assert expected in lines[-1] and TOKEN not in " ".join(lines)
