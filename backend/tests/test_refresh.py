"""Refresh-token sessions: HttpOnly cookie, rotation, reuse detection, CSRF guard, revocation."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import RefreshToken
from app.services import refresh as refresh_tokens
from tests.conftest import register

REFRESH = "/api/v1/auth/refresh"
H = {"X-Requested-With": "codecoach"}


def cookie(client) -> str | None:
    return client.cookies.get("cc_refresh")


def refresh(client, **kw):
    return client.post(REFRESH, headers={**H, **kw.pop("headers", {})}, **kw)


def use_cookie(client, value: str) -> None:
    client.cookies.clear()
    client.cookies.set("cc_refresh", value, path="/api/v1/auth")


def test_sign_in_sets_a_locked_down_cookie_and_a_short_access_token(client):
    r = client.post("/api/v1/auth/register", json={"email": "ada@example.com", "password": "CorrectHorse42"})
    set_cookie = r.headers["set-cookie"].lower()
    assert "cc_refresh=" in set_cookie and "httponly" in set_cookie and "samesite=strict" in set_cookie
    assert "path=/api/v1/auth" in set_cookie
    assert "cc_refresh" not in r.text  # never in the body: page scripts can't get at it
    ttl = datetime.fromisoformat(r.json()["expires_at"]) - datetime.now(UTC)
    assert timedelta(minutes=14) < ttl <= timedelta(minutes=15)


def test_refresh_rotates_and_the_new_access_token_works(client):
    register(client)
    first = cookie(client)
    r = refresh(client)
    assert r.status_code == 200, r.text
    assert cookie(client) and cookie(client) != first  # rotated
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "ada@example.com"
    assert refresh(client).status_code == 200  # and the rotated one works in turn


def test_only_hashes_are_stored(client):
    register(client)
    raw = cookie(client)
    with client.app.state.session_factory() as db:
        hashes = db.scalars(select(RefreshToken.token_hash)).all()
    assert raw not in hashes and all(len(h) == 64 for h in hashes)


def test_refresh_requires_the_app_header_and_a_known_origin(client):
    register(client)
    r = client.post(REFRESH)  # no custom header: a plain cross-site form/fetch can't add it
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_rejected"
    r = refresh(client, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert refresh(client, headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_missing_or_garbage_cookie_is_401(client):
    assert refresh(client).json()["error"]["code"] == "invalid_refresh"
    use_cookie(client, "not-a-real-token")
    r = refresh(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_refresh"
    assert 'cc_refresh=""' in r.headers.get("set-cookie", "")  # told to forget it


def test_two_tabs_refreshing_at_once_is_a_retryable_race(client):
    register(client)
    old = cookie(client)
    assert refresh(client).status_code == 200  # tab A
    new = cookie(client)
    use_cookie(client, old)
    r = refresh(client)  # tab B, same old cookie, a moment later
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_race"
    assert "set-cookie" not in r.headers  # tab B's browser keeps the cookie tab A just received
    use_cookie(client, new)
    assert refresh(client).status_code == 200  # the session survived


def test_reusing_a_rotated_token_later_revokes_the_whole_family(client, monkeypatch):
    register(client)
    stolen = cookie(client)
    assert refresh(client).status_code == 200
    legit = cookie(client)
    monkeypatch.setattr(refresh_tokens, "RACE_GRACE", timedelta(0))  # well after the race window
    use_cookie(client, stolen)
    r = refresh(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_reused"
    use_cookie(client, legit)
    assert refresh(client).json()["error"]["code"] == "invalid_refresh"  # the thief's copy killed it


def test_expired_refresh_token_is_rejected(client):
    register(client)
    with client.app.state.session_factory() as db:
        for row in db.scalars(select(RefreshToken)):
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert refresh(client).json()["error"]["code"] == "invalid_refresh"


def _two_devices(client):
    """Sign in twice: two independent refresh-token families (say, laptop and phone)."""
    register(client)
    laptop = cookie(client)
    login = {"email": "ada@example.com", "password": "CorrectHorse42"}
    phone_token = client.post("/api/v1/auth/login", json=login).json()["access_token"]
    phone = cookie(client)
    return laptop, phone, phone_token


def test_logout_signs_out_only_this_device(client):
    laptop, phone, phone_token = _two_devices(client)
    r = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {phone_token}"})
    assert r.status_code == 204 and 'cc_refresh=""' in r.headers["set-cookie"]
    use_cookie(client, phone)
    assert refresh(client).status_code == 401  # this device is signed out
    use_cookie(client, laptop)
    assert refresh(client).status_code == 200  # the other device isn't


def test_logout_all_ends_every_session(client):
    laptop, phone, phone_token = _two_devices(client)
    r = client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {phone_token}"})
    assert r.status_code == 204
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {phone_token}"}).status_code == 401
    )
    for device in (laptop, phone):
        use_cookie(client, device)
        assert refresh(client).status_code == 401


def test_password_change_keeps_this_session_and_ends_the_others(client):
    tokens = register(client)
    other_device = cookie(client)
    r = client.post(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": "CorrectHorse42", "new_password": "BatteryStaple99"},
    )
    assert r.status_code == 200
    this_device = cookie(client)
    assert this_device != other_device
    assert refresh(client).status_code == 200
    use_cookie(client, other_device)
    assert refresh(client).status_code == 401


def test_deleting_the_account_removes_its_refresh_tokens(client):
    tokens = register(client)
    raw = cookie(client)
    r = client.request(
        "DELETE",
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"password": "CorrectHorse42", "confirm": "DELETE"},
    )
    assert r.status_code == 204 and 'cc_refresh=""' in r.headers["set-cookie"]
    with client.app.state.session_factory() as db:
        assert db.scalar(select(RefreshToken)) is None
    use_cookie(client, raw)
    assert refresh(client).status_code == 401


def test_guest_sessions_get_a_refresh_cookie_too(client):
    assert client.post("/api/v1/auth/guest").status_code == 201
    assert cookie(client)
    assert refresh(client).json()["user"]["is_guest"] is True


def test_cors_allows_credentials_for_listed_origins_only(client):
    ok = client.options(
        REFRESH,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-requested-with",
        },
    )
    assert ok.headers.get("access-control-allow-credentials") == "true"
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options(
        REFRESH, headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert bad.headers.get("access-control-allow-origin") is None


def test_production_refuses_insecure_cookies(make_settings):
    import pytest

    base = {
        "environment": "production",
        "secret_key": "x" * 48,
        "cors_origins": ["https://app.example"],
        "email_backend": "smtp",
        "smtp_host": "smtp.example.com",
        "app_base_url": "https://app.example",
    }
    assert make_settings(**base).cookie_secure is True
    with pytest.raises(ValueError, match="REFRESH_COOKIE_SECURE"):
        make_settings(**base, refresh_cookie_secure=False)


def test_expired_rows_are_pruned_but_used_ones_are_kept_for_reuse_detection(client):
    register(client)
    assert refresh(client).status_code == 200  # one used row + one live row
    with client.app.state.session_factory() as db:
        old = db.scalars(select(RefreshToken).where(RefreshToken.used_at.is_not(None))).one()
        old.expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    assert refresh(client).status_code == 200  # issuing a new token prunes the expired row
    with client.app.state.session_factory() as db:
        rows = db.scalars(select(RefreshToken)).all()
    assert len(rows) == 2 and all(r.used_at is None or r.expires_at > datetime.now(UTC) for r in rows)
