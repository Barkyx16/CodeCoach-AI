"""Coding practice where it was planned (Volume 14, prompt 2; docs/ACCEPTED_ACTIONS.md, docs/PLAN_UPDATES.md):
an improvement accepted from a coding interview lists the judged submissions of that interview's
problem made since it was accepted; judged submissions count as new evidence for the plan; a target
requirement shows the latest judged submissions to the problems it offers. Stored links only.
Verdicts are written as the worker writes them (the judge isn't run here). Synthetic data only."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.models import (
    AcceptedAction,
    ExecutionResult,
    Problem,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    User,
)
from tests.conftest import auth_headers, register
from tests.test_submission_comparisons import BETTER, CODE, judge

TRACK = "software-engineer"
JD = """Software Engineer
Requirements:
- Strong knowledge of data structures and algorithms
"""


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=TRACK))


def submit(client, h, code=CODE, slug="two-sum"):
    r = client.post("/api/v1/submissions", headers=h, json={"problem_slug": slug, "source_code": code})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def accepted(client, h, slug="two-sum"):
    """An improvement accepted from a finished coding interview on ``slug``."""
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "coding", "problem_slug": slug, "duration_minutes": 15}
    )
    assert iv.status_code in (200, 201), iv.text
    iv_id = iv.json()["id"]
    assert (
        client.post(f"/api/v1/interviews/{iv_id}/finish", headers=h, json={"code": CODE}).status_code == 200
    )
    imp = client.get(f"/api/v1/interviews/{iv_id}/review", headers=h).json()["improvements"][0]
    r = client.post(
        "/api/v1/me/actions",
        headers=h,
        json={
            "source": {"kind": "interview_improvement", "interview_id": iv_id, "key": imp["key"]},
            "recurrence": "weekly",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def practice(client, h, action_id):
    r = client.get(f"/api/v1/me/actions/{action_id}/practice", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def backdate(client, action_id, seconds=60):
    """The action accepted a little earlier (submissions made in the same instant are ordered by id)."""
    with client.app.state.session_factory() as db:
        a = db.get(AcceptedAction, action_id)
        db.execute(
            update(AcceptedAction)
            .where(AcceptedAction.id == action_id)
            .values(created_at=a.created_at - timedelta(seconds=seconds))
        )
        db.commit()


def test_a_coding_interviews_improvement_lists_judged_submissions_since_it_was_accepted(client):
    h = coder(client)
    before = submit(client, h)
    judge(client, before, SubmissionStatus.FAILED, 2)
    with client.app.state.session_factory() as db:  # made well before the improvement was accepted
        db.execute(
            update(Submission)
            .where(Submission.id == before)
            .values(created_at=datetime.now(UTC) - timedelta(hours=1))
        )
        db.commit()
    action = accepted(client, h)
    after = submit(client, h, BETTER)
    judge(client, after, SubmissionStatus.PASSED, 7)

    p = practice(client, h, action)
    assert p["linked"] and p["count"] == 1 and p["items"] == []
    assert p["note"].startswith("Submissions of the interview's problem since you accepted this")
    [item] = p["submissions"]
    assert item["submission_id"] == after and item["status"] == "PASSED"
    assert (item["passed_count"], item["total_count"]) == (7, 7)
    assert item["href"] == f"/history/submissions/{after}"
    assert item["conditions"]["labels"] == ["No in-app help recorded"]
    # Compared with the submission before it, by the one rule (Volume 14, prompt 1).
    assert item["compared"]["previous"]["id"] == before
    assert item["compared"]["comparison"]["outcome"] == "comparable"
    # Nothing ticks the action or says it worked.
    a = client.get(f"/api/v1/me/actions/{action}", headers=h).json()
    assert a["status"] != "done" and all(o["completed_at"] is None for o in a["occurrences"])
    for claim in ("it worked", "improved", "better than", "helped you"):
        assert claim not in str(p).lower()


def test_a_run_an_unjudged_attempt_and_another_problem_are_not_its_practice(client):
    h = coder(client)
    action = accepted(client, h)
    backdate(client, action)
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        run = Submission(
            user_id=user.id, problem_id=pid, source_code=CODE, mode=SubmissionMode.RUN, content_version=1
        )
        db.add(run)
        db.commit()
        run_id = run.id
    judge(client, run_id, SubmissionStatus.PASSED, 3, 3)
    broken = submit(client, h)
    judge(client, broken, SubmissionStatus.INTERNAL_ERROR)
    other = submit(client, h, slug="find-largest-number")
    judge(client, other, SubmissionStatus.PASSED, 5, 5)
    waiting = submit(client, h, BETTER)  # still queued: not judged yet
    p = practice(client, h, action)
    assert p["linked"] and p["submissions"] == [] and p["count"] == 0
    assert waiting not in str(p)


def test_another_accounts_submissions_are_never_its_practice_and_a_deleted_one_drops_out(client):
    theirs = coder(client, email="other@example.com")
    mine = coder(client)
    action = accepted(client, mine)
    backdate(client, action)
    t = submit(client, theirs)
    judge(client, t, SubmissionStatus.PASSED, 7)
    m = submit(client, mine)
    judge(client, m, SubmissionStatus.FAILED, 2)
    assert [s["submission_id"] for s in practice(client, mine, action)["submissions"]] == [m]
    with client.app.state.session_factory() as db:
        db.execute(delete(ExecutionResult).where(ExecutionResult.submission_id == m))
        db.execute(delete(Submission).where(Submission.id == m))
        db.commit()
    assert practice(client, mine, action)["submissions"] == []
    assert client.get(f"/api/v1/me/actions/{action}/practice", headers=theirs).status_code == 404


def test_the_export_carries_the_links_by_id(client):
    h = coder(client)
    action = accepted(client, h)
    backdate(client, action)
    sid = submit(client, h)
    judge(client, sid, SubmissionStatus.FAILED, 2)
    v2 = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    [entry] = [a for a in v2["accepted_actions"] if a["id"] == action]
    assert entry["related_submissions"] == [sid] and entry["related_attempts"] == []
    v1 = client.get("/api/v1/me/export", headers=h).json()
    assert v1["accepted_actions"][0]["related_practice"] == 1


def test_judged_submissions_are_new_evidence_for_the_plan(client):
    h = coder(client)
    p = client.get("/api/v1/me/plan", headers=h).json()
    assert p["version"] == 1 and p["news"] is None
    sid = submit(client, h)
    judge(client, sid, SubmissionStatus.FAILED, 2)
    news = client.get("/api/v1/me/plan", headers=h).json()["news"]
    assert news is not None, "a failed submission is unfinished business the planner would use"
    assert news["submissions"] == 1 and news["not_passed"] == 1
    assert news["text"] == "1 submission (not passed) since this plan."
    entry = next(e for e in news["entries"] if e["kind"] == "submission")
    assert entry == {
        "kind": "submission",
        "title": "Two Sum",
        "score": None,
        "verdict": "not passed",
        "href": f"/history/submissions/{sid}",
    }
    # A run (public tests only) isn't evidence.
    with client.app.state.session_factory() as db:
        db.execute(update(Submission).where(Submission.id == sid).values(mode=SubmissionMode.RUN))
        db.commit()
    assert client.get("/api/v1/me/plan", headers=h).json()["news"] is None
    with client.app.state.session_factory() as db:
        db.execute(update(Submission).where(Submission.id == sid).values(mode=SubmissionMode.SUBMIT))
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        run = Submission(
            user_id=user.id, problem_id=pid, source_code=CODE, mode=SubmissionMode.RUN, content_version=1
        )
        db.add(run)
        db.commit()
        run_id = run.id
    judge(client, run_id, SubmissionStatus.FAILED, 1, 3)
    news = client.get("/api/v1/me/plan", headers=h).json()["news"]
    assert news["submissions"] == 1 and [e["href"] for e in news["entries"]] == [
        f"/history/submissions/{sid}"
    ]
    # Updating uses it, and says so.
    r = client.post("/api/v1/me/plan/update", headers=h, json={"version": 1})
    assert r.status_code == 200, r.text
    v2 = r.json()
    assert v2["version"] == 2
    assert "Updated when you asked: 1 submission (not passed) since version 1." in v2["changes"]


def test_a_target_requirement_shows_the_latest_judged_submissions_to_its_problems(client):
    h = coder(client)
    t = client.post(
        "/api/v1/targets", headers=h, json={"title": "Backend engineer", "description": JD}
    ).json()
    req = next(
        r for r in t["requirement_list"] if r["text"] == "Strong knowledge of data structures and algorithms"
    )
    assert req["submissions"] == []
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    waiting = submit(client, h, BETTER + " ")
    t = client.get(f"/api/v1/targets/{t['id']}", headers=h).json()
    req = next(
        r for r in t["requirement_list"] if r["text"] == "Strong knowledge of data structures and algorithms"
    )
    assert [(s["submission_id"], s["status"]) for s in req["submissions"]] == [
        (second, "PASSED"),
        (first, "FAILED"),
    ]
    assert waiting not in str(req["submissions"])
    assert all(
        s["problem_title"] == "Two Sum" and s["href"].startswith("/history/submissions/")
        for s in req["submissions"]
    )
    # Passed, Two Sum leaves the practice links; its attempts are still listed.
    assert "Problem: Two Sum" not in [
        f"Problem: {p['title']}" for p in req["practice"] if p["kind"] == "problem"
    ]


def test_news_wording_counts_without_claiming_anything():
    from app.services.roadmap import news_text

    assert news_text(0, 0, 0, 0, "this plan", 1, 0) == "1 submission (passed) since this plan."
    assert news_text(0, 0, 0, 0, "this plan", 3, 2) == "3 submissions (2 not passed) since this plan."
    assert news_text(0, 0, 0, 0, "this plan", 2, 0) == "2 submissions (both passed) since this plan."
    assert (
        news_text(2, 0, 1, 0, "this plan", 2, 2)
        == "2 answers and 2 submissions (neither passed) since this plan, 1 answer below 70."
    )
    assert (
        news_text(1, 0, 1, 1, "this plan", 1, 1)
        == "1 answer, 1 finished round and 1 submission (not passed) since this plan, the answer below 70."
    )
    assert (
        news_text(2, 0, 1, 0, "this plan") == "2 answers since this plan, one below 70."
    )  # unchanged without submissions
