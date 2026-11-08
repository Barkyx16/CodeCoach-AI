"""Email verification and changing email: links, expiry, cooldown, notices, and the rules."""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import EmailVerificationToken
from app.services import email_verification
from tests.conftest import auth_headers, register

PASSWORD = "CorrectHorse42"


@pytest.fixture
def outbox(tmp_path) -> Path:
    return tmp_path / "outbox"


@pytest.fixture
def mail_client(make_client, outbox):
    return make_client(email_backend="file", email_file_dir=str(outbox))


def mails(outbox: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(outbox.glob("*.json"))] if outbox.exists() else []


def link_token(mail: dict) -> str:
    m = re.search(r"/verify-email#token=([\w-]+)", mail["text"])
    assert m, mail["text"]
    return m.group(1)


def verify(client, token):
    return client.post("/api/v1/auth/verify-email", json={"token": token})


def me(client, headers) -> dict:
    return client.get("/api/v1/auth/me", headers=headers).json()


def test_registration_sends_a_link_that_verifies_the_email(mail_client, outbox):
    tokens = register(mail_client)
    assert tokens["user"]["email_verified"] is False
    [mail] = mails(outbox)
    assert mail["to"] == "ada@example.com" and mail["subject"].endswith(
        "is your CodeCoach AI verification code"
    )
    r = verify(mail_client, link_token(mail))
    assert r.status_code == 200 and r.json()["email_verified"] is True
    assert me(mail_client, auth_headers(tokens))["email_verified"] is True
    again = verify(mail_client, link_token(mail))
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_verification_token"


def test_links_expire_and_hashes_only_are_stored(mail_client, outbox):
    register(mail_client)
    token = link_token(mails(outbox)[0])
    with mail_client.app.state.session_factory() as db:
        row = db.scalars(select(EmailVerificationToken)).one()
        assert row.token_hash != token and len(row.token_hash) == 64
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert verify(mail_client, token).json()["error"]["code"] == "invalid_verification_token"


def test_resend_respects_cooldown_and_supersedes_old_links(mail_client, outbox, monkeypatch):
    h = auth_headers(register(mail_client))
    first = link_token(mails(outbox)[0])
    r = mail_client.post("/api/v1/auth/verify-email/resend", headers=h)
    # Within the cooldown: says so, with the time left (it used to answer "sent" and send nothing).
    assert r.status_code == 429 and r.json()["error"]["code"] == "resend_cooldown"
    assert 1 <= int(r.headers["Retry-After"]) <= 60 and "seconds" in r.json()["error"]["message"]
    assert len(mails(outbox)) == 1  # no second email
    monkeypatch.setattr(email_verification, "RESEND_COOLDOWN", timedelta(0))
    r = mail_client.post("/api/v1/auth/verify-email/resend", headers=h)
    assert r.status_code == 202 and "on its way to ada@example.com" in r.json()["message"]
    second = link_token(mails(outbox)[1])
    assert verify(mail_client, first).status_code == 400  # superseded
    assert verify(mail_client, second).status_code == 200
    r = mail_client.post("/api/v1/auth/verify-email/resend", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_verified"


def test_guests_have_nothing_to_verify(mail_client, outbox):
    g = mail_client.post("/api/v1/auth/guest").json()
    assert g["user"]["email_verified"] is False
    r = mail_client.post("/api/v1/auth/verify-email/resend", headers=auth_headers(g))
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_applicable"
    assert mails(outbox) == []


def test_upgrading_a_guest_sends_a_verification_link(mail_client, outbox):
    g = mail_client.post("/api/v1/auth/guest").json()
    mail_client.post(
        "/api/v1/auth/upgrade",
        headers=auth_headers(g),
        json={"email": "grace@example.com", "password": PASSWORD},
    )
    assert [m["to"] for m in mails(outbox)] == ["grace@example.com"]


def login_ok(c, email):
    return c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200


def test_changing_email_waits_for_the_new_address_and_warns_the_old_one(mail_client, outbox):
    tokens = register(mail_client)
    h = auth_headers(tokens)
    verify(mail_client, link_token(mails(outbox)[0]))
    assert me(mail_client, h)["email_verified"] is True

    wrong = mail_client.post(
        "/api/v1/auth/email", headers=h, json={"new_email": "new@example.com", "password": "nope"}
    )
    assert wrong.status_code == 401
    r = mail_client.post(
        "/api/v1/auth/email", headers=h, json={"new_email": "New@Example.com", "password": PASSWORD}
    )
    assert r.status_code == 200
    # Nothing has changed yet: the account keeps its verified address until the new one confirms.
    assert (r.json()["email"], r.json()["email_verified"], r.json()["pending_email"]) == (
        "ada@example.com",
        True,
        "new@example.com",
    )
    assert login_ok(mail_client, "ada@example.com") and not login_ok(mail_client, "new@example.com")
    sent = mails(outbox)[1:]
    warning = next(m for m in sent if m["to"] == "ada@example.com")
    assert (
        "asked to change its email to new@example.com" in warning["text"]
        and "reset your password" in warning["text"]
    )
    new_link = next(m for m in sent if m["to"] == "new@example.com")
    done = verify(mail_client, link_token(new_link)).json()
    assert (done["email"], done["email_verified"], done["pending_email"]) == ("new@example.com", True, None)
    notice = [m for m in mails(outbox) if m["to"] == "ada@example.com"][-1]
    assert "changed to new@example.com" in notice["text"]  # and then the old address is told
    assert login_ok(mail_client, "new@example.com") and not login_ok(mail_client, "ada@example.com")


def test_a_link_for_a_previous_address_stops_working(mail_client, outbox):
    h = auth_headers(register(mail_client))
    old_link = link_token(mails(outbox)[0])
    mail_client.post(
        "/api/v1/auth/email", headers=h, json={"new_email": "new@example.com", "password": PASSWORD}
    )
    assert verify(mail_client, old_link).json()["error"]["code"] == "invalid_verification_token"


def test_change_email_rules(mail_client):
    register(mail_client, email="taken@example.com")
    mail_client.cookies.clear()
    h = auth_headers(register(mail_client))
    taken = mail_client.post(
        "/api/v1/auth/email", headers=h, json={"new_email": "taken@example.com", "password": PASSWORD}
    )
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "email_taken"
    same = mail_client.post(
        "/api/v1/auth/email", headers=h, json={"new_email": "ada@example.com", "password": PASSWORD}
    )
    assert same.status_code == 409 and same.json()["error"]["code"] == "same_email"
    g = mail_client.post("/api/v1/auth/guest").json()
    guest = mail_client.post(
        "/api/v1/auth/email",
        headers=auth_headers(g),
        json={"new_email": "x@example.com", "password": PASSWORD},
    )
    assert guest.status_code == 401


def code_from(mail: dict) -> str:
    m = re.search(r"verification code is: (\d{6})", mail["text"])
    assert m, mail["text"]
    return m.group(1)


def test_the_six_digit_code_verifies_the_signed_in_user(mail_client, outbox):
    h = auth_headers(register(mail_client))
    mail = mails(outbox)[0]
    code = code_from(mail)
    assert mail["subject"].startswith(code)  # visible in the inbox list
    r = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": f" {code} "})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    assert verify(mail_client, link_token(mail)).status_code == 400  # code and link are one token


def test_five_wrong_codes_kill_the_code(mail_client, outbox):
    h = auth_headers(register(mail_client))
    good = code_from(mails(outbox)[0])
    wrong = "000000" if good != "000000" else "111111"
    for left in (4, 3, 2, 1):
        r = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": wrong})
        assert r.status_code == 400 and r.json()["error"]["details"]["attempts_left"] == left
    r = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": wrong})
    assert r.json()["error"]["code"] == "too_many_attempts"
    r = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": good})
    assert r.status_code == 400  # even the right code is dead now; a resend issues a new one


def test_codes_are_stored_keyed_not_plain(mail_client, outbox):
    register(mail_client)
    code = code_from(mails(outbox)[0])
    with mail_client.app.state.session_factory() as db:
        row = db.scalars(select(EmailVerificationToken)).one()
    assert code not in row.code_hash and len(row.code_hash) == 64
    import hashlib

    assert row.code_hash != hashlib.sha256(code.encode()).hexdigest()  # not a plain, guessable hash


def test_code_format_is_validated(mail_client):
    h = auth_headers(register(mail_client))
    assert (
        mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": "12ab56"}).status_code
        == 422
    )


def test_a_replaced_code_says_so_and_the_newest_works(mail_client, outbox, monkeypatch):
    h = auth_headers(register(mail_client))
    old = code_from(mails(outbox)[0])
    monkeypatch.setattr(email_verification, "RESEND_COOLDOWN", timedelta(0))
    mail_client.post("/api/v1/auth/verify-email/resend", headers=h)
    new = code_from(mails(outbox)[1])
    if old == new:  # a 1-in-a-million coincidence would make the case below meaningless
        return
    r = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": old})
    assert r.status_code == 400 and r.json()["error"]["code"] == "superseded_verification_code"
    assert r.json()["error"]["details"]["attempts_left"] == 4  # it still counts as a guess
    ok = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": new})
    assert ok.status_code == 200 and ok.json()["email_verified"] is True
    # Using it again: already verified, nothing to do.
    assert (
        mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": new}).status_code == 200
    )


def test_parallel_wrong_guesses_get_no_more_than_five_tries(mail_client, outbox):
    import threading

    h = auth_headers(register(mail_client))
    right = code_from(mails(outbox)[0])
    wrong = f"{(int(right) + 1) % 1_000_000:06d}"
    counted: list[int] = []  # attempts_left from each answer that counted a wrong guess

    def guess() -> None:
        r = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": wrong})
        assert r.status_code == 400
        left = (r.json()["error"]["details"] or {}).get("attempts_left")
        if left is not None:
            counted.append(left)

    threads = [threading.Thread(target=guess) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # At most 4 answers say "N tries left" (4, 3, 2, 1, each once); the 5th wrong guess kills the code.
    assert sorted(counted) == sorted(set(counted)) and len(counted) <= 4 and min(counted, default=1) >= 1
    with mail_client.app.state.session_factory() as db:
        row = db.scalars(select(EmailVerificationToken)).one()
        assert row.code_attempts <= 5 and row.used_at is not None
    # The right code no longer works either: ask for a new one.
    r = mail_client.post("/api/v1/auth/verify-email/code", headers=h, json={"code": right})
    assert r.status_code == 400
