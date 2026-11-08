"""Background jobs: account emails go through a durable outbox (sent right after the response,
retried with backoff if that fails, never sent twice, never holding a usable secret), and
housekeeping runs without the code judge. Synthetic accounts and a fake mail server only."""

import json
import re
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, update

from app.jobs import JobsRunner, housekeeping
from app.models import EmailJob, RateLimitCounter, RefreshToken, User
from app.services import outbox
from app.services.email import Email
from tests.conftest import auth_headers, register


class FlakyMail:
    """A mail server that fails the first `failures` sends, then records the rest."""

    def __init__(self, failures=0):
        self.failures = failures
        self.sent: list[Email] = []
        self.lock = threading.Lock()

    def send(self, email: Email) -> None:
        with self.lock:
            if self.failures > 0:
                self.failures -= 1
                raise ConnectionError("synthetic: mail server unreachable")
            self.sent.append(email)


@pytest.fixture
def mail_client(make_client):
    c = make_client()
    c.app.state.email_sender = FlakyMail()
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


def test_an_email_is_a_job_sent_right_after_the_response(mail_client):
    register(mail_client, email="ada@example.com")
    [job] = jobs(mail_client)
    assert (job.kind, job.status, job.attempts) == ("verify_email", "accepted", 1)
    assert job.payload is None and job.finished_at is not None  # nothing kept once it's done
    [mail] = mail_client.app.state.email_sender.sent
    assert mail.to == "ada@example.com" and re.search(r"\b\d{6}\b", mail.subject)


def test_a_failed_send_is_retried_and_the_retry_still_works(mail_client):
    mail = mail_client.app.state.email_sender
    mail.failures = 1
    data = register(mail_client, email="ada@example.com")
    [job] = jobs(mail_client)
    assert job.status == "pending" and job.attempts == 1 and job.last_error == "ConnectionError"
    assert job.next_attempt_at.replace(tzinfo=UTC) > datetime.now(UTC)  # backing off
    assert mail.sent == [] and drain(mail_client) == {}  # not due yet: nothing happens
    make_due(mail_client)
    assert drain(mail_client) == {"accepted": 1}
    # The retry wasn't swallowed by the once-a-minute dedupe, and its code works.
    code = re.search(r"\b(\d{6})\b", mail.sent[0].subject).group(1)
    r = mail_client.post("/api/v1/auth/verify-email/code", headers=auth_headers(data), json={"code": code})
    assert r.status_code == 200 and r.json()["email_verified"] is True


def test_it_gives_up_after_the_last_attempt_and_forgets_the_address(mail_client):
    mail_client.app.state.email_sender.failures = 99
    mail_client.post("/api/v1/auth/password-reset", json={"email": "Nobody@Example.com"})
    register(mail_client, email="ada@example.com")  # a real job that keeps failing
    for _ in range(outbox.MAX_ATTEMPTS):
        make_due(mail_client)
        drain(mail_client)
    by_kind = {j.kind: j for j in jobs(mail_client)}
    assert (
        by_kind["verify_email"].status == "failed" and by_kind["verify_email"].attempts == outbox.MAX_ATTEMPTS
    )
    assert by_kind["password_reset"].status == "skipped"  # no such account: nothing to send, no error
    assert all(j.payload is None for j in by_kind.values())


def test_a_job_is_sent_once_however_many_processes_drain(mail_client):
    mail = mail_client.app.state.email_sender
    mail.failures = 1
    register(mail_client, email="ada@example.com")
    make_due(mail_client)
    [job] = jobs(mail_client)
    results = []
    threads = [
        threading.Thread(
            target=lambda: results.append(
                outbox.run(
                    mail_client.app.state.session_factory, job.id, mail_client.app.state.settings, mail
                )
            )
        )
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results).count("accepted") == 1 and len(mail.sent) == 1


def test_a_reset_link_that_would_arrive_expired_is_dropped(mail_client):
    mail_client.app.state.email_sender.failures = 1
    register(mail_client, email="ada@example.com")
    mail_client.app.state.email_sender.failures = 1
    mail_client.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    with mail_client.app.state.session_factory() as db:
        db.execute(
            update(EmailJob)
            .where(EmailJob.kind == "password_reset")
            .values(created_at=datetime.now(UTC) - timedelta(hours=2))
        )
        db.commit()
    make_due(mail_client)
    drain(mail_client)
    reset = next(j for j in jobs(mail_client) if j.kind == "password_reset")
    assert reset.status == "dropped" and reset.payload is None
    assert not [m for m in mail_client.app.state.email_sender.sent if "Reset" in m.subject]


def test_jobs_never_hold_a_link_or_code(mail_client):
    mail = mail_client.app.state.email_sender
    mail.failures = 1
    register(mail_client, email="ada@example.com")
    mail.failures = 1
    mail_client.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    waiting = {j.kind: j.payload for j in jobs(mail_client)}
    assert waiting == {"verify_email": {}, "password_reset": {"email": "ada@example.com"}}
    make_due(mail_client)
    drain(mail_client)
    link = re.search(r"#token=([\w-]+)", next(m.text for m in mail.sent if "Reset" in m.subject)).group(1)
    with mail_client.app.state.session_factory() as db:
        stored = json.dumps([[j.payload, j.last_error] for j in db.scalars(select(EmailJob))])
    assert link not in stored


def test_an_unverified_old_address_is_never_told_about_the_change(mail_client):
    """A sign-up typo: the old address was never proven to be the owner's, so it gets nothing
    (telling it would show a stranger the person's new address)."""
    h = auth_headers(register(mail_client, email="ada@exmaple.com"))  # mistyped, never verified
    r = mail_client.post(
        "/api/v1/auth/email",
        headers=h,
        json={"new_email": "ada@example.com", "password": "CorrectHorse42"},
    )
    assert r.status_code == 200, r.text
    code = re.search(r"\b(\d{6})\b", mail_client.app.state.email_sender.sent[-1].subject).group(1)
    done = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": code}).json()
    assert (done["email"], done["email_verified"]) == ("ada@example.com", True)
    assert sorted((j.kind, j.status) for j in jobs(mail_client)) == [
        ("verify_email", "accepted"),
        ("verify_email", "accepted"),
    ]
    assert [m.to for m in mail_client.app.state.email_sender.sent] == ["ada@exmaple.com", "ada@example.com"]


def test_housekeeping_runs_without_the_judge(make_client, monkeypatch):
    c = make_client(execution_enabled=False, guest_retention_days=30)
    guest = c.post("/api/v1/auth/guest").json()["user"]["id"]
    with c.app.state.session_factory() as db:
        long_ago = datetime.now(UTC) - timedelta(days=60)
        db.execute(update(User).where(User.id == guest).values(created_at=long_ago, last_login_at=long_ago))
        db.execute(update(RefreshToken).where(RefreshToken.user_id == guest).values(created_at=long_ago))
        db.add(RateLimitCounter(key="stale", window=1, count=1, expires_at=1))
        db.add(
            EmailJob(
                kind="verify_email",
                status="accepted",
                created_at=datetime.now(UTC) - timedelta(days=30),
                finished_at=datetime.now(UTC) - timedelta(days=30),
            )
        )
        db.commit()
    done = housekeeping(c.app.state.session_factory, c.app.state.settings)
    assert done["rate_limit_counters_purged"] >= 1 and done["email_jobs_purged"] == 1
    assert done["guests_deleted"] == 1
    with c.app.state.session_factory() as db:
        assert db.get(User, guest) is None


def test_the_jobs_runner_retries_on_its_own_and_its_housekeeping_is_paced(mail_client):
    mail = mail_client.app.state.email_sender
    mail.failures = 1
    register(mail_client, email="ada@example.com")
    make_due(mail_client)
    now = [1000.0]
    runner = JobsRunner(
        mail_client.app.state.session_factory, mail_client.app.state.settings, mail, clock=lambda: now[0]
    )
    first = runner.run_once()
    assert (
        first["emails_accepted"] == 1 and "rate_limit_counters_purged" in first and "guests_deleted" in first
    )
    now[0] += 60  # a minute later: emails only; housekeeping waits its turn
    assert runner.run_once() == {}
    now[0] += 600
    assert "rate_limit_counters_purged" in runner.run_once() and "guests_deleted" not in runner.run_once()


def test_the_api_starts_and_stops_its_jobs_thread(make_client):
    c = make_client(background_jobs_in_api=True)
    names = [t.name for t in threading.enumerate()]
    assert "background-jobs" in names
    c.__exit__(None, None, None)
    assert not any(t.name == "background-jobs" and t.is_alive() for t in threading.enumerate())


def test_the_housekeeping_command(make_client, monkeypatch, capsys):
    from app.cli import main
    from app.config import get_settings

    c = make_client()
    monkeypatch.setenv("DATABASE_URL", c.app.state.settings.database_url)
    monkeypatch.setenv("EMAIL_BACKEND", "file")
    monkeypatch.setenv("EMAIL_FILE_DIR", str(Path(c.app.state.settings.email_file_dir)))
    get_settings.cache_clear()
    try:
        assert main(["cli", "housekeeping"]) == 0
    finally:
        get_settings.cache_clear()
    assert "rate_limit_counters_purged" in json.loads(capsys.readouterr().out)
