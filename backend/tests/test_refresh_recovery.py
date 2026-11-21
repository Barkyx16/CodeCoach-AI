"""A refresh whose response never reaches the browser must not sign the user out.

The failure these tests pin down (they fail on the code before the fix): the server rotates the
refresh cookie C1 -> C2, but the browser never receives the response (reload, closed tab, dropped
connection), so it still holds C1, which the server has already marked as used. Presenting C1
again then gave `refresh_race` for 30 seconds (the client gave up after one retry and signed the
user out) and `refresh_reused` afterwards (which revoked the whole session).

The recovery: each refresh attempt carries a random per-attempt key (`X-Refresh-Attempt`) that the
client keeps until it learns the outcome. The successor token is derived from the presented token
and that key with a server-side HMAC, so the same (token, key) pair can be replayed for a short,
bounded window and gets back the *same* successor, never a new one, and only while that successor
is unused, unrevoked, unexpired and the account's sessions haven't been ended. Everything else
keeps the old rules: a different or missing key is a race and then reuse; reuse revokes the family.
"""

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from app.models import RefreshToken
from app.services import refresh as refresh_tokens
from tests.conftest import TEST_DATABASE_URL, register
from tests.test_refresh import REFRESH, H, cookie, refresh, use_cookie

KEY = "k" * 22 + "AbC-_0123456789"  # 37 url-safe characters, like the client's random keys
OTHER_KEY = "z" * 30


def with_key(client, key: str = KEY):
    return refresh(client, headers={"X-Refresh-Attempt": key})


def issued(response) -> str | None:
    """The refresh cookie a response set (read from the response: after `use_cookie` the test
    client's jar can hold two entries with the same name)."""
    return response.cookies.get("cc_refresh")


def age_used_rows(client, seconds: int) -> None:
    """Pretend every used token was used `seconds` ago."""
    with client.app.state.session_factory() as db:
        for row in db.scalars(select(RefreshToken).where(RefreshToken.used_at.is_not(None))):
            row.used_at = datetime.now(UTC) - timedelta(seconds=seconds)
        db.commit()


def row_count(client) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(RefreshToken)) or 0


def bearer(response) -> dict:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def lost_response(client) -> tuple[str, str]:
    """Rotate C1 -> C2 with KEY, then put C1 back as if the response never arrived."""
    register(client)
    c1 = cookie(client)
    r = with_key(client)
    assert r.status_code == 200, r.text
    c2 = issued(r)
    assert c2 and c2 != c1
    use_cookie(client, c1)
    return c1, c2


# --- the reported failure, inside and outside the 30-second race window ---------------------


def test_a_lost_refresh_response_is_recovered_by_retrying_with_the_same_attempt_key(client):
    _, c2 = lost_response(client)
    r = with_key(client)  # the retry (or the reloaded page) still has C1 and the same key
    assert r.status_code == 200, r.text
    assert issued(r) == c2  # the same successor, not a second one
    assert client.get("/api/v1/auth/me", headers=bearer(r)).status_code == 200
    use_cookie(client, c2)
    assert refresh(client).status_code == 200  # and the session carries on normally


def test_recovery_also_works_after_the_race_window_when_a_reload_took_a_while(client):
    _, c2 = lost_response(client)
    age_used_rows(client, 60)  # past the 30 s race window, inside the recovery window
    r = with_key(client)
    assert r.status_code == 200, r.text
    assert issued(r) == c2


def test_recovery_is_idempotent_and_never_forks_the_session(client):
    c1, c2 = lost_response(client)
    rows = row_count(client)
    # Replaying the same (token, key) any number of times returns the same successor.
    for _ in range(3):
        use_cookie(client, c1)
        r = with_key(client)
        assert r.status_code == 200 and issued(r) == c2
    assert row_count(client) == rows  # nothing new was issued


# --- what recovery must NOT allow ------------------------------------------------------------


def test_a_different_attempt_key_is_still_a_race_and_then_reuse(client):
    _, c2 = lost_response(client)
    r = with_key(client, OTHER_KEY)
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_race"
    assert "set-cookie" not in r.headers
    age_used_rows(client, 60)
    r = with_key(client, OTHER_KEY)
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_reused"
    use_cookie(client, c2)
    assert refresh(client).json()["error"]["code"] == "invalid_refresh"  # the family is gone


def test_no_attempt_key_keeps_the_old_reuse_detection(client):
    _, c2 = lost_response(client)
    age_used_rows(client, 60)
    r = refresh(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_reused"
    use_cookie(client, c2)
    assert refresh(client).json()["error"]["code"] == "invalid_refresh"


def test_the_recovery_window_is_bounded(client):
    _, c2 = lost_response(client)
    age_used_rows(client, int(refresh_tokens.RECOVERY_WINDOW.total_seconds()) + 5)
    r = with_key(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_reused"
    use_cookie(client, c2)
    assert refresh(client).json()["error"]["code"] == "invalid_refresh"


def test_no_recovery_once_the_successor_has_been_used(client):
    c1, c2 = lost_response(client)
    use_cookie(client, c2)
    moved_on = refresh(client)
    assert moved_on.status_code == 200  # the real holder of C2 moved on to C3
    c3 = issued(moved_on)
    assert c3
    use_cookie(client, c1)
    assert with_key(client).json()["error"]["code"] == "refresh_race"  # a moment later: retryable
    age_used_rows(client, 60)
    assert with_key(client).json()["error"]["code"] == "refresh_reused"  # later: a copy exists
    use_cookie(client, c3)
    assert refresh(client).json()["error"]["code"] == "invalid_refresh"


def test_no_recovery_after_logout(client):
    register(client)
    c1 = cookie(client)
    r = with_key(client)
    use_cookie(client, issued(r) or "")
    assert client.post("/api/v1/auth/logout", headers=bearer(r)).status_code == 204  # signs out with C2
    use_cookie(client, c1)
    r = with_key(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_refresh"
    assert 'cc_refresh=""' in r.headers.get("set-cookie", "")


def test_no_recovery_after_signing_out_everywhere(client):
    register(client)
    c1 = cookie(client)
    r = with_key(client)
    assert client.post("/api/v1/auth/logout-all", headers=bearer(r)).status_code == 204
    use_cookie(client, c1)
    assert with_key(client).json()["error"]["code"] == "invalid_refresh"


def test_no_recovery_after_the_account_is_deleted(client):
    register(client)
    c1 = cookie(client)
    r = with_key(client)
    deleted = client.request(
        "DELETE",
        "/api/v1/auth/me",
        headers=bearer(r),
        json={"password": "CorrectHorse42", "confirm": "DELETE"},
    )
    assert deleted.status_code == 204
    use_cookie(client, c1)
    assert with_key(client).json()["error"]["code"] == "invalid_refresh"


def test_recovery_never_extends_a_lifetime_or_revives_an_expired_successor(client):
    c1, c2 = lost_response(client)

    def successor_expiry():
        with client.app.state.session_factory() as db:
            return db.scalars(select(RefreshToken).where(RefreshToken.used_at.is_(None))).one().expires_at

    expires = successor_expiry()
    assert with_key(client).status_code == 200
    assert successor_expiry() == expires  # handed back as it was, not re-issued
    with client.app.state.session_factory() as db:
        row = refresh_tokens.find(db, c2)
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    use_cookie(client, c1)
    r = with_key(client)
    assert r.status_code == 401 and r.json()["error"]["code"] in {"refresh_race", "invalid_refresh"}
    assert issued(r) != c2


def test_a_malformed_attempt_key_is_ignored(client):
    _, _ = lost_response(client)
    r = with_key(client, "not a key!")
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_race"


def test_the_attempt_key_does_not_bypass_the_csrf_guard(client):
    lost_response(client)
    r = client.post(REFRESH, headers={"X-Refresh-Attempt": KEY})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_rejected"
    r = client.post(REFRESH, headers={**H, "X-Refresh-Attempt": KEY, "Origin": "https://evil.example"})
    assert r.status_code == 403


def test_cors_lets_the_app_send_the_attempt_key(client):
    ok = client.options(
        REFRESH,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-requested-with,x-refresh-attempt",
        },
    )
    assert ok.status_code == 200
    assert "x-refresh-attempt" in ok.headers.get("access-control-allow-headers", "").lower()


# --- rotation is atomic, and a revoked family stays dead -------------------------------------


def test_two_requests_rotating_one_token_at_the_same_moment_issue_one_successor(client, monkeypatch):
    register(client)
    raw = cookie(client)
    real_find = refresh_tokens.find
    settings = client.app.state.settings

    def find_then_lose_the_race(db, value):
        row = real_find(db, value)  # this request has read C1 as unused...
        monkeypatch.setattr(refresh_tokens, "find", real_find)
        with client.app.state.session_factory() as other:  # ...and another one rotates it first
            refresh_tokens.rotate(other, value, settings)
            other.commit()
        return row

    monkeypatch.setattr(refresh_tokens, "find", find_then_lose_the_race)
    use_cookie(client, raw)
    r = refresh(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_race"
    with client.app.state.session_factory() as db:
        live = db.scalars(select(RefreshToken).where(RefreshToken.used_at.is_(None))).all()
    assert len(live) == 1  # one successor: the session didn't fork into two valid cookies


def test_a_family_with_any_revoked_token_cannot_be_refreshed(client):
    """Defence in depth for a logout that races a refresh: if a successor is issued just after
    the family was revoked (the revocation didn't see the new row), it must not work."""
    register(client)
    c1 = cookie(client)
    assert refresh(client).status_code == 200
    c2 = cookie(client)
    with client.app.state.session_factory() as db:
        row = refresh_tokens.find(db, c1)
        assert row is not None
        row.revoked_at = datetime.now(UTC)  # only the old row was revoked
        db.commit()
    use_cookie(client, c2)
    r = refresh(client)
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_refresh"


@pytest.mark.skipif(
    not (TEST_DATABASE_URL or "").startswith("postgresql"), reason="row locks: PostgreSQL only"
)
def test_a_logout_racing_a_refresh_also_revokes_the_successor_that_refresh_issued(client):
    """PostgreSQL, READ COMMITTED: a logout that waits on the row a refresh is rotating must still
    revoke the successor that refresh inserts. (A plain UPDATE wouldn't see the new row.)"""
    register(client)
    c1 = cookie(client)
    assert c1
    settings = client.app.state.settings
    sessions = client.app.state.session_factory
    refreshing = sessions()
    try:
        _, c2 = refresh_tokens.rotate(refreshing, c1, settings)  # C1 claimed, C2 inserted: not committed
        refreshing.flush()
        row = refresh_tokens.find(refreshing, c1)
        assert row is not None
        family = row.family_id

        def logout() -> None:
            with sessions() as db:
                refresh_tokens.revoke_family(db, family)
                db.commit()

        worker = threading.Thread(target=logout)
        worker.start()
        deadline = time.monotonic() + 10
        with sessions() as watcher:  # wait until the logout is blocked on the refresh's row lock
            waiting = text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'")
            while not watcher.scalar(waiting):
                assert time.monotonic() < deadline, "the logout never waited for the refresh"
                time.sleep(0.02)
        refreshing.commit()
    finally:
        refreshing.close()
    worker.join(timeout=10)
    assert not worker.is_alive()
    with sessions() as db:
        successor = refresh_tokens.find(db, c2)
        assert successor is not None and successor.revoked_at is not None


def test_a_reload_while_the_first_refresh_is_still_being_processed_gets_that_refresh_s_result(
    client, monkeypatch
):
    """The reloaded page sends the same cookie and key while the server is still rotating it for
    the first request: whichever claims the token first, both get the same successor."""
    register(client)
    raw = cookie(client)
    real_find = refresh_tokens.find
    settings = client.app.state.settings
    issued_first: list[str] = []

    def find_then_lose_to_the_first_request(db, value):
        row = real_find(db, value)
        monkeypatch.setattr(refresh_tokens, "find", real_find)
        with client.app.state.session_factory() as other:  # the first request, same key, wins
            issued_first.append(refresh_tokens.rotate(other, value, settings, attempt=KEY)[1])
            other.commit()
        return row

    monkeypatch.setattr(refresh_tokens, "find", find_then_lose_to_the_first_request)
    use_cookie(client, raw)
    r = with_key(client)
    assert r.status_code == 200, r.text
    assert issued(r) == issued_first[0]
