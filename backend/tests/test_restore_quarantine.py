"""After a restore, emails that were unsent at backup time are held, not sent by the first worker
that starts. The compose rehearsal found two pending verification emails in a restored copy.

Against a real SMTP conversation (tests/smtp_fake.py), synthetic accounts only. tests/test_backup.py
checks that restore-database holds them on a real PostgreSQL copy."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from app.models import EmailJob, EmailVerificationToken, User, new_id
from app.services import email_ops, outbox
from app.services.preflight import BLOCKED, run_preflight
from tests.conftest import register
from tests.smtp_fake import FakeSMTPServer, make_certificate
from tests.test_email_transport import drain, jobs, mail_client, make_due

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command")


@pytest.fixture
def cert(tmp_path):
    return make_certificate(tmp_path, "localhost")


@pytest.fixture
def server(cert):
    srv = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    yield srv
    srv.close()


def restored_outbox(c) -> dict[str, str]:
    """An outbox as a backup might hold it: one delivered email, and unsent ones of every kind of
    unsent (never tried, retrying, leased mid-send, too old). Returns job id by name."""
    register(c, email="delivered@example.com")  # sent right after the response: accepted
    ids = {"delivered": jobs(c)[0].id}
    with c.app.state.session_factory() as db:
        users = {}
        for name in ("pending", "retrying", "leased", "too_old"):
            users[name] = User(
                email=f"{name}@example.com",
                display_name=name,
                password_hash="x",
                auth_provider_id=f"password:{new_id()}",
            )
            db.add(users[name])
        db.flush()
        now = datetime.now(UTC)
        for name, user in users.items():
            job = outbox.enqueue(db, "verify_email", user_id=user.id)
            ids[name] = job.id
        db.flush()
        db.execute(
            update(EmailJob)
            .where(EmailJob.id == ids["retrying"])
            .values(attempts=2, last_error="TimeoutError")
        )
        db.execute(
            update(EmailJob)
            .where(EmailJob.id == ids["leased"])
            .values(status="sending", attempts=1, next_attempt_at=now + outbox.LEASE)
        )
        db.execute(
            update(EmailJob).where(EmailJob.id == ids["too_old"]).values(created_at=now - timedelta(days=30))
        )
        db.commit()
    return ids


def status_of(c, job_id: str) -> str:
    with c.app.state.session_factory() as db:
        return db.get(EmailJob, job_id).status


def test_held_emails_survive_two_workers_and_a_restart_without_one_send(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    sent_before = len(server.messages)
    with c.app.state.session_factory() as db:
        assert email_ops.hold_unsent(db) == 4  # every unsent one; the delivered one is untouched
    assert status_of(c, ids["delivered"]) == "accepted"
    for _ in range(2):  # two workers, then a restarted one (a fresh client on the same database)
        make_due(c)
        assert drain(c) == {}
        assert (
            drain(mail_client(make_client, server, cert, database_url=str(c.app.state.settings.database_url)))
            == {}
        )
    assert len(server.messages) == sent_before
    assert {status_of(c, ids[n]) for n in ("pending", "retrying", "leased", "too_old")} == {"held"}


def test_the_inventory_says_what_release_would_do_without_showing_addresses(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
        rows = {r["job"]: r for r in email_ops.held_inventory(db, c.app.state.settings)}
    assert set(rows) == {ids[n] for n in ("pending", "retrying", "leased", "too_old")}
    assert rows[ids["too_old"]]["on_release"].startswith("dropped")
    assert rows[ids["pending"]]["on_release"].startswith("sent, with a fresh code")
    assert all(r["to_domain"] == "example.com" for r in rows.values())
    assert not any("pending@" in str(v) for r in rows.values() for v in r.values())


def test_release_is_deliberate_partial_repeatable_and_sends_fresh_codes(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
        tokens_before = db.scalar(select(func.count()).select_from(EmailVerificationToken))
        # A dry run changes nothing.
        assert set(email_ops.release_held(db, job_ids=[ids["pending"], ids["too_old"]])) == {
            ids["pending"],
            ids["too_old"],
        }
    assert status_of(c, ids["pending"]) == "held"
    with c.app.state.session_factory() as db:
        email_ops.release_held(db, job_ids=[ids["pending"], ids["too_old"]], apply=True)
        assert (
            email_ops.release_held(db, job_ids=[ids["pending"], ids["too_old"]], apply=True) == []
        )  # repeat: no-op
    sent_before = len(server.messages)
    drain(c)
    assert status_of(c, ids["pending"]) == "accepted"  # sent
    assert status_of(c, ids["too_old"]) == "dropped"  # too old: nothing went out
    assert len(server.messages) == sent_before + 1
    with c.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(EmailVerificationToken)) == tokens_before + 1
        )  # a fresh code
    # The others are still held.
    assert {status_of(c, ids["retrying"]), status_of(c, ids["leased"])} == {"held"}


def test_a_released_email_that_fails_is_retried_normally(make_client, cert):
    down = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="451 4.3.0 try later")
    try:
        c = mail_client(make_client, down, cert)
        with c.app.state.session_factory() as db:
            user = User(
                email="later@example.com",
                display_name="Later",
                password_hash="x",
                auth_provider_id=f"password:{new_id()}",
            )
            db.add(user)
            db.flush()
            job_id = outbox.enqueue(db, "verify_email", user_id=user.id).id
            db.commit()
            email_ops.hold_unsent(db)
            email_ops.release_held(db, job_ids=[job_id], apply=True)
        assert drain(c) == {"retry": 1}
        assert status_of(c, job_id) == "pending"  # ordinary backoff, not held again
    finally:
        down.close()


def test_suppressed_emails_are_never_sent_and_lose_their_addresses(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
        chosen = email_ops.suppress_held(db, kind="verify_email", apply=True)
        assert set(chosen) == {ids[n] for n in ("pending", "retrying", "leased", "too_old")}
        assert email_ops.suppress_held(db, kind="verify_email", apply=True) == []
        assert all(j.payload is None for j in db.scalars(select(EmailJob).where(EmailJob.id.in_(chosen))))
    sent_before = len(server.messages)
    make_due(c)
    drain(c)
    assert len(server.messages) == sent_before
    assert {status_of(c, i) for i in chosen} == {"dropped"}
    assert status_of(c, ids["delivered"]) == "accepted"  # a sent email is history, not suppressed


def test_without_a_restore_nothing_is_held_and_queued_mail_still_goes(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    with c.app.state.session_factory() as db:
        user = User(
            email="normal@example.com",
            display_name="Normal",
            password_hash="x",
            auth_provider_id=f"password:{new_id()}",
        )
        db.add(user)
        db.flush()
        job_id = outbox.enqueue(db, "verify_email", user_id=user.id).id
        db.commit()
    assert drain(c) == {"accepted": 1}
    assert status_of(c, job_id) == "accepted"


def test_the_preflight_blocks_while_emails_are_held(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
    found = {ch.area: ch for ch in run_preflight(c.app.state.settings, engine=c.app.state.engine)}
    assert found["outbox"].status == BLOCKED and "held after a restore" in found["outbox"].reason


def test_the_cli_is_a_dry_run_by_default_and_shows_no_address(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
    env = {"DATABASE_URL": str(c.app.state.settings.database_url), "PATH": "/usr/bin:/bin"}
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, "-m", "app.cli", "email-quarantine", *a],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    listing = run()
    assert listing.returncode == 0 and "4 email(s) held" in listing.stdout
    assert "@example.com" in listing.stdout and "pending@" not in listing.stdout  # the domain only
    dry = run("--release", "--job", ids["pending"])
    assert "Would release 1" in dry.stdout and status_of(c, ids["pending"]) == "held"
    done = run("--release", "--job", ids["pending"], "--apply")
    assert "Released 1" in done.stdout and status_of(c, ids["pending"]) == "pending"
    assert run("--release", "--suppress").returncode == 2
