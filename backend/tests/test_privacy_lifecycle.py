"""Privacy over time: what happens to an account's data when it's deleted while work is still in
flight, and what retention removes on its own. A late email job or a judge result that arrives
after the account is gone must not send anything to it or recreate a row for it. Expired sign-in
material is deleted a week after it expires. Synthetic accounts only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.models import (
    EmailJob,
    EmailVerificationToken,
    PasswordResetToken,
    ProgressEvent,
    RefreshToken,
    Submission,
    User,
)
from app.services import email_verification, outbox
from app.services.retention import purge_expired_tokens
from tests.conftest import auth_headers, register
from tests.judge_fakes import EXPECTED, expected_outputs, lines, submit

DELETE = {"password": "CorrectHorse42", "confirm": "DELETE"}


def rows_for(c, user_id: str) -> dict[str, int]:
    with c.app.state.session_factory() as db:
        return {
            m.__tablename__: db.scalar(select(func.count()).select_from(m).where(m.user_id == user_id))
            for m in (EmailJob, EmailVerificationToken, Submission, ProgressEvent, RefreshToken)
        }


def delete_account(c, h) -> None:
    assert c.request("DELETE", "/api/v1/auth/me", headers=h, json=DELETE).status_code == 204


def test_an_email_job_queued_before_deletion_sends_nothing_after(make_client, tmp_path):
    outbox_dir = tmp_path / "mail"
    c = make_client(email_backend="file", email_file_dir=str(outbox_dir))
    data = register(c, email="ada@example.com")
    user_id = data["user"]["id"]
    sent_before = len(list(outbox_dir.glob("*.json")))
    with c.app.state.session_factory() as db:
        job = outbox.enqueue(db, "verify_email", user_id=user_id)
        db.commit()
        job_id = job.id
    delete_account(c, auth_headers(data))
    outcome = outbox.run(c.app.state.session_factory, job_id, c.app.state.settings, c.app.state.email_sender)
    assert outcome == "not_due"  # the job went with the account
    assert len(list(outbox_dir.glob("*.json"))) == sent_before
    assert set(rows_for(c, user_id).values()) == {0}


def test_an_email_job_mid_send_when_the_account_is_deleted_recreates_nothing(
    make_client, tmp_path, monkeypatch
):
    outbox_dir = tmp_path / "mail"
    c = make_client(email_backend="file", email_file_dir=str(outbox_dir))
    data = register(c, email="ada@example.com")
    user_id = data["user"]["id"]
    with c.app.state.session_factory() as db:
        job_id = outbox.enqueue(db, "verify_email", user_id=user_id).id
        db.commit()
    sent_before = len(list(outbox_dir.glob("*.json")))
    real = email_verification.send_verification

    def deleted_meanwhile(*args, **kwargs):  # the job was claimed; the person deletes the account
        delete_account(c, auth_headers(data))
        return real(*args, **kwargs)

    monkeypatch.setattr(email_verification, "send_verification", deleted_meanwhile)
    assert (
        outbox.run(c.app.state.session_factory, job_id, c.app.state.settings, c.app.state.email_sender)
        == "skipped"
    )
    assert len(list(outbox_dir.glob("*.json"))) == sent_before  # nothing sent to a deleted account
    assert set(rows_for(c, user_id).values()) == {0}  # no code, no job row brought back
    with c.app.state.session_factory() as db:
        assert db.get(User, user_id) is None


def test_a_judge_result_after_deletion_recreates_nothing(judged):
    holder: dict = {}

    def script(files, nonce):  # the account is deleted while its code is being judged
        delete_account(holder["c"], holder["h"])
        return ("ok", lines(nonce, EXPECTED[0]), {})

    c, _, worker, h = judged(script)
    holder.update(c=c, h=h)
    EXPECTED[:] = [expected_outputs(c, "two-sum")[0]]
    user_id = c.get("/api/v1/auth/me", headers=h).json()["id"]
    submit(c, h)
    assert worker.process_one() is True  # handled, not a crash that would retry forever
    assert set(rows_for(c, user_id).values()) == {0}  # no "solved" event for a deleted account


def test_expired_sign_in_material_is_purged_a_week_after_it_expires(client):
    data = register(client, email="ada@example.com")
    client.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    now = datetime.now(UTC)
    with client.app.state.session_factory() as db:
        for model in (RefreshToken, PasswordResetToken, EmailVerificationToken):
            assert db.scalar(select(func.count()).select_from(model)) >= 1, model.__name__
        # One of each long expired, the newest refresh token left alone (it's this session).
        newest = db.scalar(select(RefreshToken.id).order_by(RefreshToken.created_at.desc()).limit(1))
        db.execute(update(PasswordResetToken).values(expires_at=now - timedelta(days=8)))
        db.execute(
            update(EmailVerificationToken).values(expires_at=now - timedelta(days=6))
        )  # within the week
        db.add(
            RefreshToken(
                user_id=data["user"]["id"],
                family_id="old-family",
                token_hash="0" * 64,
                token_version=0,
                created_at=now - timedelta(days=40),
                expires_at=now - timedelta(days=10),
            )
        )
        db.commit()
        removed = purge_expired_tokens(db, now)
        db.commit()
        assert removed == 2  # the old reset link and the old session
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 0
        assert db.scalar(select(func.count()).select_from(EmailVerificationToken)) >= 1  # kept for now
        assert db.get(RefreshToken, newest) is not None
    assert client.get("/api/v1/auth/me", headers=auth_headers(data)).status_code == 200  # still signed in


def test_daily_housekeeping_runs_the_purge(client):
    from app.jobs import housekeeping

    done = housekeeping(client.app.state.session_factory, client.app.state.settings, daily=True)
    assert "expired_tokens_purged" in done
