"""Forgot-password flow: no account enumeration, single-use expiring links, sessions revoked."""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import PasswordResetToken
from app.services import password_reset
from app.services.email import Email, SmtpEmailSender
from tests.conftest import auth_headers, register

PASSWORD = "CorrectHorse42"
NEW = "BatteryStaple99"


@pytest.fixture
def outbox(tmp_path) -> Path:
    return tmp_path / "outbox"


@pytest.fixture
def mail_client(make_client, outbox):
    return make_client(email_backend="file", email_file_dir=str(outbox))


def emails(outbox: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(outbox.glob("*.json"))] if outbox.exists() else []


def token_from(mail: dict) -> str:
    m = re.search(r"/reset-password#token=([\w-]+)", mail["text"])
    assert m, mail["text"]
    return m.group(1)


def ask(client, email):
    return client.post("/api/v1/auth/password-reset", json={"email": email})


def confirm(client, token, password=NEW):
    return client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": password})


def test_same_answer_for_known_unknown_and_guest_accounts(mail_client, outbox):
    register(mail_client)
    mail_client.post("/api/v1/auth/guest")
    known, unknown = ask(mail_client, "ada@example.com"), ask(mail_client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    sent = emails(outbox)
    assert [m["to"] for m in sent] == ["ada@example.com"]  # only the real account got mail
    assert sent[0]["subject"] == "Reset your CodeCoach AI password"


def test_reset_link_sets_the_password_once_and_ends_every_session(mail_client, outbox):
    tokens = register(mail_client)
    old_access = auth_headers(tokens)
    ask(mail_client, "ADA@example.com")  # emails are matched case-insensitively
    token = token_from(emails(outbox)[0])
    assert token not in mail_client.app.state.settings.app_base_url  # sanity: it's in the fragment

    r = confirm(mail_client, token)
    assert r.status_code == 204
    assert mail_client.get("/api/v1/auth/me", headers=old_access).status_code == 401  # signed out
    refreshed = mail_client.post("/api/v1/auth/refresh", headers={"X-Requested-With": "codecoach"})
    assert refreshed.status_code == 401  # the refresh cookie is dead too
    assert (
        mail_client.post(
            "/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        mail_client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": NEW}).status_code
        == 200
    )

    again = confirm(mail_client, token, "AnotherPass123")
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_reset_token"


def test_expired_and_garbage_links_are_rejected(mail_client, outbox):
    register(mail_client)
    ask(mail_client, "ada@example.com")
    token = token_from(emails(outbox)[0])
    with mail_client.app.state.session_factory() as db:
        db.scalars(select(PasswordResetToken)).one().expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert confirm(mail_client, token).json()["error"]["code"] == "invalid_reset_token"
    assert confirm(mail_client, "x" * 43).json()["error"]["code"] == "invalid_reset_token"


def test_one_email_per_minute_and_only_the_newest_link_works(mail_client, outbox, monkeypatch):
    register(mail_client)
    ask(mail_client, "ada@example.com")
    ask(mail_client, "ada@example.com")
    assert len(emails(outbox)) == 1  # can't be used to flood someone's inbox
    first = token_from(emails(outbox)[0])
    monkeypatch.setattr(password_reset, "RESEND_COOLDOWN", timedelta(0))
    ask(mail_client, "ada@example.com")
    assert len(emails(outbox)) == 2
    second = token_from(emails(outbox)[1])
    assert confirm(mail_client, first).status_code == 400  # superseded
    assert confirm(mail_client, second).status_code == 204


def test_only_hashes_are_stored(mail_client, outbox):
    register(mail_client)
    ask(mail_client, "ada@example.com")
    token = token_from(emails(outbox)[0])
    with mail_client.app.state.session_factory() as db:
        stored = db.scalars(select(PasswordResetToken.token_hash)).all()
    assert token not in stored and len(stored[0]) == 64


def test_new_password_follows_the_password_rules(mail_client, outbox):
    register(mail_client)
    ask(mail_client, "ada@example.com")
    r = confirm(mail_client, token_from(emails(outbox)[0]), "alllowercase1")
    assert r.status_code == 422


def test_reset_endpoints_are_rate_limited(make_client, outbox):
    c = make_client(email_backend="file", email_file_dir=str(outbox), auth_rate_limit_per_minute=2)
    assert ask(c, "a@example.com").status_code == 202
    assert ask(c, "b@example.com").status_code == 202
    assert ask(c, "c@example.com").status_code == 429


def test_deleting_the_account_removes_its_reset_links(mail_client, outbox):
    tokens = register(mail_client)
    ask(mail_client, "ada@example.com")
    mail_client.request(
        "DELETE",
        "/api/v1/auth/me",
        headers=auth_headers(tokens),
        json={"password": PASSWORD, "confirm": "DELETE"},
    )
    with mail_client.app.state.session_factory() as db:
        assert db.scalar(select(PasswordResetToken)) is None


def test_a_failing_mail_server_never_reaches_the_requester(make_client):
    c = make_client()

    class Broken:
        def send(self, email):
            raise ConnectionError("smtp down")

    c.app.state.email_sender = Broken()
    register(c)
    assert ask(c, "ada@example.com").status_code == 202


def test_smtp_sender_uses_starttls_and_login(make_settings):
    calls: list = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user))

        def send_message(self, msg):
            calls.append(("send", msg["To"], msg["Subject"], msg["From"]))

    settings = make_settings(
        email_backend="smtp",
        smtp_host="smtp.example.com",
        smtp_username="u",
        smtp_password="p",
        email_from="CodeCoach <no-reply@example.com>",
    )
    SmtpEmailSender(settings, smtp_class=FakeSMTP).send(
        Email(to="ada@example.com", subject="Hi", text="Body")
    )  # type: ignore[arg-type]
    assert calls == [
        ("connect", "smtp.example.com", 587),
        ("starttls",),
        ("login", "u"),
        ("send", "ada@example.com", "Hi", "CodeCoach <no-reply@example.com>"),
    ]


def test_production_requires_smtp_and_an_https_app_url(make_settings):
    base = {
        "environment": "production",
        "secret_key": "x" * 48,
        "cors_origins": ["https://app.example"],
        "email_backend": "smtp",
        "smtp_host": "smtp.example.com",
        "app_base_url": "https://app.example",
    }
    assert make_settings(**base).email_backend == "smtp"
    with pytest.raises(ValueError, match="EMAIL_BACKEND=smtp"):
        make_settings(**{**base, "email_backend": "console"})
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        make_settings(**{**base, "app_base_url": "http://app.example"})
