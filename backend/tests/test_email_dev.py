"""Email on a development server: nothing is sent, so the email is printed in the terminal as a
readable block, the app is told (so the "Check your email" page can say where the code went),
and settings from the repository's .env (what .env.example says to create) are read."""

import io
from pathlib import Path

from app.config import ENV_FILES
from app.services.email import ConsoleEmailSender, Email
from tests.conftest import register

REPO = Path(__file__).resolve().parents[2]


def test_the_console_backend_prints_a_readable_email():
    out = io.StringIO()
    ConsoleEmailSender(out).send(
        Email(
            to="ada@example.com",
            subject="123456 is your CodeCoach AI verification code",
            text="Code: 123456\nLink: x",
        )
    )
    text = out.getvalue()
    assert "EMAIL (not sent" in text and "docs/EMAIL.md" in text
    assert "│ To:      ada@example.com" in text
    assert "│ Subject: 123456 is your CodeCoach AI verification code" in text
    assert "│ Code: 123456" in text and "│ Link: x" in text


def test_registering_prints_the_verification_code(make_client, capsys):
    c = make_client(email_backend="console")
    register(c, email="ada@example.com")
    printed = capsys.readouterr().err
    assert "verification code" in printed and "ada@example.com" in printed


def test_capabilities_say_whether_emails_are_delivered(make_client):
    assert (
        make_client(email_backend="console").get("/api/v1/capabilities").json()["emails_delivered"] is False
    )
    smtp = make_client(email_backend="smtp", smtp_host="smtp.example.com")
    assert smtp.get("/api/v1/capabilities").json()["emails_delivered"] is True


def test_settings_read_the_repository_env_file_then_backend_env():
    assert ENV_FILES[0] == str(REPO / ".env")  # where .env.example says to put it
    assert ENV_FILES[1] == str(REPO / "backend" / ".env")  # overrides it
