from sqlalchemy import func, select

from app.models import (
    AIInteraction,
    ExecutionResult,
    InterviewTurn,
    PracticeSession,
    ProgressEvent,
    Submission,
    User,
)
from tests.conftest import auth_headers, register


def make_activity(client, headers):
    client.post(
        "/api/v1/submissions",
        headers=headers,
        json={"problem_slug": "two-sum", "source_code": "class Solution {}"},
    )
    client.post("/api/v1/ai/hint", headers=headers, json={"problem_slug": "two-sum", "level": 1})
    iv = client.post("/api/v1/interviews", headers=headers, json={"problem_slug": "two-sum"}).json()
    client.post(
        f"/api/v1/interviews/{iv['id']}/messages", headers=headers, json={"message": "Can it be empty?"}
    )


def counts(client, user_id):
    with client.app.state.session_factory() as db:
        return {
            "users": db.scalar(select(func.count()).select_from(User).where(User.id == user_id)),
            "submissions": db.scalar(
                select(func.count()).select_from(Submission).where(Submission.user_id == user_id)
            ),
            "ai": db.scalar(
                select(func.count()).select_from(AIInteraction).where(AIInteraction.user_id == user_id)
            ),
            "sessions": db.scalar(
                select(func.count()).select_from(PracticeSession).where(PracticeSession.user_id == user_id)
            ),
            "events": db.scalar(
                select(func.count()).select_from(ProgressEvent).where(ProgressEvent.user_id == user_id)
            ),
            "turns": db.scalar(
                select(func.count())
                .select_from(InterviewTurn)
                .join(PracticeSession)
                .where(PracticeSession.user_id == user_id)
            ),
        }


def test_update_display_name(client, user_headers):
    r = client.patch("/api/v1/auth/me", headers=user_headers, json={"display_name": "  Grace  "})
    assert r.status_code == 200 and r.json()["display_name"] == "Grace"
    assert (
        client.patch("/api/v1/auth/me", headers=user_headers, json={"display_name": "x" * 41}).status_code
        == 422
    )


def test_delete_requires_confirmation_and_password(client):
    tokens = register(client, email="del@example.com", password="CorrectHorse42")
    h = auth_headers(tokens)
    no_confirm = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "yes"}
    )
    assert no_confirm.status_code == 400 and no_confirm.json()["error"]["code"] == "confirmation_required"
    wrong = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "Nope12345A", "confirm": "DELETE"}
    )
    assert wrong.status_code == 401
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200  # still there


def test_delete_removes_every_row_and_nothing_else(client):
    me = register(client, email="gone@example.com", password="CorrectHorse42")
    other = register(client, email="stays@example.com", password="CorrectHorse42")
    make_activity(client, auth_headers(me))
    make_activity(client, auth_headers(other))
    before = counts(client, me["user"]["id"])
    assert all(v > 0 for v in before.values()), before

    r = client.request(
        "DELETE",
        "/api/v1/auth/me",
        headers=auth_headers(me),
        json={"password": "CorrectHorse42", "confirm": "DELETE"},
    )
    assert r.status_code == 204
    assert set(counts(client, me["user"]["id"]).values()) == {0}
    assert all(v > 0 for v in counts(client, other["user"]["id"]).values())
    # The old token no longer works, and the email can be registered again.
    assert client.get("/api/v1/auth/me", headers=auth_headers(me)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "gone@example.com", "password": "CorrectHorse42"}
        ).status_code
        == 401
    )
    register(client, email="gone@example.com", password="CorrectHorse42")


def test_delete_cascades_execution_results(client):
    me = register(client, email="res@example.com")
    h = auth_headers(me)
    sub = client.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": "class Solution {}"}
    ).json()
    with client.app.state.session_factory() as db:
        db.add(ExecutionResult(submission_id=sub["id"], passed_count=0, total_count=7, public_results=[]))
        db.commit()
    client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ExecutionResult)) == 0


def test_guests_can_delete_without_a_password(client):
    guest = client.post("/api/v1/auth/guest").json()
    r = client.request("DELETE", "/api/v1/auth/me", headers=auth_headers(guest), json={"confirm": "DELETE"})
    assert r.status_code == 204


def test_export_contains_everything_but_credentials(client):
    me = register(client, email="export@example.com", display_name="Ada")
    h = auth_headers(me)
    make_activity(client, h)
    other = auth_headers(register(client, email="private@example.com"))
    client.post(
        "/api/v1/submissions",
        headers=other,
        json={"problem_slug": "binary-search", "source_code": "class Solution { /* not mine */ }"},
    )

    r = client.get("/api/v1/me/export", headers=h)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    data = r.json()
    assert data["profile"]["email"] == "export@example.com" and data["profile"]["display_name"] == "Ada"
    assert len(data["submissions"]) == 1 and data["submissions"][0]["problem"] == "two-sum"
    assert data["ai_feedback"][0]["action"] == "hint" and data["ai_feedback"][0]["response"]["hint"]
    assert data["interviews"][0]["transcript"][1]["content"] == "Can it be empty?"
    assert {e["type"] for e in data["activity"]} >= {"submitted", "hint_used"}
    raw = r.text
    assert "password" not in raw.lower() and "token_version" not in raw and "not mine" not in raw


def test_export_requires_auth(client):
    assert client.get("/api/v1/me/export").status_code == 401
