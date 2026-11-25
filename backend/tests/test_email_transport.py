"""Real email transport (SMTP): what a send proves, and what it doesn't.

Against a real SMTP conversation on a local socket (tests/smtp_fake.py): certificates and hostnames
are verified (an unknown certificate is refused, never downgraded to plaintext), a permanent refusal
(5xx) stops at once as `rejected`, a temporary one (4xx), a silent server or an outage is retried,
and `accepted` means only that the mail server took the message. Logs never carry addresses,
subjects or codes. No message leaves the machine."""

import logging
import shutil
from datetime import UTC, datetime, timedelta
from email import message_from_bytes

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update

from app.config import Settings
from app.models import EmailJob
from app.services import outbox
from app.services.email import (
    Email,
    EmailConfigurationError,
    EmailRejectedError,
    SmtpEmailSender,
    check_email,
)
from tests.conftest import PRODUCTION_BASE, register
from tests.smtp_fake import FakeSMTPServer, make_certificate

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command")


@pytest.fixture
def cert(tmp_path):
    return make_certificate(tmp_path, "localhost")


@pytest.fixture
def server(cert):
    srv = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    yield srv
    srv.close()


def smtp_settings(make_settings, srv, cert=None, **over):
    base = dict(
        email_backend="smtp",
        smtp_host="localhost",
        smtp_port=srv.port,
        smtp_username="synthetic-user",
        smtp_password="synthetic-pass",
        smtp_ca_bundle=str(cert[0]) if cert else None,
        smtp_timeout_seconds=2,
        email_from="CodeCoach AI <no-reply@codecoach.test>",
    )
    return make_settings(**{**base, **over})


MAIL = Email(
    to="ada@example.com",
    subject="123456 is your code",
    text="Your code: 123456",
    message_id="<codecoach.j1@codecoach.test>",
)


def test_a_trusted_server_gets_the_message_over_verified_tls(make_settings, server, cert):
    SmtpEmailSender(smtp_settings(make_settings, server, cert)).send(MAIL)
    assert server.sessions[-1]["tls"] and server.sessions[-1]["auth"]
    [raw] = server.messages
    msg = message_from_bytes(raw)
    assert (msg["To"], msg["Subject"], msg["Message-ID"]) == (
        "ada@example.com",
        "123456 is your code",
        "<codecoach.j1@codecoach.test>",
    )
    assert msg["From"] == "CodeCoach AI <no-reply@codecoach.test>" and msg["Date"]


def test_an_untrusted_certificate_is_refused_and_nothing_is_sent_in_plaintext(make_settings, server):
    import ssl

    with pytest.raises(ssl.SSLCertVerificationError):
        SmtpEmailSender(smtp_settings(make_settings, server)).send(
            MAIL
        )  # no CA bundle: self-signed is unknown
    assert server.messages == [] and not server.sessions[-1]["auth"]


def test_a_certificate_for_another_host_is_refused(make_settings, tmp_path):
    import ssl

    other_cert, other_key = make_certificate(tmp_path, "mail.other.test")
    srv = FakeSMTPServer(certfile=other_cert, keyfile=other_key)
    try:
        # The CA is trusted, but the certificate names a different host than the one we dialled.
        with pytest.raises(ssl.SSLCertVerificationError):
            SmtpEmailSender(smtp_settings(make_settings, srv, (other_cert, other_key))).send(MAIL)
        assert srv.messages == []
    finally:
        srv.close()


def test_implicit_tls(make_settings, cert):
    srv = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], implicit_tls=True)
    try:
        SmtpEmailSender(smtp_settings(make_settings, srv, cert, smtp_security="ssl")).send(MAIL)
        assert len(srv.messages) == 1 and srv.sessions[-1]["tls"]
    finally:
        srv.close()


def test_a_permanent_refusal_is_typed_and_names_only_the_code(make_settings, cert):
    srv = FakeSMTPServer(
        certfile=cert[0], keyfile=cert[1], rcpt_reply="550 5.1.1 <ada@example.com>: no such user"
    )
    try:
        with pytest.raises(EmailRejectedError) as err:
            SmtpEmailSender(smtp_settings(make_settings, srv, cert)).send(MAIL)
        assert "550" in str(err.value) and "ada@example.com" not in str(err.value)
    finally:
        srv.close()


def test_a_wrong_password_is_a_configuration_error(make_settings, cert):
    srv = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], auth_reply="535 5.7.8 bad credentials")
    try:
        with pytest.raises(EmailConfigurationError):
            SmtpEmailSender(smtp_settings(make_settings, srv, cert)).send(MAIL)
    finally:
        srv.close()


def mail_client(make_client, srv, cert, **over):
    c = make_client(
        **{
            "email_backend": "smtp",
            "smtp_host": "localhost",
            "smtp_port": srv.port,
            "smtp_username": "synthetic-user",
            "smtp_password": "synthetic-pass",
            "smtp_ca_bundle": str(cert[0]),
            "smtp_timeout_seconds": 1,
            "email_from": "CodeCoach AI <no-reply@codecoach.test>",
            **over,
        }
    )
    return c


def jobs(c):
    with c.app.state.session_factory() as db:
        return db.scalars(select(EmailJob).order_by(EmailJob.created_at)).all()


def make_due(c):
    with c.app.state.session_factory() as db:
        db.execute(update(EmailJob).values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()


def drain(c):
    return outbox.drain(c.app.state.session_factory, c.app.state.settings, c.app.state.email_sender)


def test_signup_email_is_accepted_with_the_jobs_message_id(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    register(c, email="ada@example.com")
    [job] = jobs(c)
    assert job.status == "accepted" and job.message_id == f"<codecoach.{job.id}@codecoach.test>"
    msg = message_from_bytes(server.messages[-1])
    assert msg["Message-ID"] == job.message_id and msg["To"] == "ada@example.com"


def test_a_refused_address_is_rejected_at_once_without_retries(make_client, cert):
    srv = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="550 5.1.1 no such user")
    try:
        c = mail_client(make_client, srv, cert)
        register(c, email="ada@example.com")
        [job] = jobs(c)
        assert (job.status, job.attempts, job.payload) == ("rejected", 1, None)
        assert job.last_error.startswith("EmailRejectedError") and "550" in job.last_error
        make_due(c)
        assert drain(c) == {}  # finished: never tried again
    finally:
        srv.close()


@pytest.mark.parametrize(
    "server_kwargs",
    [
        {"rcpt_reply": "451 4.7.1 try again later"},  # deferred
        {"silent": True},  # connects, never answers: the timeout
    ],
)
def test_temporary_problems_are_retried_then_succeed(make_client, cert, server_kwargs):
    bad = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], **server_kwargs)
    good = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    try:
        c = mail_client(make_client, bad, cert)
        register(c, email="ada@example.com")
        [job] = jobs(c)
        assert job.status == "pending" and job.attempts == 1 and job.last_error
        # The mail server recovers (here: the same settings now reach a working server).
        c.app.state.email_sender.settings = c.app.state.settings.model_copy(update={"smtp_port": good.port})
        make_due(c)
        assert drain(c) == {"accepted": 1}
        assert len(good.messages) == 1
    finally:
        bad.close()
        good.close()


def test_an_outage_then_a_worker_restart_still_delivers_once(make_client, cert):
    c = mail_client(make_client, FakeSMTPServer(certfile=cert[0], keyfile=cert[1]), cert, smtp_port=1)
    register(c, email="ada@example.com")  # port 1: connection refused
    [job] = jobs(c)
    assert job.status == "pending" and job.last_error in ("ConnectionRefusedError", "OSError")
    # A worker claimed it and died mid-send: the lease runs out and another process takes it.
    with c.app.state.session_factory() as db:
        db.execute(
            update(EmailJob).values(
                status="sending", next_attempt_at=datetime.now(UTC) - timedelta(seconds=1)
            )
        )
        db.commit()
    good = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    try:
        c.app.state.email_sender.settings = c.app.state.settings.model_copy(update={"smtp_port": good.port})
        assert drain(c) == {"accepted": 1} and drain(c) == {}
        assert len(good.messages) == 1
    finally:
        good.close()


def test_logs_never_carry_the_address_subject_or_code(make_client, cert, caplog):
    srv = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="550 5.1.1 <ada@example.com> unknown")
    try:
        c = mail_client(make_client, srv, cert)
        with caplog.at_level(logging.INFO):
            data = register(c, email="ada@example.com")
            c.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
        text = caplog.text
        assert "ada@example.com" not in text and "verification code" not in text and "#token=" not in text
        assert "refused by the mail server" in text and data["user"]["id"] not in text.replace(
            "codecoach.", ""
        )
    finally:
        srv.close()


def test_production_refuses_unencrypted_smtp_and_a_localhost_sender():
    with pytest.raises(ValidationError, match="SMTP_SECURITY"):
        Settings(**{**PRODUCTION_BASE, "smtp_security": "none"}, _env_file=None)
    with pytest.raises(ValidationError, match="SMTP_SECURITY"):
        Settings(**{**PRODUCTION_BASE, "smtp_starttls": False}, _env_file=None)
    with pytest.raises(ValidationError, match="EMAIL_FROM"):
        Settings(**{**PRODUCTION_BASE, "email_from": "CodeCoach AI <no-reply@localhost>"}, _env_file=None)
    assert Settings(**{**PRODUCTION_BASE, "smtp_security": "ssl", "smtp_port": 465}, _env_file=None)


def test_check_email_reports_names_and_stages_never_values(make_settings, server, cert):
    out: list[str] = []
    settings = smtp_settings(make_settings, server, cert)
    assert check_email(settings, out=out.append) == 0
    text = "\n".join(out)
    assert "SMTP_PASSWORD: set" in text and "synthetic-pass" not in text and "synthetic-user" not in text
    out.clear()
    assert check_email(settings, connect=True, out=out.append) == 0
    assert "ok: connected" in out and "ok: encrypted, certificate verified" in out and "ok: signed in" in out
    assert server.messages == []  # --connect sends nothing
    out.clear()
    assert check_email(settings, send_to="ops@example.com", out=out.append) == 0
    assert len(server.messages) == 1 and "ACCEPTED" in out[-1] and "not proof of delivery" in out[-1]
    out.clear()
    assert check_email(make_settings(email_backend="console"), out=out.append) == 1
    assert "Nothing is sent" in "\n".join(out)


def test_check_email_reports_a_failure_without_secrets(make_settings, server):
    out: list[str] = []
    settings = smtp_settings(make_settings, server)  # the self-signed cert isn't trusted
    assert check_email(settings, connect=True, out=out.append) == 1
    assert out[-1].startswith("FAILED: SSLCertVerificationError") and "synthetic-pass" not in "\n".join(out)
