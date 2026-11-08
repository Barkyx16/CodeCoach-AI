"""After a restore, emails that were unsent at backup time are held, not sent by the first worker
that starts. The compose rehearsal found two pending verification emails in a restored copy.

Against a real SMTP conversation (tests/smtp_fake.py), synthetic accounts only. tests/test_backup.py
checks that restore-database holds them on a real PostgreSQL copy."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from email import message_from_bytes, policy
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from app.models import EmailJob, EmailVerificationToken, User, new_id
from app.services import email_ops, outbox
from app.services.preflight import BLOCKED, run_preflight
from tests.conftest import auth_headers, register
from tests.smtp_fake import FakeSMTPServer, make_certificate
from tests.test_email_transport import drain, jobs, mail_client, make_due

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command")

UNSENT = ("pending", "retrying", "leased", "too_old", "verified")


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
    unsent (never tried, retrying, leased mid-send, too old, for an address verified since).
    Returns job id by name."""
    register(c, email="delivered@example.com")  # sent right after the response: accepted
    ids = {"delivered": jobs(c)[0].id}
    with c.app.state.session_factory() as db:
        users = {}
        now = datetime.now(UTC)
        for name in UNSENT:
            users[name] = User(
                email=f"{name}@example.com",
                display_name=name,
                password_hash="x",
                auth_provider_id=f"password:{new_id()}",
                email_verified_at=now if name == "verified" else None,
            )
            db.add(users[name])
        db.flush()
        for name, user in users.items():
            ids[name] = outbox.enqueue(db, "verify_email", user_id=user.id).id
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


def settings_of(c):
    return c.app.state.settings


def code_in(raw: bytes) -> str:
    text = message_from_bytes(raw, policy=policy.default).get_body(preferencelist=("plain",)).get_content()
    return re.search(r"verification code is: (\d{6})", text).group(1)


def test_held_emails_survive_two_workers_and_a_restart_without_one_send(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    sent_before = len(server.messages)
    with c.app.state.session_factory() as db:
        assert email_ops.hold_unsent(db, "recovery") == 5  # every unsent one; the delivered one is untouched
    assert status_of(c, ids["delivered"]) == "accepted"
    for _ in range(2):  # two workers, then a restarted one (a fresh client on the same database)
        make_due(c)
        assert drain(c) == {}
        restarted = mail_client(make_client, server, cert, database_url=str(settings_of(c).database_url))
        assert drain(restarted) == {}
    assert len(server.messages) == sent_before
    assert {status_of(c, ids[n]) for n in UNSENT} == {"held"}


def test_the_inventory_says_what_release_would_do_without_showing_addresses(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
        rows = {r["job"]: r for r in email_ops.held_inventory(db, settings_of(c))}
    assert set(rows) == {ids[n] for n in UNSENT}
    # What each was doing at backup time, by the outbox's own state.
    assert {n: rows[ids[n]]["was"] for n in ("pending", "retrying", "leased")} == {
        "pending": "pending",
        "retrying": "retrying",
        "leased": "sending",
    }
    assert {r["held_by"] for r in rows.values()} == {"rehearsal"}  # the default
    # What release would do, by the real expiry and verification rules.
    assert rows[ids["too_old"]]["on_release"].startswith("dropped")
    assert rows[ids["verified"]]["on_release"].startswith("skipped: nothing to verify")
    assert rows[ids["pending"]]["on_release"].startswith("sent, with a fresh code")
    assert "may already have arrived" in rows[ids["leased"]]["on_release"]  # an ambiguous outcome
    assert "may already have arrived" not in rows[ids["pending"]]["on_release"]
    assert all(r["to_domain"] == "example.com" for r in rows.values())
    assert not any(f"{n}@" in str(v) for n in UNSENT for r in rows.values() for v in r.values())


def test_release_is_deliberate_partial_repeatable_and_sends_fresh_codes(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    chosen = [ids["pending"], ids["too_old"], ids["verified"]]
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db, "recovery")
        tokens_before = db.scalar(select(func.count()).select_from(EmailVerificationToken))
        # A dry run changes nothing.
        assert set(email_ops.release_held(db, settings_of(c), job_ids=chosen)) == set(chosen)
    assert status_of(c, ids["pending"]) == "held"
    with c.app.state.session_factory() as db:
        email_ops.release_held(db, settings_of(c), job_ids=chosen, apply=True)
        assert email_ops.release_held(db, settings_of(c), job_ids=chosen, apply=True) == []  # repeat: no-op
    sent_before = len(server.messages)
    drain(c)
    assert status_of(c, ids["pending"]) == "accepted"  # sent
    assert status_of(c, ids["too_old"]) == "dropped"  # too old: nothing went out
    assert status_of(c, ids["verified"]) == "skipped"  # verified since: nothing to send
    assert len(server.messages) == sent_before + 1
    with c.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(EmailVerificationToken)) == tokens_before + 1
        )  # a fresh code
    # The others are still held.
    assert {status_of(c, ids["retrying"]), status_of(c, ids["leased"])} == {"held"}


def test_a_rehearsal_copy_cant_email_the_real_people_in_it(make_client, server, cert, caplog):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)  # a rehearsal, the default
        for apply in (False, True):  # refused as a dry run too: it says what --apply would do
            with pytest.raises(email_ops.QuarantineRefused, match="held by a restore rehearsal"):
                email_ops.release_held(db, settings_of(c), job_ids=[ids["pending"]], apply=apply)
    assert status_of(c, ids["pending"]) == "held"
    # Suppressing is always allowed, and is kept on the job as a decision.
    with caplog.at_level(logging.INFO, logger="codecoach.email_ops"), c.app.state.session_factory() as db:
        assert email_ops.suppress_held(db, job_ids=[ids["pending"]], apply=True) == [ids["pending"]]
        job = db.get(EmailJob, ids["pending"])
        assert (job.status, job.last_error) == ("dropped", "suppressed:rehearsal:pending")
    logged = [r for r in caplog.records if r.getMessage() == "suppressed held emails"]
    assert logged and logged[0].jobs == [ids["pending"]]  # auditable by job id
    assert "pending@" not in caplog.text


def test_a_rehearsal_can_release_into_a_capture_transport(make_client, tmp_path):
    captured = tmp_path / "captured"
    c = make_client(email_backend="file", email_file_dir=str(captured))
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
        email_ops.release_held(db, settings_of(c), job_ids=[ids["pending"]], apply=True)
    drain(c)
    assert status_of(c, ids["pending"]) == "accepted"
    sent = [json.loads(p.read_text()) for p in captured.glob("*.json")]
    assert [m["to"] for m in sent if m["to"] == "pending@example.com"] == ["pending@example.com"]


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
            email_ops.hold_unsent(db, "recovery")
            email_ops.release_held(db, settings_of(c), job_ids=[job_id], apply=True)
        assert drain(c) == {"retry": 1}
        assert status_of(c, job_id) == "pending"  # ordinary backoff, not held again
    finally:
        down.close()


def test_an_interrupted_release_is_finished_by_running_it_again_and_sends_once(make_client, server, cert):
    """The release itself is one statement: all of the chosen jobs or none. What can be cut short
    is the send after it: a worker claims a released job and dies mid-send."""
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db, "recovery")
        email_ops.release_held(db, settings_of(c), job_ids=[ids["pending"]], apply=True)
        # A worker claims it (the outbox's own lease), then the process is killed before sending.
        db.execute(
            update(EmailJob)
            .where(EmailJob.id == ids["pending"])
            .values(status="sending", attempts=1, next_attempt_at=datetime.now(UTC) + outbox.LEASE)
        )
        db.commit()
        # Running the release again is harmless: that job isn't held any more.
        assert email_ops.release_held(db, settings_of(c), job_ids=[ids["pending"]], apply=True) == []
    sent_before = len(server.messages)
    assert drain(c) == {}  # the lease isn't up: nobody sends it twice at once
    make_due(c)  # the lease expires
    assert drain(c) == {"accepted": 1}
    assert len(server.messages) == sent_before + 1
    assert status_of(c, ids["retrying"]) == "held"  # the rest stayed held throughout


def test_verification_after_a_restore_only_works_with_a_valid_code(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    h = auth_headers(register(c, email="ada@example.com"))
    old_code = code_in(server.messages[-1])
    with c.app.state.session_factory() as db:
        # The backup is old: the code it sent then has expired, and a reminder was still queued.
        now = datetime.now(UTC)
        db.execute(
            update(EmailVerificationToken).values(
                created_at=now - timedelta(hours=49), expires_at=now - timedelta(hours=1)
            )
        )
        user_id = db.scalar(select(User.id).where(User.email == "ada@example.com"))
        job_id = outbox.enqueue(db, "verify_email", user_id=user_id).id
        db.commit()
        email_ops.hold_unsent(db, "recovery")
        email_ops.release_held(db, settings_of(c), job_ids=[job_id], apply=True)
    make_due(c)
    assert drain(c) == {"accepted": 1}
    new_code = code_in(server.messages[-1])
    assert new_code != old_code
    late = c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": old_code})
    assert late.status_code != 200 or late.json()["email_verified"] is False  # an expired code is not revived
    done = c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": new_code})
    assert done.status_code == 200 and done.json()["email_verified"] is True


def test_suppressed_emails_are_never_sent_and_lose_their_addresses(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
        chosen = email_ops.suppress_held(db, kind="verify_email", apply=True)
        assert set(chosen) == {ids[n] for n in UNSENT}
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
    found = {ch.area: ch for ch in run_preflight(settings_of(c), engine=c.app.state.engine)}
    assert found["outbox"].status == BLOCKED and "held after a restore" in found["outbox"].reason


def test_the_cli_is_a_dry_run_by_default_and_shows_no_address(make_client, server, cert):
    c = mail_client(make_client, server, cert)
    ids = restored_outbox(c)
    with c.app.state.session_factory() as db:
        email_ops.hold_unsent(db)
    env = {"DATABASE_URL": str(settings_of(c).database_url), "PATH": "/usr/bin:/bin", "EMAIL_BACKEND": "smtp"}
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, "-m", "app.cli", "email-quarantine", *a],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    listing = run()
    assert listing.returncode == 0 and "5 email(s) held" in listing.stdout
    assert "held by a rehearsal, was sending" in listing.stdout
    assert "@example.com" in listing.stdout and "pending@" not in listing.stdout  # the domain only
    refused = run("--release", "--job", ids["pending"], "--apply")  # a rehearsal, over SMTP
    assert (
        refused.returncode == 1
        and "Not released" in refused.stdout
        and status_of(c, ids["pending"]) == "held"
    )
    with c.app.state.session_factory() as db:  # the same backup, restored for a real recovery
        db.execute(update(EmailJob).where(EmailJob.status == "held").values(status="pending"))
        db.commit()
        email_ops.hold_unsent(db, "recovery")
    dry = run("--release", "--job", ids["pending"])
    assert "Would release 1" in dry.stdout and status_of(c, ids["pending"]) == "held"
    done = run("--release", "--job", ids["pending"], "--apply")
    assert "Released 1" in done.stdout and status_of(c, ids["pending"]) == "pending"
    assert run("--release", "--suppress").returncode == 2
    assert run("--kind").returncode == 2
