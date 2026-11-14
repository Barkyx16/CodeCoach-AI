"""Launch preflight: one command that checks the configuration it runs in, and says for each
check whether it's ready, blocked, optional or unverified, and why.

    python -m app.cli preflight [--connect-email] [--backup-manifest FILE] [--json]

- ready: checked here, and it holds.
- blocked: checked here, and launch should wait until it's fixed.
- optional: not needed to launch (an extra that's off, by choice).
- unverified: can't be proven from here. The reason names what would prove it.

It reads settings by name and presence, never by value. It connects to the database and, only
with --connect-email, to the mail server (connect, TLS, sign in; nothing is sent). It makes no
paid call, sends no email, changes nothing and deploys nothing. Passing unit tests isn't one of
its checks: it looks at this environment. docs/LAUNCH.md is the runbook around it.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings

READY, BLOCKED, OPTIONAL, UNVERIFIED = "ready", "blocked", "optional", "unverified"


@dataclass
class Check:
    area: str
    status: str
    reason: str


def _settings_checks(s: Settings) -> list[Check]:
    out = []
    prod = s.environment == "production"
    out.append(
        Check(
            "configuration",
            READY if prod else BLOCKED,
            "ENVIRONMENT=production, and every production start-up guard passed (they run when the settings load)"
            if prod
            else f"ENVIRONMENT={s.environment}: the production guards (secret strength, https links, "
            "SMTP with TLS, no SQLite, no AUTO_MIGRATE) only apply with ENVIRONMENT=production",
        )
    )
    secrets = [("SECRET_KEY", True)]
    if s.email_backend == "smtp":
        secrets += [("SMTP_PASSWORD", bool(s.smtp_password)), ("SMTP_USERNAME", bool(s.smtp_username))]
    if s.metrics_enabled:
        secrets.append(("METRICS_TOKEN", bool(s.metrics_token)))
    if s.ai_provider == "anthropic":
        secrets.append(("ANTHROPIC_API_KEY", bool(s.anthropic_api_key)))
    if s.execution_enabled:
        secrets.append(("RUNNER_TOKEN", bool(s.runner_token)))
    missing = [n for n, present in secrets if not present]
    out.append(
        Check(
            "secrets",
            BLOCKED if missing else READY,
            ("missing: " + ", ".join(missing))
            if missing
            else "present (names only): " + ", ".join(n for n, _ in secrets),
        )
    )
    out.append(_client_address_check(os.environ.get("FORWARDED_ALLOW_IPS")))
    https = s.app_base_url.startswith("https://")
    out.append(
        Check(
            "links",
            READY if https else BLOCKED,
            "APP_BASE_URL is https, so emailed links can't be read in transit"
            if https
            else "APP_BASE_URL isn't https: emailed codes and links would point at an insecure address",
        )
    )
    return out


def _client_address_check(trusted: str | None) -> Check:
    """Rate limits are per client address. uvicorn believes X-Forwarded-For only from
    FORWARDED_ALLOW_IPS (default 127.0.0.1). The value isn't printed: only whether it's set."""
    if not trusted:
        return Check(
            "client addresses",
            UNVERIFIED,
            "FORWARDED_ALLOW_IPS isn't set, so only a proxy on 127.0.0.1 is believed. Behind any other proxy "
            "(Docker's published ports included) every visitor shares the proxy's address and its sign-in "
            "rate limit. Set it to the proxy's address; the production compose file does (docs/STORAGE.md)",
        )
    if "*" in [part.strip() for part in trusted.split(",")]:
        return Check(
            "client addresses",
            UNVERIFIED,
            "FORWARDED_ALLOW_IPS=*: any client's X-Forwarded-For is believed. Safe only if nothing but the "
            "proxy can reach the API's port; otherwise a client can pick its own rate-limit address",
        )
    return Check(
        "client addresses",
        READY,
        "FORWARDED_ALLOW_IPS is set (not shown), so client addresses come from the trusted proxy's "
        "X-Forwarded-For",
    )


def _mail_checks(s: Settings, connect: bool) -> list[Check]:
    out = []
    if s.email_backend != "smtp":
        out.append(
            Check(
                "mail transport", BLOCKED, f"EMAIL_BACKEND={s.email_backend}: nothing is sent (docs/EMAIL.md)"
            )
        )
        return out
    if s.smtp_tls_mode == "none":
        out.append(Check("mail transport", BLOCKED, "SMTP_SECURITY=none: mail would travel unencrypted"))
    elif not connect:
        out.append(
            Check(
                "mail transport",
                UNVERIFIED,
                f"SMTP set up ({s.smtp_tls_mode}, host and credentials present); not contacted: re-run with --connect-email",
            )
        )
    else:
        from app.services.email import SmtpEmailSender

        try:
            stages = SmtpEmailSender(s).check()
            out.append(
                Check(
                    "mail transport",
                    READY,
                    "the mail server answered: " + ", ".join(stages) + " (nothing sent)",
                )
            )
        except Exception as exc:  # noqa: BLE001 - reported by class, never with a secret
            out.append(
                Check("mail transport", BLOCKED, f"the mail server couldn't be used: {type(exc).__name__}")
            )
    out.append(
        Check(
            "mail delivery",
            UNVERIFIED,
            "a server accepting mail isn't delivery: send one test (`check-email --send-test`), check the inbox "
            "and spam folder, and the provider's SPF/DKIM/DMARC status for the sender domain",
        )
    )
    return out


def _database_checks(s: Settings, engine: Any, session_factory: Callable[[], Session]) -> list[Check]:
    from app.api.routes.health import schema_state
    from app.db.rls import rls_status
    from app.db.roles import engine_role_report, least_privilege_problems

    out = []
    if engine.dialect.name != "postgresql":
        out.append(
            Check(
                "database", BLOCKED, "SQLite: a file on this server's disk; use PostgreSQL (docs/STORAGE.md)"
            )
        )
        return out
    try:
        with session_factory() as db:
            db.execute(text("SELECT 1"))
            state = schema_state(db)
    except Exception as exc:  # noqa: BLE001
        out.append(Check("database", BLOCKED, f"unreachable: {type(exc).__name__}"))
        return out
    out.append(Check("database", READY, "PostgreSQL answers"))
    out.append(
        Check(
            "migrations",
            READY if state == "current" else BLOCKED,
            {
                "current": "the schema is at this code's migration head",
                "behind": "the schema is older than this code: run the migrate job (alembic upgrade head)",
                "newer": "the schema is newer than this code: deploy the newer code, or restore",
                "unmanaged": "no migration ledger (made by create_all): production must be migrated with alembic",
            }.get(state, state),
        )
    )
    status = rls_status(engine)
    report = engine_role_report(engine) or {}
    problems = least_privilege_problems(report)
    if status.get("role_bypasses_rls") or status.get("missing"):
        out.append(
            Check(
                "row-level security",
                BLOCKED,
                "not enforced: "
                + (
                    "the role bypasses it"
                    if status.get("role_bypasses_rls")
                    else f"missing on {status['missing']}"
                ),
            )
        )
    else:
        out.append(
            Check("row-level security", READY, f"enforced on {len(status.get('protected', []))} tables")
        )
    out.append(
        Check(
            "database role",
            BLOCKED if problems else READY,
            (f"{report.get('role')} " + "; ".join(problems))
            if problems
            else f"{report.get('role')} owns nothing and can't create objects (least privilege)",
        )
    )
    return out


def _backup_check(manifest: Path | None) -> Check:
    if manifest is None:
        return Check(
            "backups",
            UNVERIFIED,
            "no backup schedule can be seen from here: pass --backup-manifest with the newest manifest, "
            "and rehearse a restore (docs/BACKUP.md)",
        )
    try:
        data = json.loads(manifest.read_text())
        made = datetime.fromisoformat(data["created_at"])
    except Exception:  # noqa: BLE001
        return Check("backups", BLOCKED, "that file isn't a readable backup manifest")
    age = datetime.now(UTC) - made
    if age > timedelta(hours=26):
        return Check("backups", BLOCKED, f"the newest backup is {age.days} days {age.seconds // 3600} h old")
    return Check(
        "backups",
        UNVERIFIED,
        f"a backup from {int(age.total_seconds() // 3600)} h ago exists; recovery is proven only by a restore rehearsal",
    )


def _jobs_checks(s: Settings, session_factory: Callable[[], Session]) -> list[Check]:
    from app.models import EmailJob

    out = []
    if s.background_jobs_in_api:
        out.append(
            Check(
                "background jobs",
                READY,
                "the API runs the outbox and housekeeping (guest clean-up, token and counter purges) itself; "
                "no judge needed",
            )
        )
    else:
        out.append(
            Check(
                "background jobs",
                UNVERIFIED,
                "BACKGROUND_JOBS_IN_API=false: emails and housekeeping need `python -m app.worker` running",
            )
        )
    try:
        with session_factory() as db:
            held = db.scalar(select(func.count()).select_from(EmailJob).where(EmailJob.status == "held"))
            stuck = db.scalar(
                select(func.count())
                .select_from(EmailJob)
                .where(
                    EmailJob.status.in_(("pending", "sending")),
                    EmailJob.next_attempt_at < datetime.now(UTC) - timedelta(minutes=15),
                )
            )
            failed = db.scalar(
                select(func.count())
                .select_from(EmailJob)
                .where(
                    EmailJob.status == "failed", EmailJob.created_at > datetime.now(UTC) - timedelta(days=1)
                )
            )
    except Exception as exc:  # noqa: BLE001
        out.append(Check("outbox", UNVERIFIED, f"couldn't read the outbox: {type(exc).__name__}"))
        return out
    if held:
        out.append(
            Check(
                "outbox",
                BLOCKED,
                f"{held} emails held after a restore: review them with `email-quarantine`, then release or "
                "suppress them (a rehearsal's can only be suppressed over SMTP)",
            )
        )
    elif stuck:
        out.append(
            Check("outbox", BLOCKED, f"{stuck} emails overdue by 15+ minutes: is anything processing jobs?")
        )
    elif failed:
        out.append(
            Check(
                "outbox",
                BLOCKED,
                f"{failed} emails failed in the last 24 h: `email-status`, then `email-retry --failed`",
            )
        )
    else:
        out.append(Check("outbox", READY, "nothing overdue, no failures in the last 24 h"))
    return out


def _capability_checks(s: Settings) -> list[Check]:
    out = []
    if s.ai_provider == "offline":
        out.append(
            Check("AI coach", OPTIONAL, "the built-in coach; Claude isn't enabled (AI_PROVIDER=offline)")
        )
    else:
        out.append(
            Check(
                "AI coach",
                UNVERIFIED,
                "AI_PROVIDER=anthropic with a key present; not called (a paid request). Ask for one hint after launch",
            )
        )
    if not s.execution_enabled:
        out.append(Check("code execution", OPTIONAL, "off (EXECUTION_ENABLED=false): code is saved, not run"))
    else:
        out.append(
            Check(
                "code execution",
                UNVERIFIED,
                "enabled; prove the sandbox end to end with `python -m app.cli judge-check`",
            )
        )
    return out


def run_preflight(
    s: Settings,
    *,
    connect_email: bool = False,
    backup_manifest: Path | None = None,
    engine: Any = None,
) -> list[Check]:
    from app.db.session import make_engine, make_session_factory

    own = engine is None
    engine = engine or make_engine(s.database_url, pool_timeout=5)
    try:
        factory = make_session_factory(engine)
        checks = _settings_checks(s)
        checks += _mail_checks(s, connect_email)
        checks += _database_checks(s, engine, factory)
        checks.append(_backup_check(backup_manifest))
        checks += _jobs_checks(s, factory)
        checks += _capability_checks(s)
        return checks
    finally:
        if own:
            engine.dispose()


def render(checks: list[Check], as_json: bool = False) -> str:
    if as_json:
        return json.dumps([asdict(c) for c in checks], indent=2)
    width = max(len(c.area) for c in checks)
    lines = [f"{c.status.upper():<10} {c.area:<{width}}  {c.reason}" for c in checks]
    counts = {k: sum(c.status == k for c in checks) for k in (READY, BLOCKED, OPTIONAL, UNVERIFIED)}
    lines.append("")
    lines.append(", ".join(f"{v} {k}" for k, v in counts.items()))
    lines.append(
        "Not launch-ready while anything is blocked. Unverified checks need the evidence each names."
        if counts[BLOCKED]
        else "Nothing blocked here. Unverified checks still need the evidence each names before launch."
    )
    return "\n".join(lines)
