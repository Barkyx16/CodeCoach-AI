"""The launch preflight reports each check as ready, blocked, optional or unverified with a reason,
never prints a secret's value, and only says "ready" for what it actually checked. The full
production-shaped run (owner/app roles, PostgreSQL, verified SMTP) is scripts/rehearse_launch.py,
recorded in docs/LAUNCH.md."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine

from app.config import Settings
from app.models import EmailJob
from app.services import outbox
from app.services.preflight import BLOCKED, OPTIONAL, READY, UNVERIFIED, render, run_preflight
from tests.conftest import PRODUCTION_BASE, TEST_DATABASE_URL, register


def by_area(checks) -> dict[str, tuple[str, str]]:
    return {c.area: (c.status, c.reason) for c in checks}


def test_a_development_setup_is_plainly_not_ready(make_settings, client):
    s = make_settings(environment="development", email_backend="console")
    found = by_area(run_preflight(s, engine=client.app.state.engine))
    assert found["configuration"][0] == BLOCKED and "ENVIRONMENT=development" in found["configuration"][1]
    assert found["mail transport"][0] == BLOCKED and "nothing is sent" in found["mail transport"][1]
    assert found["links"][0] == BLOCKED
    if not TEST_DATABASE_URL:
        assert found["database"][0] == BLOCKED and "SQLite" in found["database"][1]
    assert found["AI coach"][0] == OPTIONAL and found["code execution"][0] == OPTIONAL
    assert found["backups"][0] == UNVERIFIED


def test_production_settings_pass_their_own_checks_and_print_no_secret(make_settings):
    s = Settings(
        **{**PRODUCTION_BASE, "smtp_username": "u", "smtp_password": "smtp-synthetic-secret-value"},
        _env_file=None,
    )
    engine = create_engine(make_settings().database_url)  # the database part is tested below
    checks = run_preflight(s, engine=engine)
    found = by_area(checks)
    assert found["configuration"][0] == READY and found["secrets"][0] == READY and found["links"][0] == READY
    assert found["mail transport"][0] == UNVERIFIED and "--connect-email" in found["mail transport"][1]
    assert found["mail delivery"][0] == UNVERIFIED  # accepted isn't delivered, ever
    text = render(checks) + render(checks, as_json=True)
    for value in (
        "smtp-synthetic-secret-value",
        PRODUCTION_BASE["secret_key"],
        PRODUCTION_BASE["metrics_token"],
    ):
        assert value not in text
    json.loads(render(checks, as_json=True))


def test_missing_secrets_are_named_not_shown(make_settings):
    s = make_settings(
        email_backend="smtp", smtp_host="smtp.example.com", metrics_enabled=True, metrics_token=None
    )
    found = by_area(run_preflight(s, engine=create_engine(s.database_url)))
    assert found["secrets"][0] == BLOCKED
    assert "METRICS_TOKEN" in found["secrets"][1] and "SMTP_PASSWORD" in found["secrets"][1]


@pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl")
def test_connect_email_proves_tls_and_sign_in_or_says_why_not(make_settings, tmp_path):
    from tests.smtp_fake import FakeSMTPServer, make_certificate

    cert = make_certificate(tmp_path, "localhost")
    srv = FakeSMTPServer(certfile=cert[0], keyfile=cert[1])
    try:
        base = dict(email_backend="smtp", smtp_host="localhost", smtp_port=srv.port, smtp_username="u",
                    smtp_password="p-synthetic", smtp_timeout_seconds=2)  # fmt: skip
        trusted = make_settings(**base, smtp_ca_bundle=str(cert[0]))
        found = by_area(
            run_preflight(trusted, connect_email=True, engine=create_engine(trusted.database_url))
        )
        assert found["mail transport"][0] == READY and "certificate verified" in found["mail transport"][1]
        assert srv.messages == []  # nothing sent
        untrusted = make_settings(**base)
        found = by_area(
            run_preflight(untrusted, connect_email=True, engine=create_engine(untrusted.database_url))
        )
        assert found["mail transport"] == (
            BLOCKED,
            "the mail server couldn't be used: SSLCertVerificationError",
        )
    finally:
        srv.close()


def test_a_backup_manifest_is_judged_by_age_and_never_called_recovery(make_settings, tmp_path):
    s = make_settings()
    engine = create_engine(s.database_url)

    def backups(created: datetime | None, raw: str | None = None) -> tuple[str, str]:
        path = tmp_path / "m.json"
        path.write_text(raw if raw is not None else json.dumps({"created_at": created.isoformat()}))
        return by_area(run_preflight(s, backup_manifest=path, engine=engine))["backups"]

    fresh = backups(datetime.now(UTC) - timedelta(hours=3))
    assert fresh[0] == UNVERIFIED and "restore rehearsal" in fresh[1]
    assert backups(datetime.now(UTC) - timedelta(hours=30))[0] == BLOCKED
    assert backups(None, raw="not json")[0] == BLOCKED


def test_overdue_or_failed_emails_block(client, make_settings):
    s = client.app.state.settings
    engine = client.app.state.engine
    assert by_area(run_preflight(s, engine=engine))["outbox"][0] == READY
    data = register(client, email="ada@example.com")
    with client.app.state.session_factory() as db:
        job = outbox.enqueue(db, "verify_email", user_id=data["user"]["id"])
        job.next_attempt_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
    found = by_area(run_preflight(s, engine=engine))
    assert found["outbox"][0] == BLOCKED and "overdue" in found["outbox"][1]
    with client.app.state.session_factory() as db:
        db.get(EmailJob, job.id).status = "failed"
        db.commit()
    assert "failed in the last 24 h" in by_area(run_preflight(s, engine=engine))["outbox"][1]


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="PostgreSQL only")
def test_a_role_that_owns_the_tables_blocks_launch(client):
    found = by_area(run_preflight(client.app.state.settings, engine=client.app.state.engine))
    assert found["database"][0] == READY
    assert found["database role"][0] == BLOCKED and "owns" in found["database role"][1]


def test_the_cli_exits_1_when_anything_is_blocked(client, monkeypatch, capsys):
    from app.cli import main
    from app.config import get_settings

    monkeypatch.setenv("DATABASE_URL", client.app.state.settings.database_url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()
    try:
        assert main(["cli", "preflight"]) == 1
    finally:
        get_settings.cache_clear()
    out = capsys.readouterr().out
    assert "BLOCKED" in out and "Not launch-ready while anything is blocked." in out
