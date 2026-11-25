"""A guest start or registration whose reply was lost (Volume 8, prompt 6; docs/RECOVERY.md).

The browser gets an anchor first: an HttpOnly, SameSite=Strict cookie. The create stores its hash
with the account, so the same browser's retry finds that account:
- a guest is resumed by the anchor alone (it's the only thing that ties a guest to a browser);
- a registration only with the right password too, and without a second verification email.
Nothing is granted by an email, a key in page storage, or a guessed value; another browser, a
deliberate sign-out, an expired anchor, or a guest that became an account all start fresh."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.models import CreateIntent, EmailJob, User
from app.services import create_intents

GUEST = "/api/v1/auth/guest"
REGISTER = "/api/v1/auth/register"
ANCHOR = "/api/v1/auth/create-anchor"
BODY = {"email": "ada@example.com", "password": "CorrectHorse42", "display_name": "Ada"}


def users(client, **where) -> int:
    with client.app.state.session_factory() as db:
        q = select(func.count()).select_from(User)
        for k, v in where.items():
            q = q.where(getattr(User, k) == v)
        return db.scalar(q) or 0


def verification_emails(client) -> int:
    with client.app.state.session_factory() as db:
        return (
            db.scalar(select(func.count()).select_from(EmailJob).where(EmailJob.kind == "verify_email")) or 0
        )


def test_the_anchor_is_set_once_http_only_and_kept_for_a_retry(client):
    first = client.post(ANCHOR)
    assert first.status_code == 204
    cookie = first.headers["set-cookie"]
    assert (
        "cc_create=" in cookie
        and "HttpOnly" in cookie
        and "SameSite=strict" in cookie.replace("Strict", "strict")
    )
    assert "Path=/api/v1/auth" in cookie
    value = client.cookies.get("cc_create")
    again = client.post(ANCHOR)
    assert again.status_code == 204 and client.cookies.get("cc_create") == value  # kept (and renewed)
    assert value in again.headers["set-cookie"]


def test_a_lost_guest_start_sent_again_resumes_the_same_guest(client):
    client.post(ANCHOR)
    first = client.post(GUEST)
    assert first.status_code == 201
    client.cookies.delete(
        "cc_refresh", path="/api/v1/auth"
    )  # the reply, and its session cookie, never arrived
    again = client.post(GUEST)
    assert again.status_code == 200 and again.headers["X-Account-Resumed"] == "guest"
    assert again.json()["user"]["id"] == first.json()["user"]["id"]
    assert users(client, is_guest=True) == 1


def test_without_an_anchor_every_start_is_a_new_guest_as_before(client):
    assert client.post(GUEST).status_code == 201
    client.cookies.clear()
    assert client.post(GUEST).status_code == 201
    assert users(client, is_guest=True) == 2


def test_another_browser_a_guessed_anchor_or_a_sign_out_never_resumes_it(client, make_client):
    client.post(ANCHOR)
    first = client.post(GUEST).json()
    # Another browser: its own anchor, its own guest.
    other = make_client()
    other.post(ANCHOR)
    assert other.post(GUEST).json()["user"]["id"] != first["user"]["id"]
    # A value made up by anyone else is just an unknown anchor: a new guest. Too short to be one
    # of ours: ignored. (Each in a browser of its own.)
    for made_up in ("x" * 43, "short"):
        stranger = make_client()
        stranger.cookies.set("cc_create", made_up)
        r = stranger.post(GUEST)
        assert r.status_code == 201 and r.json()["user"]["id"] != first["user"]["id"]
    # A deliberate sign-out forgets it on the server, even if the cookie's removal never reached
    # the browser (the old anchor is sent again): the next start here is a new guest.
    anchor = client.cookies.get("cc_create")
    h = {"Authorization": f"Bearer {first['access_token']}"}
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 204
    assert client.cookies.get("cc_create") is None  # and the browser is told to drop it
    client.cookies.set("cc_create", anchor, path="/api/v1/auth")
    assert client.post(GUEST).json()["user"]["id"] != first["user"]["id"]


def test_an_expired_anchor_or_a_guest_that_became_an_account_starts_fresh(client):
    client.post(ANCHOR)
    first = client.post(GUEST).json()
    with client.app.state.session_factory() as db:
        old = datetime.now(UTC) - timedelta(minutes=create_intents.CREATE_INTENT_MINUTES + 1)
        db.execute(update(CreateIntent).values(created_at=old))
        db.commit()
    second = client.post(GUEST).json()
    assert second["user"]["id"] != first["user"]["id"]  # expired: a new guest
    # That guest becomes an account; a guest start from this browser now never returns it.
    h = {"Authorization": f"Bearer {second['access_token']}"}
    up = client.post("/api/v1/auth/upgrade", headers=h, json=BODY)
    assert up.status_code in (200, 201), up.text
    third = client.post(GUEST).json()
    assert third["user"]["id"] != second["user"]["id"] and third["user"]["is_guest"] is True


def test_a_lost_registration_sent_again_signs_in_once_and_sends_no_second_email(client):
    client.post(ANCHOR)
    first = client.post(REGISTER, json=BODY)
    assert first.status_code == 201 and verification_emails(client) == 1
    client.cookies.delete("cc_refresh", path="/api/v1/auth")
    again = client.post(REGISTER, json=BODY)
    assert again.status_code == 200 and again.headers["X-Account-Resumed"] == "register"
    assert again.json()["user"]["id"] == first.json()["user"]["id"]
    assert verification_emails(client) == 1 and users(client, is_guest=False) == 1


def test_a_registration_retry_without_proof_is_the_usual_answer(client, make_client):
    client.post(ANCHOR)
    client.post(REGISTER, json=BODY)
    # The same browser with another password: no session, the same answer as before this change.
    wrong = client.post(REGISTER, json={**BODY, "password": "WrongHorse99"})
    assert wrong.status_code == 409 and wrong.json()["error"]["code"] == "email_taken"
    assert "access_token" not in wrong.text
    # Another browser with the right password: also the usual answer (signing in is the way).
    other = make_client()
    other.post(ANCHOR)
    r = other.post(REGISTER, json=BODY)
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    assert (
        other.post(
            "/api/v1/auth/login", json={"email": BODY["email"], "password": BODY["password"]}
        ).status_code
        == 200
    )


def test_signing_out_everywhere_ends_resuming_too(client):
    client.post(ANCHOR)
    first = client.post(GUEST).json()
    h = {"Authorization": f"Bearer {first['access_token']}"}
    assert client.post("/api/v1/auth/logout-all", headers=h).status_code == 204
    assert client.post(GUEST).json()["user"]["id"] != first["user"]["id"]


def test_two_tabs_starting_at_once_get_one_guest(client):
    # Two tabs of one browser share its anchor: the second start finds the first's guest.
    client.post(ANCHOR)
    a = client.post(GUEST)
    b = client.post(GUEST)
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.json()["user"]["id"] == b.json()["user"]["id"] and users(client, is_guest=True) == 1


def test_intents_are_purged_after_an_hour(client):
    client.post(ANCHOR)
    client.post(GUEST)
    with client.app.state.session_factory() as db:
        assert create_intents.purge(db) == 0
        db.execute(update(CreateIntent).values(created_at=datetime.now(UTC) - timedelta(hours=2)))
        db.commit()
        assert create_intents.purge(db) == 1
        db.commit()
