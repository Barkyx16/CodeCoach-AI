"""Delivery problems, against a real SMTP conversation (tests/smtp_fake.py), no provider:
- an outage ends in `failed` after a bounded number of attempts, never in endless resending or a
  "delivered" the app can't know;
- an operator retry after the outage sends each email exactly once, drops a reset link that would
  arrive dead, and never retries a permanent refusal;
- diagnostics name jobs, statuses, error classes and Message-IDs, never an address, subject or
  code.
Synthetic accounts only; nothing leaves the machine."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.models import EmailJob
from app.services import email_ops, outbox
from tests.conftest import register
from tests.smtp_fake import FakeSMTPServer, make_certificate
from tests.test_email_transport import drain, jobs, mail_client, make_due

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command")


@pytest.fixture
def cert(tmp_path):
    return make_certificate(tmp_path, "localhost")


def exhaust(c) -> list[str]:
    """Run every retry the outbox will make, as if time passed between them."""
    seen = []
    for _ in range(outbox.MAX_ATTEMPTS + 3):
        make_due(c)
        seen.append(drain(c))
    return seen


def test_an_outage_stops_after_its_attempts_and_never_claims_delivery(make_client, cert):
    down = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="451 4.3.0 try later")
    try:
        c = mail_client(make_client, down, cert)
        register(c, email="ada@example.com")  # first attempt right after the response
        outcomes = exhaust(c)
        [job] = jobs(c)
        assert (job.status, job.attempts) == ("failed", outbox.MAX_ATTEMPTS)
        assert outcomes[-1] == {} and outcomes[-2] == {}  # finished: no endless resending
        assert down.messages == []  # every attempt was deferred, none taken
        assert len(down.sessions) == outbox.MAX_ATTEMPTS  # one SMTP conversation per attempt, no more
        assert {job.status for job in jobs(c)} <= set(outbox.FINISHED) and "delivered" not in outbox.FINISHED
    finally:
        down.close()


def test_after_the_outage_an_operator_retry_sends_each_email_once(make_client, cert, tmp_path):
    down = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="451 4.3.0 try later")
    up = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    try:
        c = mail_client(make_client, down, cert)
        register(c, email="ada@example.com")
        c.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
        exhaust(c)
        assert sorted(j.status for j in jobs(c)) == ["failed", "failed"]

        with c.app.state.session_factory() as db:
            # The verification email is retried; the reset link isn't (its address was cleared, and
            # the person can ask again).
            assert email_ops.requeue_failed(db, within=timedelta(hours=24)) == {
                "requeued": 1,
                "not_resendable": 1,
            }
        c.app.state.email_sender.settings = c.app.state.settings.model_copy(update={"smtp_port": up.port})
        assert drain(c) == {"accepted": 1}
        assert drain(c) == {} and len(up.messages) == 1  # once, not again
        assert "verification code" in up.messages[0].decode()
        with c.app.state.session_factory() as db:
            assert (
                email_ops.requeue_failed(db, within=timedelta(hours=24))["requeued"] == 0
            )  # accepted is final
    finally:
        down.close()
        up.close()


def test_a_retried_code_that_outlived_its_lifetime_is_dropped_not_sent(make_client, cert):
    down = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="451 4.3.0 try later")
    up = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    try:
        c = mail_client(make_client, down, cert)
        register(c, email="ada@example.com")
        exhaust(c)
        with c.app.state.session_factory() as db:
            db.execute(update(EmailJob).values(created_at=datetime.now(UTC) - timedelta(days=3)))
            db.commit()
            assert email_ops.requeue_failed(db, within=timedelta(days=7))["requeued"] == 1
        c.app.state.email_sender.settings = c.app.state.settings.model_copy(update={"smtp_port": up.port})
        assert drain(c) == {"dropped": 1} and up.messages == []
    finally:
        down.close()
        up.close()


def test_a_permanent_refusal_is_never_retried(make_client, cert):
    refusing = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="550 5.1.1 no such user")
    try:
        c = mail_client(make_client, refusing, cert)
        register(c, email="ada@example.com")
        [job] = jobs(c)
        assert job.status == "rejected"
        with c.app.state.session_factory() as db:
            assert email_ops.requeue_failed(db, within=timedelta(hours=24))["requeued"] == 0
        make_due(c)
        assert drain(c) == {} and len(refusing.sessions) == 1
    finally:
        refusing.close()


def test_diagnostics_are_redacted_but_correlate(make_client, cert, capsys, monkeypatch):
    up = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    try:
        c = mail_client(make_client, up, cert)
        data = register(c, email="ada.lovelace@example.com")
        [job] = jobs(c)
        with c.app.state.session_factory() as db:
            report = email_ops.status_report(db, account_email="ADA.lovelace@example.com")
            by_id = email_ops.status_report(db, message_id=job.message_id)
        [row] = report["jobs"]
        assert row == by_id["jobs"][0]
        assert (row["status"], row["to_domain"], row["account"]) == (
            "accepted",
            "example.com",
            data["user"]["id"],
        )
        assert row["message_id"] == job.message_id  # what a provider's logs will show
        assert report["counts"] == {"accepted": 1}

        from app.cli import main
        from app.config import get_settings

        monkeypatch.setenv("DATABASE_URL", c.app.state.settings.database_url)
        get_settings.cache_clear()
        try:
            assert main(["cli", "email-status", "--account", "ada.lovelace@example.com"]) == 0
        finally:
            get_settings.cache_clear()
        out = capsys.readouterr().out
        assert job.id in out and job.message_id in out and "to=*@example.com" in out
        assert "ada.lovelace" not in out and "verification code" not in out and "#token=" not in out
    finally:
        up.close()
