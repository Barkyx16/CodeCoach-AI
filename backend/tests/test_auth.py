from datetime import timedelta

from app.services.auth import decode_access_token, issue_access_token
from tests.conftest import auth_headers, register


def test_register_returns_token_and_user(client):
    body = register(client, email="Grace@Example.com")
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "grace@example.com"  # normalized
    assert body["user"]["is_guest"] is False
    assert "password" not in str(body).lower().replace("password_hash", "")


def test_duplicate_email_is_rejected_case_insensitively(client):
    register(client, email="a@example.com")
    r = client.post("/api/v1/auth/register", json={"email": "A@EXAMPLE.com", "password": "CorrectHorse42"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_weak_passwords_are_rejected(client):
    for pw in ["short1A", "alllowercase123", "ALLUPPERCASE123", "NoDigitsHereAtAll"]:
        r = client.post("/api/v1/auth/register", json={"email": "x@example.com", "password": pw})
        assert r.status_code == 422, pw


def test_login_success_and_generic_failure(client):
    register(client, email="b@example.com", password="CorrectHorse42")
    ok = client.post("/api/v1/auth/login", json={"email": "B@example.com", "password": "CorrectHorse42"})
    assert ok.status_code == 200
    wrong_pw = client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "Nope12345A"})
    no_user = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "Nope12345A"})
    assert wrong_pw.status_code == no_user.status_code == 401
    # Same message either way: no account enumeration.
    assert wrong_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


def test_me_requires_valid_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    bad = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_token"
    assert bad.headers["WWW-Authenticate"] == "Bearer"


def test_logout_revokes_existing_tokens(client):
    headers = auth_headers(register(client))
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_change_password_rotates_tokens(client):
    tokens = register(client, email="c@example.com", password="CorrectHorse42")
    old = auth_headers(tokens)
    r = client.post(
        "/api/v1/auth/password",
        headers=old,
        json={"current_password": "CorrectHorse42", "new_password": "BatteryStaple99"},
    )
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=old).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth_headers(r.json())).status_code == 200
    login = client.post("/api/v1/auth/login", json={"email": "c@example.com", "password": "BatteryStaple99"})
    assert login.status_code == 200


def test_guest_session(client):
    r = client.post("/api/v1/auth/guest", json={"display_name": "Visitor"})
    assert r.status_code == 201
    me = client.get("/api/v1/auth/me", headers=auth_headers(r.json())).json()
    assert me["is_guest"] is True and me["email"] is None and me["display_name"] == "Visitor"


def test_guest_can_be_disabled(make_client):
    c = make_client(allow_guest_sessions=False)
    assert c.post("/api/v1/auth/guest").json()["error"]["code"] == "guest_disabled"


def test_auth_rate_limit(make_client):
    c = make_client(auth_rate_limit_per_minute=3)
    codes = [
        c.post("/api/v1/auth/login", json={"email": "z@example.com", "password": "x"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


def test_tokens_signed_with_other_secret_or_expired_are_rejected():
    secret = "a" * 40
    token, _ = issue_access_token("b" * 40, user_id="u1", token_version=0, ttl=timedelta(minutes=5))
    assert decode_access_token(secret, token) is None
    expired, _ = issue_access_token(secret, user_id="u1", token_version=0, ttl=timedelta(seconds=-1))
    assert decode_access_token(secret, expired) is None
    good, _ = issue_access_token(secret, user_id="u1", token_version=3, ttl=timedelta(minutes=5))
    assert decode_access_token(secret, good)["ver"] == 3
