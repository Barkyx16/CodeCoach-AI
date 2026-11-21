"""Publishing the portfolio demo on the production compose (docs/DEMO.md, "Publishing it"): with
DEMO_MODE=true, production settings need no mail server (the demo refuses everything that sends
email, and the email helper refuses again; tests/test_demo.py), while every other production check
still applies and a production server that isn't a demo still needs SMTP; the preflight says
mail is optional there; deploy/demo.app.env.example, filled in, passes the production checks; and
the production compose takes the database's name from CODECOACH_DB everywhere it's used."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from app.config import Settings
from app.services.preflight import OPTIONAL, run_preflight
from tests.conftest import PRODUCTION_BASE

ROOT = Path(__file__).resolve().parents[2]
NO_MAIL = {k: v for k, v in PRODUCTION_BASE.items() if k not in ("email_backend", "smtp_host", "email_from")}


def test_a_production_demo_needs_no_mail_server():
    s = Settings(**NO_MAIL, demo_mode=True, email_backend="file")
    assert s.environment == "production" and s.demo_mode


def test_a_production_server_that_isnt_a_demo_still_needs_smtp():
    with pytest.raises(ValueError, match="EMAIL_FROM must be an address"):
        Settings(**NO_MAIL, email_backend="file")
    with pytest.raises(ValueError, match="EMAIL_BACKEND=smtp and SMTP_HOST"):
        Settings(**NO_MAIL, email_backend="file", email_from="CodeCoach AI <no-reply@app.example>")


def test_a_production_demo_cant_print_messages_to_the_logs():
    with pytest.raises(ValueError, match="EMAIL_BACKEND=console"):
        Settings(**NO_MAIL, demo_mode=True, email_backend="console")


def test_every_other_production_check_still_applies_to_a_demo():
    with pytest.raises(ValueError, match="SQLite"):
        Settings(
            **{**NO_MAIL, "database_url": "sqlite:///./codecoach-demo.db"},
            demo_mode=True,
            email_backend="file",
        )
    with pytest.raises(ValueError, match="https"):
        Settings(**{**NO_MAIL, "app_base_url": "http://demo.example"}, demo_mode=True, email_backend="file")
    with pytest.raises(ValueError):
        Settings(**{**NO_MAIL, "secret_key": "changeme"}, demo_mode=True, email_backend="file")


def test_the_preflight_says_a_demos_mail_is_optional(client, make_settings):
    s = make_settings(demo_mode=True, email_backend="file")
    checks = {c.area: c for c in run_preflight(s, engine=client.app.state.engine)}
    assert (
        checks["mail transport"].status == OPTIONAL
        and "demo mode sends no email" in checks["mail transport"].reason
    )
    assert "mail delivery" not in checks


def test_the_demo_env_example_filled_in_passes_the_production_checks():
    values: dict[str, str] = {}
    for line in (ROOT / "deploy/demo.app.env.example").read_text().splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key.lower()] = value
    assert values["demo_mode"] == "true" and values["ai_provider"] == "offline"
    blanks = {k for k, v in values.items() if v == ""}
    assert blanks == {
        "secret_key",
        "app_base_url",
        "cors_origins",
        "metrics_token",
    }  # what the owner fills in
    filled = {
        **{k: v for k, v in values.items() if v != ""},
        "secret_key": PRODUCTION_BASE["secret_key"],
        "app_base_url": "https://demo.example",
        "cors_origins": ["https://demo.example"],
        "metrics_token": PRODUCTION_BASE["metrics_token"],
        "environment": "production",  # the compose file sets it
        # The fixture's synthetic production URL, pointed at a demo database.
        "database_url": PRODUCTION_BASE["database_url"].rsplit("/", 1)[0] + "/codecoach_demo",
    }
    s = Settings(**filled)
    assert (s.demo_mode, s.ai_provider, s.execution_enabled, s.guest_retention_days) == (
        True,
        "offline",
        False,
        1,
    )


def test_the_compose_file_takes_the_database_name_from_one_variable():
    text = (ROOT / "deploy/docker-compose.production.yml").read_text()
    compose = yaml.safe_load(text)
    assert compose["services"]["db"]["environment"]["POSTGRES_DB"] == "${CODECOACH_DB:-codecoach}"
    urls = re.findall(r"DATABASE_URL: (\S+)", text)
    assert urls and all(u.endswith("@db:5432/${CODECOACH_DB:-codecoach}") for u in urls), urls
    assert "-d codecoach" not in text  # the health check reads the name too
