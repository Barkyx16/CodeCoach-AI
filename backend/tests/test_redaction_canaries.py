"""Synthetic canaries through the failure paths added in this batch, checked in what an operator
actually sees. Every value here is fake and exists only to be looked for. tests/test_log_redaction.py,
test_email_transport.py and test_preflight.py cover the older paths; docs/PRIVACY.md maps the sinks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings
from app.services.preflight import render, run_preflight
from tests.conftest import PRODUCTION_BASE

BACKEND = Path(__file__).resolve().parents[1]
CANARY = "CANARY-7f3a9-not-a-real-secret"


def cli(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.cli", *args],
        cwd=BACKEND,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize("command", ["backup", "restore"])
def test_an_unreachable_database_is_one_clear_line_without_the_password(tmp_path, command):
    """Before: a raw SQLAlchemy traceback. Now one line with the driver's reason, never the URL."""
    url = f"postgresql+psycopg://canary_user:{CANARY}@127.0.0.1:1/codecoach"
    recipients = tmp_path / "r.txt"
    recipients.write_text("age1" + "q" * 58 + "\n")
    if command == "backup":
        done = cli(
            "backup-database", "--out", str(tmp_path / "b"), "--recipients", str(recipients), DATABASE_URL=url
        )
    else:
        dump = tmp_path / "x.dump.age"
        dump.write_bytes(b"x")
        (tmp_path / "x.manifest.json").write_text('{"format": "codecoach-backup/1"}')
        done = cli(
            "restore-database",
            str(dump),
            "--identity",
            str(recipients),
            DATABASE_URL=url,
            RESTORE_DATABASE_URL=url,
        )
    out = done.stdout + done.stderr
    assert done.returncode != 0
    assert CANARY not in out
    assert "Traceback" not in out, out[-400:]
    # Before this batch, an incomplete manifest was a raw KeyError traceback; now it's a refusal.
    assert "Backup failed" in out or "Not restored" in out


def test_the_preflight_never_prints_a_configured_value():
    s = Settings(
        **{
            **PRODUCTION_BASE,
            "smtp_username": "u",
            "smtp_password": CANARY + "-smtp",
            "metrics_token": CANARY + "-metrics" * 2,
        },
        _env_file=None,
    )
    from sqlalchemy import create_engine

    os.environ["FORWARDED_ALLOW_IPS"] = "10.9.8.7"  # a value, not a secret, but still never shown
    try:
        checks = run_preflight(s, engine=create_engine("sqlite://"))
    finally:
        del os.environ["FORWARDED_ALLOW_IPS"]
    text = render(checks) + render(checks, as_json=True)
    for value in (CANARY, PRODUCTION_BASE["secret_key"], "10.9.8.7"):
        assert value not in text


def test_a_settings_error_names_the_setting_not_its_value():
    with pytest.raises(ValueError) as caught:
        Settings(**{**PRODUCTION_BASE, "secret_key": CANARY}, _env_file=None)  # too weak for production
    assert "secret_key" in str(caught.value).lower() and CANARY not in str(caught.value)


def test_the_production_image_writes_no_visitor_addresses_to_its_logs():
    """uvicorn's access log writes each visitor's IP and full path on every request. The app
    logs requests itself without either, so the image turns uvicorn's off (docs/PRIVACY.md)."""
    cmd = next(
        line
        for line in (BACKEND / "Dockerfile").read_text().splitlines()
        if line.startswith('CMD ["uvicorn"')
    )
    assert '"--no-access-log"' in cmd
