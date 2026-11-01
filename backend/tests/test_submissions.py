from app.services.judge.backends import EXECUTION_DISABLED_DETAIL
from tests.conftest import auth_headers, register

CODE = "class Solution { public int max(int[] nums) { return nums[0]; } }"


def submit(client, headers, slug="find-largest-number", code=CODE):
    return client.post(
        "/api/v1/submissions", headers=headers, json={"problem_slug": slug, "source_code": code}
    )


def test_submission_requires_auth(client):
    assert submit(client, {}).status_code == 401


def test_submission_is_queued_not_executed(client, user_headers):
    r = submit(client, user_headers)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "QUEUED" and body["is_terminal"] is False
    assert body["execution_enabled"] is False
    assert body["status_detail"] == EXECUTION_DISABLED_DETAIL
    assert body["result"] is None
    polled = client.get(f"/api/v1/submissions/{body['id']}", headers=user_headers).json()
    assert polled["id"] == body["id"] and polled["source_code"] == CODE


def test_other_users_cannot_read_submissions(client, user_headers):
    sub_id = submit(client, user_headers).json()["id"]
    intruder = auth_headers(register(client, email="eve@example.com"))
    r = client.get(f"/api/v1/submissions/{sub_id}", headers=intruder)
    assert r.status_code == 404  # not 403: don't confirm the id exists
    listing = client.get("/api/v1/me/submissions", headers=intruder).json()
    assert listing["total"] == 0


def test_submission_validation(client, user_headers):
    assert submit(client, user_headers, code="   \n").status_code == 422
    assert submit(client, user_headers, slug="nope").status_code == 404
    r = client.post(
        "/api/v1/submissions",
        headers=user_headers,
        json={"problem_slug": "two-sum", "source_code": "x", "language": "python"},
    )
    assert r.status_code == 422


def test_source_size_limit(make_client):
    c = make_client(max_source_chars=100)
    headers = auth_headers(register(c))
    r = submit(c, headers, code="x" * 101)
    assert r.status_code == 400 and r.json()["error"]["code"] == "payload_too_large"


def test_attempt_history(client, user_headers):
    for slug in ["two-sum", "two-sum", "binary-search"]:
        assert submit(client, user_headers, slug=slug).status_code == 202
    hist = client.get("/api/v1/me/submissions", headers=user_headers).json()
    assert hist["total"] == 3
    assert hist["items"][0]["problem_slug"] == "binary-search"  # newest first
    assert set(hist["items"][0]) >= {
        "id",
        "problem_slug",
        "problem_title",
        "status",
        "created_at",
        "duration_ms",
    }
    only = client.get(
        "/api/v1/me/submissions", headers=user_headers, params={"problem_slug": "two-sum"}
    ).json()
    assert only["total"] == 2
    queued = client.get("/api/v1/me/submissions", headers=user_headers, params={"status": "QUEUED"}).json()
    assert queued["total"] == 3


def test_timestamps_are_timezone_aware(client, user_headers):
    """Regression: SQLite used to return naive datetimes (no offset) in API responses."""
    body = submit(client, user_headers).json()
    for field in ("created_at", "updated_at"):
        assert body[field].endswith("Z") or body[field].endswith("+00:00"), body[field]
    listed = client.get("/api/v1/me/submissions", headers=user_headers).json()["items"][0]
    assert listed["created_at"].endswith("Z") or listed["created_at"].endswith("+00:00")
