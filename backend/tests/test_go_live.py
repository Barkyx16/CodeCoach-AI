"""Going live (docs/GO_LIVE.md): deploy/setup.sh writes the two settings files with generated
secrets, and what it writes passes the production checks as written, for the demo, the demo with
the judge, and real accounts once the mail settings are filled in. It never prints a secret and
never overwrites a file. The production compose's https proxy and judge are opt-in profiles that
can't break a stack without them, the jobs that run no learner code keep the judge off, and the
Caddyfile serves the app and the API on one origin without exposing /metrics."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "deploy" / "setup.sh"
COMPOSE = ROOT / "deploy" / "docker-compose.production.yml"
CADDYFILE = ROOT / "deploy" / "Caddyfile"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("openssl") is None,
    reason="needs bash and openssl, like the server",
)


def run_setup(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    deploy = tmp_path / "deploy"
    deploy.mkdir(exist_ok=True)
    shutil.copy(SETUP, deploy / "setup.sh")
    env = {k: v for k, v in os.environ.items() if k != "COMPOSE_PROFILES"}
    # Where Docker is installed without gVisor, setup only prints a note: it never stops it.
    return subprocess.run(
        [shutil.which("bash") or "bash", str(deploy / "setup.sh"), *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def api_settings(tmp_path: Path, **extra) -> Settings:
    """The API's settings as the compose file assembles them: .env.app whole, plus the
    environment it sets per container (the app role's database URL, the runner)."""
    prod = read_env(tmp_path / "deploy" / ".env.production")
    app = {k.lower(): v for k, v in read_env(tmp_path / "deploy" / ".env.app").items()}
    app.pop("rate_limit_backend", None)
    values = {
        **app,
        "environment": "production",
        "database_url": f"postgresql+psycopg://codecoach_app:{prod['CODECOACH_APP_PASSWORD']}@db:5432/{prod['CODECOACH_DB']}",
        "runner_url": "http://runner:8100",
        **({"runner_token": prod["RUNNER_TOKEN"]} if "RUNNER_TOKEN" in prod else {}),
        **extra,
    }
    values = {k: v for k, v in values.items() if v != ""}  # env_ignore_empty, as in the container
    if "cors_origins" in values:
        values["cors_origins"] = [values["cors_origins"]]
    return Settings(**values)


def test_the_demo_settings_pass_the_production_checks_as_written(tmp_path):
    out = run_setup(tmp_path, "--domain", "Demo.Example.com")
    assert out.returncode == 0, out.stderr
    prod = read_env(tmp_path / "deploy" / ".env.production")
    app = read_env(tmp_path / "deploy" / ".env.app")
    assert prod["COMPOSE_PROFILES"] == "https"
    assert prod["SITE_ADDRESS"] == "demo.example.com"
    assert prod["PUBLIC_API_URL"] == app["APP_BASE_URL"] == app["CORS_ORIGINS"] == "https://demo.example.com"
    assert prod["CODECOACH_DB"] == "codecoach_demo"  # demo-reset insists on "demo" in the name
    assert (
        app["DEMO_MODE"] == "true" and app["EXECUTION_ENABLED"] == "false" and app["AI_PROVIDER"] == "offline"
    )
    s = api_settings(tmp_path)
    assert s.environment == "production" and s.demo_mode and not s.execution_enabled


def test_secrets_are_generated_unique_never_printed_and_private(tmp_path):
    out = run_setup(tmp_path, "--domain", "demo.example.com", "--judge")
    assert out.returncode == 0, out.stderr
    prod = read_env(tmp_path / "deploy" / ".env.production")
    app = read_env(tmp_path / "deploy" / ".env.app")
    secrets = [
        prod[k]
        for k in (
            "POSTGRES_SUPERUSER_PASSWORD",
            "CODECOACH_OWNER_PASSWORD",
            "CODECOACH_APP_PASSWORD",
            "RUNNER_TOKEN",
        )
    ] + [app["SECRET_KEY"], app["METRICS_TOKEN"]]
    assert all(re.fullmatch(r"[0-9a-f]{64}", v) for v in secrets)  # hex: no escaping in database URLs
    assert len(set(secrets)) == len(secrets)
    for value in secrets:
        assert value not in out.stdout and value not in out.stderr
    for name in (".env.production", ".env.app"):
        mode = stat.S_IMODE((tmp_path / "deploy" / name).stat().st_mode)
        assert mode == 0o600, oct(mode)


def test_the_judge_settings_pass_the_production_checks(tmp_path):
    assert run_setup(tmp_path, "--domain", "demo.example.com", "--judge").returncode == 0
    prod = read_env(tmp_path / "deploy" / ".env.production")
    assert prod["COMPOSE_PROFILES"] == "https,judge"
    s = api_settings(tmp_path)
    assert s.execution_enabled and s.runner_url == "http://runner:8100"


def test_real_accounts_wait_for_the_mail_settings_then_pass(tmp_path):
    out = run_setup(tmp_path, "--domain", "app.example.com", "--mode", "full", "--no-https")
    assert out.returncode == 0, out.stderr
    prod = read_env(tmp_path / "deploy" / ".env.production")
    app = read_env(tmp_path / "deploy" / ".env.app")
    assert prod["COMPOSE_PROFILES"] == "" and prod["CODECOACH_DB"] == "codecoach"
    assert "DEMO_MODE" not in app and app["EMAIL_BACKEND"] == "smtp"
    assert "Fill in SMTP_*" in out.stdout
    with pytest.raises(ValueError):  # the API refuses to start until the provider's settings are in
        api_settings(tmp_path)
    s = api_settings(
        tmp_path,
        smtp_host="smtp.example.com",
        smtp_username="mailer",
        smtp_password="synthetic-smtp-password",
        email_from="CodeCoach AI <no-reply@app.example.com>",
    )
    assert s.environment == "production" and not s.demo_mode


def test_it_never_overwrites_and_refuses_what_isnt_a_host_name(tmp_path):
    assert run_setup(tmp_path, "--domain", "demo.example.com").returncode == 0
    before = (tmp_path / "deploy" / ".env.production").read_text()
    again = run_setup(tmp_path, "--domain", "other.example.com")
    assert again.returncode == 1 and "already exists" in again.stderr
    assert (tmp_path / "deploy" / ".env.production").read_text() == before
    for bad in (
        "https://demo.example.com",
        "demo example.com",
        "demo.example.com:443",
        "demo.example.com/x",
        "-bad.example.com",
    ):
        fresh = tmp_path / bad.replace("/", "_").replace(" ", "_").replace(":", "_")
        fresh.mkdir()
        out = run_setup(fresh, "--domain", bad)
        assert out.returncode != 0 and not (fresh / "deploy" / ".env.app").exists(), bad
    other = tmp_path / "mode"
    other.mkdir()
    assert run_setup(other, "--domain", "demo.example.com", "--mode", "prod").returncode != 0


def test_the_proxy_and_judge_are_opt_in_and_cant_break_a_stack_without_them():
    text = COMPOSE.read_text()
    services = yaml.safe_load(text)["services"]
    assert services["proxy"]["profiles"] == ["https"]
    assert {"80:80", "443:443"} <= set(services["proxy"]["ports"])
    assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in services["proxy"]["volumes"]
    for name in ("sandbox-image", "runner", "worker"):
        assert services[name]["profiles"] == ["judge"], name
    assert "/var/run/docker.sock:/var/run/docker.sock" in services["runner"]["volumes"]
    assert "ports" not in services["runner"]  # reachable on the compose network only
    # Compose interpolates every service, profiled or not: a required ${VAR:?} in one of them
    # would stop `up` for everyone who doesn't use it.
    for name in ("proxy", "sandbox-image", "runner", "worker"):
        assert ":?" not in yaml.safe_dump(services[name]), name
    # Jobs that run no learner code never see the judge's switch on (or need its token).
    for name in ("migrate", "backup"):
        assert services[name]["environment"]["EXECUTION_ENABLED"] == "false", name
    assert services["api"]["environment"]["RUNNER_URL"] == "http://runner:8100"
    # The worker is the app role, like the API: row-level security applies to it too.
    assert "codecoach_app:" in services["worker"]["environment"]["DATABASE_URL"]


def test_the_caddyfile_serves_one_origin_and_keeps_metrics_private():
    caddy = CADDYFILE.read_text()
    assert "{$SITE_ADDRESS}" in caddy
    assert re.search(r"@api path /api/\* /health /health/\*", caddy)
    assert "reverse_proxy api:8000" in caddy and "reverse_proxy web:8080" in caddy
    assert "/metrics" not in re.search(r"@api path[^\n]*", caddy).group(0)
    assert "Strict-Transport-Security" in caddy
