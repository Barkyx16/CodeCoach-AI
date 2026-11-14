"""Account recovery with the existing authentication: password reset and a change of email that
only takes effect once the new address confirms. Synthetic accounts; emails go to files."""

import json
import re
import threading
from pathlib import Path

import pytest

from tests.conftest import auth_headers, register

PASSWORD = "CorrectHorse42"
NEW_PASSWORD = "BatteryStaple99"


@pytest.fixture
def outbox(tmp_path) -> Path:
    return tmp_path / "outbox"


@pytest.fixture
def c(make_client, outbox):
    return make_client(email_backend="file", email_file_dir=str(outbox))


def mails(outbox: Path, to: str | None = None) -> list[dict]:
    found = [json.loads(p.read_text()) for p in sorted(outbox.glob("*.json"))] if outbox.exists() else []
    return [m for m in found if to is None or m["to"] == to]


def code_in(mail: dict) -> str:
    return re.search(r"verification code is: (\d{6})", mail["text"]).group(1)


def reset_token(mail: dict) -> str:
    return re.search(r"#token=([\w-]+)", mail["text"]).group(1)


def verified(c, outbox, email="ada@example.com"):
    data = register(c, email=email)
    h = auth_headers(data)
    r = c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": code_in(mails(outbox, email)[-1])})
    assert r.json()["email_verified"] is True
    return h


def ask_change(c, h, new, password=PASSWORD):
    return c.post("/api/v1/auth/email", headers=h, json={"new_email": new, "password": password})


def me(c, h):
    return c.get("/api/v1/auth/me", headers=h).json()


def test_cancelling_a_change_kills_its_codes(c, outbox):
    h = verified(c, outbox)
    assert ask_change(c, h, "new@example.com").json()["pending_email"] == "new@example.com"
    code = code_in(mails(outbox, "new@example.com")[-1])
    r = c.delete("/api/v1/auth/email/pending", headers=h)
    assert (
        r.status_code == 200 and r.json()["pending_email"] is None and r.json()["email"] == "ada@example.com"
    )
    late = c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": code})
    assert late.status_code == 409 or me(c, h)["email"] == "ada@example.com"
    assert me(c, h)["email"] == "ada@example.com" and me(c, h)["email_verified"] is True


def test_a_password_reset_from_the_old_address_cancels_the_change_and_signs_everyone_out(c, outbox):
    h = verified(c, outbox)
    ask_change(c, h, "attacker@example.com")  # say whoever had the password asked for this
    warning = mails(outbox, "ada@example.com")[-1]
    assert "reset your password" in warning["text"]
    assert c.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"}).status_code == 202
    token = reset_token(mails(outbox, "ada@example.com")[-1])
    r = c.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
    assert r.status_code == 204
    assert c.get("/api/v1/auth/me", headers=h).status_code == 401  # every session ended
    fresh = c.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": NEW_PASSWORD}).json()
    assert me(c, auth_headers(fresh))["pending_email"] is None
    # The code sent to the other address can no longer complete the change.
    code = code_in(mails(outbox, "attacker@example.com")[-1])
    r = c.post("/api/v1/auth/verify-email/code", headers=auth_headers(fresh), json={"code": code})
    assert me(c, auth_headers(fresh))["email"] == "ada@example.com"


def test_if_the_new_address_is_taken_before_confirming_nothing_changes(c, outbox):
    h = verified(c, outbox)
    ask_change(c, h, "new@example.com")
    code = code_in(mails(outbox, "new@example.com")[-1])
    register(c, email="new@example.com")  # someone else signs up with it meanwhile
    r = c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": code})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    after = me(c, h)
    assert (after["email"], after["email_verified"], after["pending_email"]) == (
        "ada@example.com",
        True,
        None,
    )


def test_a_second_change_replaces_the_first(c, outbox, monkeypatch):
    from datetime import timedelta

    from app.services import email_verification

    monkeypatch.setattr(email_verification, "RESEND_COOLDOWN", timedelta(0))
    h = verified(c, outbox)
    ask_change(c, h, "first@example.com")
    first = code_in(mails(outbox, "first@example.com")[-1])
    ask_change(c, h, "second@example.com")
    assert me(c, h)["pending_email"] == "second@example.com"
    c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": first})
    assert me(c, h)["email"] == "ada@example.com"  # the first address's code no longer works
    second = code_in(mails(outbox, "second@example.com")[-1])
    done = c.post("/api/v1/auth/verify-email/code", headers=h, json={"code": second}).json()
    assert done["email"] == "second@example.com"


def test_resend_goes_to_the_pending_address(c, outbox, monkeypatch):
    from datetime import timedelta

    from app.services import email_verification

    h = verified(c, outbox)
    ask_change(c, h, "new@example.com")
    assert c.post("/api/v1/auth/verify-email/resend", headers=h).status_code == 429  # cooldown applies
    monkeypatch.setattr(email_verification, "RESEND_COOLDOWN", timedelta(0))
    r = c.post("/api/v1/auth/verify-email/resend", headers=h)
    assert r.status_code == 202 and "n•••@example.com" in r.json()["message"]  # masked
    assert len(mails(outbox, "new@example.com")) == 2


def test_a_reset_link_works_once_even_when_used_twice_at_the_same_moment(c, outbox):
    register(c, email="ada@example.com")
    c.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    token = reset_token(mails(outbox, "ada@example.com")[-1])
    results: list[int] = []

    def use(password: str) -> None:
        r = c.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": password})
        results.append(r.status_code)

    threads = [threading.Thread(target=use, args=(f"ParallelPassword{i}9",)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [204] + [400] * 5
    again = c.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_reset_token"


def test_reset_requests_look_the_same_for_unknown_addresses(c, outbox):
    register(c, email="ada@example.com")
    known = c.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    unknown = c.post("/api/v1/auth/password-reset", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert mails(outbox, "nobody@example.com") == []


def test_a_guest_cannot_change_an_email_and_a_wrong_password_changes_nothing(c, outbox):
    g = c.post("/api/v1/auth/guest").json()
    assert ask_change(c, auth_headers(g), "x@example.com").status_code == 401
    h = verified(c, outbox)
    assert ask_change(c, h, "new@example.com", password="WrongHorse99").status_code == 401
    assert me(c, h)["pending_email"] is None and mails(outbox, "new@example.com") == []


def link_in(mail: dict) -> str:
    return re.search(r"/verify-email#token=([\w-]+)", mail["text"]).group(1)


def test_a_password_change_cancels_a_pending_change_and_its_signed_out_link(c, outbox):
    h = verified(c, outbox)
    ask_change(c, h, "attacker@example.com")  # whoever had the old password asked for this
    link = link_in(mails(outbox, "attacker@example.com")[-1])
    r = c.post(
        "/api/v1/auth/password",
        headers=h,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 200
    fresh = auth_headers(r.json())
    assert me(c, fresh)["pending_email"] is None
    # The link works without a session, so ending sessions alone wouldn't have stopped it.
    assert c.post("/api/v1/auth/verify-email", json={"token": link}).status_code == 400
    assert me(c, fresh)["email"] == "ada@example.com"
