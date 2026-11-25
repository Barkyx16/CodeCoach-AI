"""Session and recovery hardening from the security pass of 2026-11-21 (docs/SECURITY.md, "Session
cookies"): where cookies are Secure, the sign-in and create-anchor cookies are `__Host-` cookies,
which no sibling subdomain or plain-http page can plant, and an unprefixed one (as such a page
could plant) is ignored; a guest's creation is resumable for 10 minutes, not an hour; a password
reset link stops working when the password is changed in Settings, on sign out everywhere, and
when a change of address is confirmed; the interactive API pages are off in production. Synthetic
accounts only."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.config import Settings
from app.services import create_intents
from tests.conftest import PRODUCTION_BASE, auth_headers, register

PASSWORD = "CorrectHorse42"
NEW = "BatteryStaple99"


def set_cookies(response) -> list[str]:
    return [v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"]


@pytest.fixture
def secure_client(make_client):
    c = make_client(refresh_cookie_secure=True)
    c.cookies.clear()
    return c


def test_where_cookies_are_secure_they_are_host_only_cookies(secure_client):
    c = secure_client
    anchor = set_cookies(c.post("/api/v1/auth/create-anchor"))
    started = set_cookies(c.post("/api/v1/auth/guest"))
    for header, name in ((anchor[0], "__Host-cc_create"), (started[0], "__Host-cc_refresh")):
        low = header.lower()
        assert header.startswith(f"{name}="), header
        assert "secure" in low and "httponly" in low and "samesite=strict" in low and "path=/;" in low + ";"
        assert "domain=" not in low  # host-only: no sibling subdomain receives or can replace it


def test_an_unprefixed_cookie_such_as_another_site_could_plant_is_ignored(secure_client):
    """A sibling subdomain (or a plain-http page on the network) can set `cc_create` but not
    `__Host-cc_create`. One planted for a victim's guest start must not tie that guest to a value the
    attacker knows."""
    c = secure_client
    planted = "planted-anchor-value-known-to-the-attacker-0001"
    victim = c.post("/api/v1/auth/guest", headers={"Cookie": f"cc_create={planted}"})
    assert victim.status_code == 201
    c.cookies.clear()
    attacker = c.post("/api/v1/auth/guest", headers={"Cookie": f"cc_create={planted}"})
    assert attacker.status_code == 201  # a new guest of its own, never the victim's
    assert attacker.json()["user"]["id"] != victim.json()["user"]["id"]
    assert attacker.headers.get("X-Account-Resumed") is None
    # The same goes for the sign-in cookie: an unprefixed one isn't a session here.
    raw = re.search(r"__Host-cc_refresh=([^;]+)", set_cookies(victim)[-1]).group(1)
    c.cookies.clear()
    refused = c.post(
        "/api/v1/auth/refresh",
        headers={
            "Cookie": f"cc_refresh={raw}",
            "X-Requested-With": "codecoach",
            "Origin": "http://localhost:5173",
        },
    )
    assert refused.status_code == 401
    # Under its own name, as the browser keeps it, the same value works.
    ok = c.post(
        "/api/v1/auth/refresh",
        headers={
            "Cookie": f"__Host-cc_refresh={raw}",
            "X-Requested-With": "codecoach",
            "Origin": "http://localhost:5173",
        },
    )
    assert ok.status_code == 200, ok.text


def test_a_lost_guest_start_is_resumable_for_minutes_not_an_hour():
    # Resuming a guest needs nothing but this browser's anchor, so the window is short.
    assert create_intents.CREATE_INTENT_MINUTES == 10


@pytest.fixture
def outbox(tmp_path) -> Path:
    return tmp_path / "outbox"


@pytest.fixture
def mail_client(make_client, outbox):
    return make_client(email_backend="file", email_file_dir=str(outbox))


def mails(outbox: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(outbox.glob("*.json"))] if outbox.exists() else []


def reset_link(client, outbox: Path, email: str = "ada@example.com") -> str:
    assert client.post("/api/v1/auth/password-reset", json={"email": email}).status_code == 202
    mail = [m for m in mails(outbox) if m["subject"] == "Reset your CodeCoach AI password"][-1]
    return re.search(r"/reset-password#token=([\w-]+)", mail["text"]).group(1)


def use(client, token):
    return client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW})


def test_changing_the_password_in_settings_ends_an_earlier_reset_link(mail_client, outbox):
    h = auth_headers(register(mail_client))
    token = reset_link(mail_client, outbox)
    r = mail_client.post(
        "/api/v1/auth/password",
        headers=h,
        json={"current_password": PASSWORD, "new_password": "Another-Pass-77"},
    )
    assert r.status_code == 200, r.text
    assert use(mail_client, token).json()["error"]["code"] == "invalid_reset_token"


def test_signing_out_everywhere_ends_an_earlier_reset_link(mail_client, outbox):
    h = auth_headers(register(mail_client))
    token = reset_link(mail_client, outbox)
    assert mail_client.post("/api/v1/auth/logout-all", headers=h).status_code == 204
    assert use(mail_client, token).json()["error"]["code"] == "invalid_reset_token"


def test_a_reset_link_sent_to_the_old_address_ends_when_a_new_one_is_confirmed(mail_client, outbox):
    h = auth_headers(register(mail_client))
    verify_first = next(m for m in mails(outbox) if "verify-email#token=" in m["text"])
    token = re.search(r"/verify-email#token=([\w-]+)", verify_first["text"]).group(1)
    assert mail_client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    reset = reset_link(mail_client, outbox)
    asked = mail_client.post(
        "/api/v1/auth/email", headers=h, json={"new_email": "new@example.com", "password": PASSWORD}
    )
    assert asked.status_code == 200
    to_new = [m for m in mails(outbox) if m["to"] == "new@example.com"][-1]
    new_token = re.search(r"/verify-email#token=([\w-]+)", to_new["text"]).group(1)
    assert mail_client.post("/api/v1/auth/verify-email", json={"token": new_token}).json()["changed_email"]
    assert use(mail_client, reset).json()["error"]["code"] == "invalid_reset_token"


def test_a_reset_link_still_works_when_nothing_has_changed(mail_client, outbox):
    """The fix doesn't break the ordinary path: request, then use."""
    register(mail_client)
    assert use(mail_client, reset_link(mail_client, outbox)).status_code == 204


def test_the_interactive_api_pages_are_off_in_production_unless_asked_for(make_client):
    assert Settings(**PRODUCTION_BASE).api_docs is False
    assert Settings(**PRODUCTION_BASE, api_docs_enabled=True).api_docs is True
    on = make_client()
    assert on.get("/docs").status_code == 200
    off = make_client(api_docs_enabled=False)
    assert off.get("/docs").status_code == 404 and off.get("/redoc").status_code == 404
    assert off.get("/openapi.json").status_code == 200  # the spec stays: it's in the repository
