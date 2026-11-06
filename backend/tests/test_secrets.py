"""Secret management: secret values never appear in errors or repr, production refuses guessable
or example secrets, the example env file starts as-is, and SECRET_KEY can be rotated without
signing everyone out. Synthetic values only."""

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, weak_secret_reason
from app.services.auth import decode_access_token, issue_access_token
from tests.conftest import PRODUCTION_BASE, auth_headers, register

REPO = Path(__file__).resolve().parents[2]
FAKE_API_KEY = "sk-ant-synthetic-visible-0123456789abcdef"
FAKE_SMTP_PASSWORD = "smtp-synthetic-visible-pw-42"


def test_a_failed_startup_check_never_prints_the_values_it_was_given():
    with pytest.raises(ValidationError) as err:
        Settings(
            environment="production",  # the default SECRET_KEY: refused
            anthropic_api_key=FAKE_API_KEY,
            smtp_password=FAKE_SMTP_PASSWORD,
            _env_file=None,
        )
    text = str(err.value)
    assert "SECRET_KEY" in text
    assert FAKE_API_KEY not in text and FAKE_SMTP_PASSWORD not in text and "input_value" not in text
    with pytest.raises(ValidationError) as short:
        Settings(secret_key="short-visible-key", _env_file=None)
    assert "short-visible-key" not in str(short.value)


def test_printing_the_settings_shows_no_secret_values():
    s = Settings(
        **{**PRODUCTION_BASE, "anthropic_api_key": FAKE_API_KEY, "smtp_password": FAKE_SMTP_PASSWORD},
        _env_file=None,
    )
    for text in (repr(s), str(s), str(s.model_dump())):
        assert FAKE_API_KEY not in text and FAKE_SMTP_PASSWORD not in text
        assert PRODUCTION_BASE["secret_key"] not in text
        assert "unique-db-password" not in text  # DATABASE_URL carries the database password
    assert s.anthropic_api_key is not None and s.anthropic_api_key.get_secret_value() == FAKE_API_KEY


@pytest.mark.parametrize(
    "key",
    [
        "a" * 32,
        "abababababababababababababababab",
        "change-me-change-me-change-me-change-me",
        "my-production-secret-key-for-codecoach-2026",
        "0123456789012345678901234567890123",
    ],
)
def test_production_refuses_a_guessable_secret_key(key):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(**{**PRODUCTION_BASE, "secret_key": key}, _env_file=None)


def test_generated_keys_pass_the_strength_check():
    import secrets

    for _ in range(50):
        assert weak_secret_reason(secrets.token_urlsafe(48)) is None
        assert weak_secret_reason(secrets.token_hex(32)) is None


def test_production_refuses_example_database_passwords_and_auto_migrate():
    ok = Settings(**PRODUCTION_BASE, _env_file=None)
    assert ok.auto_migrate is False  # off by default in production; on elsewhere
    assert Settings(_env_file=None).auto_migrate is True
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            **{**PRODUCTION_BASE, "database_url": "postgresql+psycopg://codecoach:codecoach@db/codecoach"},
            _env_file=None,
        )
    with pytest.raises(ValidationError, match="AUTO_MIGRATE"):
        Settings(**{**PRODUCTION_BASE, "auto_migrate": True}, _env_file=None)


def test_the_example_env_file_starts_as_is():
    s = Settings(_env_file=str(REPO / ".env.example"))
    assert s.environment == "development"
    assert s.refresh_cookie_secure is None  # a blank line means "not set", not an error
    assert s.anthropic_api_key is None and s.runner_token is None


def test_previous_keys_must_be_long_enough():
    with pytest.raises(ValidationError, match="SECRET_KEY_PREVIOUS"):
        Settings(secret_key_previous="too-short", _env_file=None)


OLD = "old-synthetic-signing-key-0123456789-abcdefghij"
NEW = "new-synthetic-signing-key-9876543210-zyxwvutsrq"


def test_tokens_signed_with_a_previous_key_are_accepted_only_while_it_is_listed():
    token, _ = issue_access_token(OLD, user_id="u1", token_version=0, ttl=timedelta(minutes=5))
    assert decode_access_token([NEW, OLD], token)["sub"] == "u1"
    assert decode_access_token([NEW], token) is None
    assert decode_access_token(NEW, token) is None
    expired, _ = issue_access_token(OLD, user_id="u1", token_version=0, ttl=timedelta(minutes=-1))
    assert decode_access_token([NEW, OLD], expired) is None


def test_rotating_secret_key_keeps_people_signed_in_when_the_old_key_is_listed(make_client):
    before = make_client(secret_key=OLD, auto_migrate=True)
    data = register(before, email="rotate@example.com")
    headers = auth_headers(data)
    cookies = dict(before.cookies)

    rotated = make_client(secret_key=NEW, secret_key_previous=OLD, auto_migrate=False)
    rotated.cookies.update(cookies)
    assert rotated.get("/api/v1/auth/me", headers=headers).status_code == 200
    refreshed = rotated.post("/api/v1/auth/refresh", headers={"X-Requested-With": "codecoach"})
    assert refreshed.status_code == 200, refreshed.text
    new_token = refreshed.json()["access_token"]
    assert decode_access_token(NEW, new_token) is not None  # new tokens use the new key only
    assert decode_access_token(OLD, new_token) is None

    dropped = make_client(secret_key=NEW, auto_migrate=False)
    assert dropped.get("/api/v1/auth/me", headers=headers).status_code == 401
