from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models import Submission, SubmissionStatus, User
from app.services.progress import ProgressService, _streaks


def test_streaks():
    today = date(2026, 11, 10)
    days = {today - timedelta(days=i) for i in range(3)} | {date(2026, 10, 1), date(2026, 10, 2)}
    assert _streaks(days, today) == (3, 3)
    assert _streaks({today - timedelta(days=1)}, today) == (1, 1)  # yesterday still counts
    assert _streaks({today - timedelta(days=2)}, today) == (0, 1)
    assert _streaks(set(), today) == (0, 0)


def test_empty_progress(client, user_headers):
    p = client.get("/api/v1/me/progress", headers=user_headers).json()
    assert p["solved"] == 0 and p["attempted"] == 0 and p["total_problems"] >= 10
    assert p["acceptance_rate"] is None and p["current_streak_days"] == 0
    assert len(p["activity"]) == 28
    assert {r["difficulty"] for r in p["by_difficulty"]} >= {"easy", "medium"}


def test_progress_reflects_activity(client, user_headers):
    client.get("/api/v1/problems/two-sum", headers=user_headers)
    client.post(
        "/api/v1/submissions",
        headers=user_headers,
        json={"problem_slug": "two-sum", "source_code": "class Solution {}"},
    )
    client.post(
        "/api/v1/ai/hint",
        headers=user_headers,
        json={"problem_slug": "two-sum", "level": 1, "source_code": ""},
    )
    p = client.get("/api/v1/me/progress", headers=user_headers).json()
    assert p["attempted"] == 1 and p["submissions"] == 1 and p["hints_used"] == 1
    assert p["current_streak_days"] == 1
    status = {s["slug"]: s for s in p["problems"]}
    assert status["two-sum"]["status"] == "attempted"
    assert status["two-sum"]["last_submission_status"] == "QUEUED"
    assert "hash-maps" in p["weakest_topics"] or "arrays" in p["weakest_topics"]


def test_solved_problems_and_recommendations(client, user_headers):
    for slug in ["find-largest-number", "two-sum"]:
        client.post(
            "/api/v1/submissions", headers=user_headers, json={"problem_slug": slug, "source_code": "x"}
        )
    # Simulate the (future) judge marking one submission as passed.
    with client.app.state.session_factory() as db:
        sub = db.scalar(
            select(Submission)
            .join(Submission.problem)
            .where(Submission.problem.has(slug="find-largest-number"))
        )
        sub.status = SubmissionStatus.PASSED
        db.commit()
    p = client.get("/api/v1/me/progress", headers=user_headers).json()
    assert p["solved"] == 1 and p["accepted_submissions"] == 1 and p["acceptance_rate"] == 1.0
    recs = client.get("/api/v1/me/recommendations", headers=user_headers, params={"limit": 4}).json()
    assert recs[0]["slug"] == "two-sum" and recs[0]["kind"] == "retry"
    assert "find-largest-number" not in [r["slug"] for r in recs]
    assert all(r["reason"] for r in recs) and len(recs) == 4


def test_new_user_recommendations_start_easy(client, user_headers):
    recs = client.get("/api/v1/me/recommendations", headers=user_headers).json()
    assert recs and all(r["difficulty"] == "easy" for r in recs[:3])
    assert all(r["kind"] == "next_step" for r in recs)


def test_service_progress_is_timezone_safe(client, user_headers):
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User))
        out = ProgressService(db).progress(user, now=datetime(2030, 1, 1, tzinfo=UTC))
        assert out.current_streak_days == 0
