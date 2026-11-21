"""Email verification as a recovery journey (Volume 7, prompt 5).

What the "Check your email" page can say, and what a link that doesn't work says:
- the status is the owner's only: a masked address, and a delivery state the outbox can back up
  (queued, retrying, sent to provider, kept locally, failed, unknown), never "delivered";
- resend follows the server's cooldown, a duplicate send makes one email, and only the newest
  email's code and link work, so an older message that arrives late can't verify anything;
- a link says why it doesn't work (malformed, unknown, expired, superseded, already used, address
  changed), and a link for another account isn't used by a session signed in as someone else
  unless it asks to;
- no response carries a code or link, and public answers don't reveal whether an address has an
  account.
Synthetic accounts, a fake SMTP server on localhost, nothing leaves the machine."""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select, update

from app.models import EmailJob, EmailVerificationToken, User
from app.services import email_verification, outbox
from tests.conftest import auth_headers, register
from tests.smtp_fake import FakeSMTPServer, make_certificate
from tests.test_email_transport import drain, jobs, mail_client, make_due

PASSWORD = "CorrectHorse42"
needs_openssl = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command")


@pytest.fixture
def outbox_dir(tmp_path) -> Path:
    return tmp_path / "outbox"


@pytest.fixture
def c(make_client, outbox_dir):
    return make_client(email_backend="file", email_file_dir=str(outbox_dir))


@pytest.fixture
def cert(tmp_path):
    return make_certificate(tmp_path, "localhost")


def mails(directory: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))] if directory.exists() else []


def link_token(mail: dict) -> str:
    m = re.search(r"/verify-email#token=([\w-]+)", mail["text"])
    assert m, mail["text"]
    return m.group(1)


def code_of(mail: dict) -> str:
    m = re.search(r"verification code is: (\d{6})", mail["text"])
    assert m, mail["text"]
    return m.group(1)


def status(client, headers) -> dict:
    r = client.get("/api/v1/auth/verify-email/status", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def verify(client, token, headers=None, **extra):
    return client.post("/api/v1/auth/verify-email", json={"token": token, **extra}, headers=headers or {})


def age_tokens(client, seconds: int = 120) -> None:
    """As if every email so far went out `seconds` ago (past the resend cooldown)."""
    with client.app.state.session_factory() as db:
        for row in db.scalars(select(EmailVerificationToken)):
            row.created_at = row.created_at - timedelta(seconds=seconds)
        for job in db.scalars(select(EmailJob)):
            job.created_at = job.created_at - timedelta(seconds=seconds)
            if job.finished_at is not None:
                job.finished_at = job.finished_at - timedelta(seconds=seconds)
        db.commit()


# --- The status page ------------------------------------------------------------------------


def test_status_names_a_masked_address_the_cooldown_and_how_long_the_code_works(c, outbox_dir):
    h = auth_headers(register(c, email="ada.lovelace@example.com"))
    s = status(c, h)
    assert s["state"] == "pending" and s["changing_email"] is False
    assert s["address_masked"] == "a•••e@example.com"  # the domain shows, so a typo there is visible
    assert "ada.lovelace" not in json.dumps(s)
    # This server keeps emails in files (tests): said as such, never "sent" or "delivered".
    assert (s["transport"], s["delivery"]["state"]) == ("file", "kept_locally")
    assert 55 <= s["resend_available_in_seconds"] <= 60
    assert s["code_tries_left"] == email_verification.MAX_CODE_ATTEMPTS
    expires = datetime.fromisoformat(s["code_expires_at"])
    ttl = timedelta(hours=s["link_ttl_hours"])
    assert ttl - timedelta(minutes=1) < expires - datetime.now(UTC) <= ttl
    # A wrong code counts against the tries the page shows.
    c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": "000000"})
    assert status(c, h)["code_tries_left"] in (
        email_verification.MAX_CODE_ATTEMPTS - 1,
        email_verification.MAX_CODE_ATTEMPTS,  # 000000 was, by chance, the code (1 in a million)
    )


def test_status_is_the_owners_only_and_follows_verification_from_another_tab(c, outbox_dir):
    assert c.get("/api/v1/auth/verify-email/status").status_code == 401
    ada = auth_headers(register(c, email="ada@example.com"))
    c.cookies.clear()
    bob = auth_headers(register(c, email="bob@example.com"))
    assert status(c, bob)["address_masked"] == "b•••@example.com"  # its own, nothing of Ada's
    # Ada confirms in "another tab" (the link, signed out); this tab's next look says so.
    assert verify(c, link_token(mails(outbox_dir)[0])).status_code == 200
    s = status(c, ada)
    assert s["state"] == "verified" and s["delivery"] is None and s["resend_available_in_seconds"] == 0
    assert status(c, bob)["state"] == "pending"


def test_guests_have_nothing_to_confirm(c):
    guest = c.post("/api/v1/auth/guest", json={}).json()
    assert status(c, auth_headers(guest))["state"] == "not_applicable"


def test_a_queued_email_says_queued_until_it_is_sent(c, outbox_dir):
    h = auth_headers(register(c))
    with c.app.state.session_factory() as db:
        user = db.scalars(select(User)).one()
        outbox.enqueue(db, "verify_email", user_id=user.id)  # asked for, not attempted yet
        db.commit()
    s = status(c, h)["delivery"]
    assert s["state"] == "queued" and s["requested_at"] and s["updated_at"] is None
    drain(c)
    assert status(c, h)["delivery"]["state"] == "kept_locally"


@needs_openssl
def test_a_worker_failure_is_retrying_then_failed_never_sent(make_client, cert):
    down = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="451 4.3.0 try later")
    try:
        c = mail_client(make_client, down, cert)
        h = auth_headers(register(c, email="ada@example.com"))
        s = status(c, h)
        assert s["transport"] == "smtp"
        assert s["delivery"]["state"] == "retrying" and s["delivery"]["next_try_at"]
        for _ in range(outbox.MAX_ATTEMPTS + 2):
            make_due(c)
            drain(c)
        s = status(c, h)["delivery"]
        assert s["state"] == "failed" and s["updated_at"]
        assert down.messages == []
        # Nothing about the mail server reaches the learner: no SMTP code, host or error class.
        text = json.dumps(status(c, h))
        assert "451" not in text and "localhost" not in text and "Error" not in text
    finally:
        down.close()


@needs_openssl
def test_accepted_by_the_mail_server_is_sent_to_provider_and_a_refusal_is_failed(make_client, cert):
    up = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    try:
        c = mail_client(make_client, up, cert)
        h = auth_headers(register(c, email="ada@example.com"))
        s = status(c, h)["delivery"]
        assert s["state"] == "sent_to_provider" and s["updated_at"]  # not "delivered": unknowable here
    finally:
        up.close()
    refusing = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], rcpt_reply="550 5.1.1 no such user")
    try:
        c = mail_client(make_client, refusing, cert)
        h = auth_headers(register(c, email="bob@example.com"))
        assert status(c, h)["delivery"]["state"] == "failed"
    finally:
        refusing.close()


def test_no_record_is_unknown_and_a_cancelled_change_is_not_mistaken_for_this_address(c, outbox_dir):
    h = auth_headers(register(c, email="ada@example.com"))
    age_tokens(c)
    # Ask to change to another address, then cancel: the page is about ada@ again, and the
    # email that went to the other address isn't reported as this one's.
    r = c.post("/api/v1/auth/email", headers=h, json={"new_email": "other@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert status(c, h)["changing_email"] is True and status(c, h)["address_masked"] == "o•••r@example.com"
    latest = max(jobs(c), key=lambda j: j.created_at)
    with c.app.state.session_factory() as db:  # the email to other@ failed, say
        db.execute(update(EmailJob).where(EmailJob.id == latest.id).values(status="failed"))
        db.commit()
    c.delete("/api/v1/auth/email/pending", headers=h)
    s = status(c, h)
    assert s["changing_email"] is False and s["address_masked"] == "a•••@example.com"
    assert s["delivery"]["state"] == "kept_locally"  # the registration email, not the failed one to other@
    assert s["code_expires_at"] is None  # its code was replaced by the change's: send a new one
    with c.app.state.session_factory() as db:
        db.execute(delete(EmailJob))  # finished jobs are purged after a week
        db.commit()
    assert status(c, h)["delivery"]["state"] == "unknown"


# --- Resend ---------------------------------------------------------------------------------


def test_resend_follows_the_cooldown_and_a_duplicate_send_makes_one_email(c, outbox_dir, monkeypatch):
    h = auth_headers(register(c, email="ada@example.com"))
    r = c.post("/api/v1/auth/verify-email/resend", headers=h)
    assert r.status_code == 429 and r.json()["error"]["code"] == "resend_cooldown"
    assert abs(int(r.headers["Retry-After"]) - status(c, h)["resend_available_in_seconds"]) <= 1
    age_tokens(c)
    assert status(c, h)["resend_available_in_seconds"] == 0
    first = c.post("/api/v1/auth/verify-email/resend", headers=h)
    assert first.status_code == 202 and "a•••@example.com" in first.json()["message"]
    assert "ada@example.com" not in first.json()["message"]
    # A second click right after: refused with the time left, no second email.
    second = c.post("/api/v1/auth/verify-email/resend", headers=h)
    assert second.status_code == 429 and len(mails(outbox_dir)) == 2
    # Two requests that both got past the check (a race): the outbox sends one email.
    age_tokens(c)
    with c.app.state.session_factory() as db:
        user = db.scalars(select(User)).one()
        outbox.enqueue(db, "verify_email", user_id=user.id)
        outbox.enqueue(db, "verify_email", user_id=user.id)
        db.commit()
    assert drain(c) == {"accepted": 1, "skipped": 1}
    assert len(mails(outbox_dir)) == 3
    assert status(c, h)["delivery"]["state"] == "kept_locally"  # the skipped duplicate isn't "the" email


def test_a_delayed_older_email_cannot_verify_and_says_a_newer_one_replaced_it(c, outbox_dir):
    h = auth_headers(register(c, email="ada@example.com"))
    age_tokens(c)
    assert c.post("/api/v1/auth/verify-email/resend", headers=h).status_code == 202
    older, newer = mails(outbox_dir)
    # The older email arrives late and is opened first: it doesn't work, and says why.
    r = verify(c, link_token(older))
    assert r.status_code == 400 and r.json()["error"]["details"]["reason"] == "superseded"
    bad = c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": code_of(older)})
    assert bad.status_code == 400
    if code_of(older) != code_of(newer):  # equal by chance 1 in a million
        assert bad.json()["error"]["code"] == "superseded_verification_code"
    assert status(c, h)["state"] == "pending"
    assert verify(c, link_token(newer)).status_code == 200
    # Opened again later, both now say the email is already confirmed.
    for mail in (older, newer):
        assert verify(c, link_token(mail)).json()["error"]["details"]["reason"] == "already_verified"


def test_an_older_email_for_a_replaced_change_cannot_move_the_account(c, outbox_dir):
    h = auth_headers(register(c, email="ada@example.com"))
    verify(c, link_token(mails(outbox_dir)[0]))
    c.post("/api/v1/auth/email", headers=h, json={"new_email": "first@example.com", "password": PASSWORD})
    first_link = link_token([m for m in mails(outbox_dir) if m["to"] == "first@example.com"][0])
    c.post("/api/v1/auth/email", headers=h, json={"new_email": "second@example.com", "password": PASSWORD})
    r = verify(c, first_link)
    assert r.status_code == 400 and r.json()["error"]["details"]["reason"] == "address_changed"
    me = c.get("/api/v1/auth/me", headers=h).json()
    assert (me["email"], me["pending_email"]) == ("ada@example.com", "second@example.com")


# --- Links that don't work ------------------------------------------------------------------


def test_each_unusable_link_says_why(c, outbox_dir):
    h = auth_headers(register(c, email="ada@example.com"))
    token = link_token(mails(outbox_dir)[0])
    for raw, reason in (
        (token[:20], "malformed"),  # cut short by a mail app
        (token + "x", "malformed"),
        ("not a token at all!", "malformed"),
        ("A" * 43, "unknown"),  # well formed, but not one of ours
    ):
        r = verify(c, raw)
        assert r.status_code == 400, (raw, r.text)
        assert r.json()["error"]["details"] == {"reason": reason, "account": "signed_out"}
    # Signed in: the same answers, and whose link it was, if it names an account.
    assert verify(c, "A" * 43, h).json()["error"]["details"] == {"reason": "unknown", "account": "unknown"}
    with c.app.state.session_factory() as db:
        db.execute(update(EmailVerificationToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    r = verify(c, token, h)
    assert r.json()["error"]["details"] == {"reason": "expired", "account": "this"}
    assert "48 hours" in r.json()["error"]["message"]  # the configured lifetime


def test_too_many_wrong_codes_stop_the_link_too(c, outbox_dir):
    h = auth_headers(register(c, email="ada@example.com"))
    mail = mails(outbox_dir)[0]
    wrong = "000001" if code_of(mail) != "000001" else "000002"
    for _ in range(email_verification.MAX_CODE_ATTEMPTS):
        c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": wrong})
    r = verify(c, link_token(mail), h)
    assert r.json()["error"]["details"] == {"reason": "stopped", "account": "this"}
    assert status(c, h)["code_expires_at"] is None and status(c, h)["code_tries_left"] is None


def test_a_link_opened_while_signed_in_as_someone_else_asks_first(c, outbox_dir):
    register(c, email="ada@example.com")
    ada_link = link_token(mails(outbox_dir)[0])
    c.cookies.clear()
    bob_tokens = register(c, email="bob@example.com")
    bob = auth_headers(bob_tokens)
    r = verify(c, ada_link, bob)
    assert r.status_code == 409 and r.json()["error"]["code"] == "verification_link_other_account"
    assert r.json()["error"]["details"] == {"account": "other", "link_for": "a•••@e•••.com"}
    with c.app.state.session_factory() as db:  # nothing changed, and the link still works
        ada = db.scalars(select(User).where(User.email == "ada@example.com")).one()
        assert ada.email_verified_at is None
    # Asked to go ahead: Ada's address is confirmed; Bob's session learns nothing of Ada's account.
    r = verify(c, ada_link, bob, other_account_ok=True)
    assert r.status_code == 200
    assert r.json() == {
        "status": "verified",
        "account": "other",
        "email_masked": "a•••@e•••.com",
        "changed_email": False,
        "user": None,
    }
    assert status(c, bob)["state"] == "pending"  # Bob's own email is untouched
    # Ada's link again, as Bob: unusable now, and it says whose it was.
    assert verify(c, ada_link, bob).json()["error"]["details"] == {
        "reason": "already_verified",
        "account": "other",
    }


def test_the_owners_own_session_gets_the_account_back(c, outbox_dir):
    tokens = register(c, email="ada@example.com")
    r = verify(c, link_token(mails(outbox_dir)[0]), auth_headers(tokens))
    body = r.json()
    assert body["account"] == "this" and body["email_masked"] == "a•••@example.com"
    assert body["user"]["id"] == tokens["user"]["id"] and body["user"]["email_verified"] is True


# --- Nothing secret or revealing in responses ------------------------------------------------


def test_no_response_carries_a_code_or_link_even_on_a_console_server(make_client, capsys):
    c = make_client(email_backend="console")
    reg = c.post("/api/v1/auth/register", json={"email": "ada@example.com", "password": PASSWORD})
    printed = capsys.readouterr().err
    code = re.search(r"verification code is: (\d{6})", printed).group(1)
    link = re.search(r"verify-email#token=([\w-]+)", printed).group(1)
    h = auth_headers(reg.json())
    bodies = [
        reg.text,
        c.get("/api/v1/auth/verify-email/status", headers=h).text,
        c.post("/api/v1/auth/verify-email/resend", headers=h).text,
        c.get("/api/v1/capabilities").text,
    ]
    for body in bodies:
        assert code not in body and link not in body
    assert c.get("/api/v1/capabilities").json()["emails_delivered"] is False


def test_public_answers_do_not_reveal_whether_an_address_has_an_account(c):
    register(c, email="ada@example.com")
    c.cookies.clear()
    known = c.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    unknown = c.post("/api/v1/auth/password-reset", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    # A made-up link says the same "unknown" whoever asks; nothing names an account.
    a, b = (verify(c, raw).json()["error"] for raw in ("B" * 43, "C" * 43))
    a.pop("request_id"), b.pop("request_id")
    assert a == b and "ada" not in json.dumps(a)
