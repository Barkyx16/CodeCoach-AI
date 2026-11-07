"""'Run' mode: public tests only, quick feedback, never an attempt.

The real-sandbox version is in tests/test_judge_sandbox.py."""

from sqlalchemy import select

from app.models import Problem, ProgressEvent, ProgressEventType
from tests.conftest import auth_headers, register
from tests.judge_fakes import expected_outputs, lines


def run(c, headers, code="class Solution { /* learner code */ }", slug="two-sum"):
    return c.post(
        "/api/v1/submissions",
        headers=headers,
        json={"problem_slug": slug, "source_code": code, "mode": "run"},
    )


def public_answers(c, slug="two-sum"):
    outputs, visibility = expected_outputs(c, slug)
    return [o for o, v in zip(outputs, visibility, strict=True) if v == "public"]


def test_run_judges_public_tests_only_and_hidden_inputs_never_enter_the_sandbox(judged):
    answers: list = []
    c, runner, worker, h = judged(lambda files, nonce: ("ok", lines(nonce, answers), {}))
    answers[:] = public_answers(c)
    r = run(c, h)
    assert r.status_code == 202 and r.json()["mode"] == "run"
    assert worker.process_one()

    done = c.get(f"/api/v1/submissions/{r.json()['id']}", headers=h).json()
    assert done["status"] == "PASSED" and done["mode"] == "run"
    res = done["result"]
    assert res["total_count"] == res["passed_count"] == len(answers) == 3
    assert res["hidden_total"] == 0 and res["hidden_passed"] == 0
    assert len(res["public_results"]) == 3

    driver = runner.calls[0]["files"]["Main.java"]
    assert driver.count("run(out, prefix,") == 3
    with c.app.state.session_factory() as db:
        p = db.scalar(select(Problem).where(Problem.slug == "two-sum"))
        hidden = [t.input["nums"] for t in p.test_cases if t.visibility.value == "hidden"]
    for nums in hidden:
        assert ", ".join(map(str, nums)) not in driver


def test_a_passing_run_is_not_an_attempt_or_a_solve(judged):
    answers: list = []
    c, _, worker, h = judged(lambda files, nonce: ("ok", lines(nonce, answers), {}))
    answers[:] = public_answers(c)
    sid = run(c, h).json()["id"]
    worker.process_one()

    with c.app.state.session_factory() as db:
        kinds = {e.event_type for e in db.scalars(select(ProgressEvent))}
    assert ProgressEventType.SOLVED not in kinds and ProgressEventType.SUBMITTED not in kinds
    progress = c.get("/api/v1/me/progress", headers=h).json()
    assert progress["solved"] == 0 and progress["submissions"] == 0 and progress["attempted"] == 0
    assert c.get("/api/v1/me/submissions", headers=h).json()["total"] == 0  # attempts only by default
    runs = c.get("/api/v1/me/submissions?mode=run", headers=h).json()
    assert runs["total"] == 1 and runs["items"][0]["id"] == sid and runs["items"][0]["mode"] == "run"


def test_submit_still_uses_every_test_and_counts(judged):
    answers: list = []
    c, runner, worker, h = judged(lambda files, nonce: ("ok", lines(nonce, answers), {}))
    answers[:] = expected_outputs(c, "two-sum")[0]
    r = c.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": "class S {}"}
    )
    assert r.json()["mode"] == "submit"
    worker.process_one()
    assert runner.calls[0]["files"]["Main.java"].count("run(out, prefix,") == 7
    assert c.get("/api/v1/me/progress", headers=h).json()["solved"] == 1


def test_run_is_refused_when_execution_is_disabled(client, user_headers):
    r = run(client, user_headers)
    assert r.status_code == 503 and r.json()["error"]["code"] == "execution_disabled"
    # Submitting is still accepted (saved, judged later).
    ok = client.post(
        "/api/v1/submissions",
        headers=user_headers,
        json={"problem_slug": "two-sum", "source_code": "class S {}"},
    )
    assert ok.status_code == 202


def test_runs_share_the_judge_abuse_limits(judged):
    c, _, _, h = judged(lambda files, nonce: ("ok", "", {}), max_pending_per_user=1)
    assert run(c, h).status_code == 202
    r = run(c, h)
    assert r.status_code == 429 and r.json()["error"]["code"] == "submission_pending"


def test_review_of_a_run_does_not_claim_a_full_verdict(judged):
    answers: list = []
    c, _, worker, h = judged(lambda files, nonce: ("ok", lines(nonce, answers), {}))
    answers[:] = public_answers(c)
    sid = run(c, h).json()["id"]
    worker.process_one()
    r = c.post(
        "/api/v1/ai/review",
        headers=h,
        json={"problem_slug": "two-sum", "source_code": "class Solution {}", "submission_id": sid},
    )
    assert r.status_code == 200
    assert r.json()["judge_status"] == "PASSED on public tests only (a Run; hidden tests were not executed)"


def test_a_failed_run_can_be_explained(judged):
    answers: list = []
    c, _, worker, h = judged(lambda files, nonce: ("ok", lines(nonce, answers), {}))
    answers[:] = public_answers(c)
    answers[1] = [0, 0]
    sid = run(c, h).json()["id"]
    worker.process_one()
    e = c.post("/api/v1/ai/explain-failure", headers=h, json={"submission_id": sid})
    assert e.status_code == 200 and e.json()["explanation"]["cause"] == "wrong-answer"


def test_other_users_cannot_see_your_runs(judged):
    c, _, _, h = judged(lambda files, nonce: ("ok", "", {}))
    sid = run(c, h).json()["id"]
    other = auth_headers(register(c, email="eve@example.com"))
    assert c.get(f"/api/v1/submissions/{sid}", headers=other).status_code == 404
    assert c.get("/api/v1/me/submissions?mode=run", headers=other).json()["total"] == 0


def test_export_includes_mode(judged):
    c, _, _, h = judged(lambda files, nonce: ("ok", "", {}))
    run(c, h)
    data = c.get("/api/v1/me/export", headers=h).json()
    assert [s["mode"] for s in data["submissions"]] == ["run"]


def test_capabilities_say_whether_runs_work(client, make_client):
    caps = client.get("/api/v1/capabilities").json()
    assert set(caps) == {
        "execution_enabled",
        "ai_provider",
        "execution",
        "guest_retention_days",
        "ui_telemetry",
        "answer_request_keys",  # Durable Saves brief 05: keyed answer saves are kept once
        "emails_delivered",  # false only on a development server that prints emails instead
    }
    assert caps["answer_request_keys"] is True
    assert (
        caps["execution_enabled"] is False
        and caps["ai_provider"] == "offline"
        and caps["guest_retention_days"] == 30
    )
    assert caps["execution"]["state"] == "not_configured" and caps["execution"]["submit_mode"] == "saved_only"
    enabled = make_client(execution_enabled=True, runner_token="r" * 40)
    enabled.app.state.execution_health.probe = lambda: True
    caps = enabled.get("/api/v1/capabilities").json()
    assert caps["execution_enabled"] is True and caps["execution"]["state"] == "ready"
