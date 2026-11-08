"""Application settings, loaded from environment variables (or a local .env file).

Every secret (SECRET_KEY, ANTHROPIC_API_KEY, database password) is read here, on the
server, from the environment. Nothing secret is hardcoded or ever sent to the browser.
See .env.example at the repository root for the full list.
"""

import math
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Where settings files are read from, lowest priority first: the repository root's .env (what
# .env.example and docker compose use), backend/.env, then .env in the current directory. Real
# environment variables override all of them.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILES = (str(_BACKEND_DIR.parent / ".env"), str(_BACKEND_DIR / ".env"), ".env")

_INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me-0000"
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}
# Words that mark a value someone typed as a placeholder rather than generated.
_PLACEHOLDER_WORDS = (
    "change",
    "example",
    "placeholder",
    "insecure",
    "dev-only",
    "your-",
    "secret-key",
    "default",
)
# Database passwords that ship in this repository's examples (compose, .env.example, CI).
_DEFAULT_DB_PASSWORDS = {"codecoach", "postgres", "password", "changeme"}


def weak_secret_reason(value: str) -> str | None:
    """Why a production signing secret looks hand-typed or guessable, or None if it looks
    generated. A rough check: it catches placeholders and repetitive strings, not every weak key.
    `python -c "import secrets; print(secrets.token_urlsafe(48))"` always passes."""
    if len(value) < 32:
        return "is shorter than 32 characters"
    lowered = value.lower()
    if any(w in lowered for w in _PLACEHOLDER_WORDS):
        return "looks like a placeholder"
    distinct = len(set(value))
    if distinct < 12 or len(value) * math.log2(distinct) < 128:
        return "is too repetitive to be random"
    return None


def _address_domain(address: str) -> str:
    """The domain of an address like 'Name <user@example.com>' (lowercase; '' if there is none)."""
    from email.utils import parseaddr

    _, addr = parseaddr(address)
    return addr.rpartition("@")[2].strip().lower() if "@" in addr else ""


def default_db_password(url: str) -> bool:
    """True if DATABASE_URL uses one of the example passwords from this repository."""
    if url.startswith("sqlite"):
        return False
    parsed = urlparse(url)
    return parsed.password is not None and parsed.password.lower() in _DEFAULT_DB_PASSWORDS


def check_runner_url(url: str) -> None:
    """The runner receives untrusted code and a bearer token: plain HTTP is only allowed to this
    machine or to a single-label name on a private container network (e.g. http://runner:8100).
    Anything else must be https:// (or reached through an SSH tunnel to localhost)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme not in ("http", "https") or not host:
        raise ValueError("RUNNER_URL must be an http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("RUNNER_URL must not contain credentials; use RUNNER_TOKEN")
    if parsed.scheme == "http" and host not in _LOOPBACK and "." in host:
        raise ValueError(
            "RUNNER_URL must use https:// for a remote judge (plain http is only allowed for localhost or a "
            "private container name like http://runner:8100). From a Mac, use an SSH tunnel to localhost or a TLS proxy."
        )


class Settings(BaseSettings):
    # hide_input_in_errors: a settings error at startup must never print the values it was given
    # (the whole input, API keys included, would otherwise appear in the traceback).
    # env_ignore_empty: a blank line copied from .env.example (`SECRET_KEY=`) means "not set".
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        env_ignore_empty=True,
    )

    app_name: str = "CodeCoach AI"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # PostgreSQL is the primary database (docker compose starts one). For a zero-dependency
    # local run you may set DATABASE_URL=sqlite:///./codecoach.db
    database_url: str = Field(
        default="postgresql+psycopg://codecoach:codecoach@localhost:5432/codecoach",
        repr=False,  # it carries the database password
        exclude=True,
    )
    # Create tables + seed problems at startup. Production runs `alembic upgrade head` and
    # the seed command explicitly instead, and refuses AUTO_MIGRATE=true. Unset means on outside
    # production.
    auto_migrate_setting: bool | None = Field(default=None, alias="auto_migrate")

    # --- Auth -----------------------------------------------------------------------------
    # Signs access tokens and keys the email-code and refresh-recovery HMACs. Secret values are
    # SecretStr: printing the settings shows '**********', never the value.
    secret_key: SecretStr = Field(default=SecretStr(_INSECURE_DEFAULT_SECRET), min_length=32)
    # Rotation: after changing SECRET_KEY, put the old one here (comma-separated) until every
    # token it signed has expired (REFRESH_TOKEN_TTL_DAYS at most). They're accepted when
    # checking, never used to sign. docs/SECURITY.md "Rotating SECRET_KEY".
    secret_key_previous: Annotated[list[SecretStr], NoDecode] = []
    # Short-lived access tokens (kept in browser memory only) plus a rotating refresh token in
    # an HttpOnly cookie that JavaScript can never read.
    access_token_ttl_minutes: int = Field(default=15, ge=5, le=60 * 24)
    refresh_token_ttl_days: int = Field(default=30, ge=1, le=90)
    # Secure cookies need HTTPS. Unset means: secure in production, not in development/tests.
    refresh_cookie_secure: bool | None = None
    allow_guest_sessions: bool = True
    # Guest (demo) accounts with no activity for this many days are deleted with their data
    # (python -m app.cli prune-guests, or daily by the judge worker). 0 keeps them forever.
    guest_retention_days: int = Field(default=30, ge=0)
    # Per-IP attempts per minute for sign-in, registration, password reset, verification and
    # other account changes (one bucket per client address; IPv6 grouped by /64).
    auth_rate_limit_per_minute: int = 10
    # Wrong passwords for one account in 15 minutes, from any addresses, before sign-in to it
    # pauses (credential stuffing spread over many IPs). Password reset still works.
    login_failures_per_account: int = Field(default=20, ge=1)
    # Session refreshes per client address per minute (every open tab refreshes).
    refresh_rate_limit_per_minute: int = Field(default=60, ge=1)
    # Exports and backup restores (preview or apply) per user per hour: each builds or parses
    # all of a user's data.
    exports_per_hour: int = Field(default=20, ge=1)
    restores_per_hour: int = Field(default=20, ge=1)
    # Written interview answers graded per user per hour (offline grading is cheap; this bounds storage).
    practice_answers_per_hour: int = 60
    # Shared answer links (per client IP / per user). The link secret is 256 bits, so these bound
    # abuse and load rather than being what stops guessing.
    share_opens_per_10_minutes: int = 120
    share_feedback_per_hour: int = 20
    shares_created_per_hour: int = 30
    # Content issue reports per user per hour.
    content_reports_per_hour: int = 10
    # "database": shared by every API replica and survives restarts. "memory": one process only.
    # Behind a reverse proxy, also set FORWARDED_ALLOW_IPS to the proxy's address so uvicorn
    # uses the real client IP from X-Forwarded-For (otherwise everyone shares the proxy's IP).
    rate_limit_backend: Literal["database", "memory"] = "database"

    # --- Email (password reset) ---------------------------------------------------------------
    # Public URL of the web app, used to build links in emails.
    app_base_url: str = "http://localhost:5173"
    # "console" logs emails (development), "file" writes them to EMAIL_FILE_DIR (tests/e2e),
    # "smtp" sends them. Production must use smtp: the others would expose reset links.
    email_backend: Literal["console", "file", "smtp"] = "console"
    email_file_dir: str = "./outbox"
    email_from: str = "CodeCoach AI <no-reply@localhost>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True
    # How the connection to the mail server is protected: "starttls" (usually port 587), "ssl"
    # (implicit TLS, usually port 465) or "none" (a local test server only; production refuses it).
    # Unset: starttls, or none if SMTP_STARTTLS=false. The server's certificate and hostname are
    # always verified; SMTP_CA_BUNDLE only adds a private CA to trust (e.g. an internal relay).
    smtp_security: Literal["starttls", "ssl", "none"] | None = None
    smtp_ca_bundle: str | None = None
    smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)
    email_verification_ttl_hours: int = Field(default=48, ge=1, le=24 * 14)

    # Comma-separated list, e.g. "http://localhost:5173,https://codecoach.example.com"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- AI coach ---------------------------------------------------------------------------
    # "offline": curated hint ladder + static analysis; no API key, deterministic, free.
    # "anthropic": Claude via the provider adapter (falls back to offline on errors).
    ai_provider: Literal["offline", "anthropic"] = "offline"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high"] = "low"
    ai_daily_request_limit: int = Field(default=50, ge=0)
    # Calls to a paid provider running at once in one API process. When all are busy, the free
    # offline coach answers at once (labelled as a fallback) instead of queueing: a slow provider
    # can't tie up every database connection and worker thread. Each user has one AI request in
    # flight at a time (PostgreSQL), which also makes the daily budget exact under concurrency.
    ai_max_concurrent_calls: int = Field(default=8, ge=1, le=256)
    ai_max_code_chars: int = Field(default=12_000, ge=500)

    # --- Code execution ---------------------------------------------------------------------
    # When enabled, submissions are queued in the database and judged by the worker process
    # (python -m app.worker), which sends code to the isolated runner service. The API process
    # itself never executes submitted code. See docs/SECURITY.md §4.
    execution_enabled: bool = False
    runner_url: str = "http://localhost:8100"
    runner_token: SecretStr | None = None
    # A private CA for a TLS runner (e.g. a self-signed internal proxy). Verification is never
    # turned off; this only adds the CA to trust.
    runner_ca_bundle: str | None = None
    # A queued submission older than this means the worker or judge isn't keeping up.
    queue_stall_seconds: int = 120
    judge_time_limit_s: float = Field(default=15.0, gt=0, le=60)
    max_source_chars: int = Field(default=20_000, ge=100)
    submission_rate_limit_per_minute: int = Field(default=6, ge=1)
    max_pending_per_user: int = Field(default=2, ge=1)
    max_queue_depth: int = Field(default=200, ge=1)
    worker_poll_interval_s: float = Field(default=0.5, gt=0)
    judge_stale_after_s: int = Field(default=120, ge=10)
    judge_max_attempts: int = Field(default=2, ge=1, le=5)
    # Run the judge worker as a thread inside the API process. Convenient for local dev and the
    # end-to-end tests; production runs `python -m app.worker` as its own process instead.
    embedded_worker: bool = False
    # Email retries and housekeeping (app/jobs.py) in a thread in each API process. Safe with any
    # number of replicas. Turn off only if `python -m app.worker` runs them instead.
    background_jobs_in_api: bool = True

    # Overload: a request that can't get a database connection within this many seconds is
    # answered 503 `server_busy` with Retry-After, instead of queueing (docs/PERFORMANCE.md).
    db_pool_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    # Connections each process keeps open, and how many more it may open under a burst. Size it
    # so (API processes × (pool + overflow)) + workers stays under PostgreSQL's max_connections
    # (default 100). docs/PERFORMANCE.md "Sizing".
    db_pool_size: int = Field(default=5, ge=1, le=200)
    db_max_overflow: int = Field(default=10, ge=0, le=200)

    # Seconds the shared public catalogue is cached in each process (and by browsers); 0 turns
    # the in-process cache off (responses are still no-store / revalidated). app/http_cache.py.
    response_cache_ttl_seconds: int = Field(default=60, ge=0, le=3600)

    # --- Observability ----------------------------------------------------------------------
    metrics_enabled: bool = True
    # When set, /metrics answers only `Authorization: Bearer <METRICS_TOKEN>` (anything else gets
    # 404, so it isn't discoverable). Required in production while metrics are on: the counts are
    # operational detail (routes, error rates, queue depth) that the public doesn't need.
    metrics_token: SecretStr | None = None
    # Recent traces kept in memory for the admin lookup (GET /api/v1/admin/traces/{id}). Spans are
    # also written to the log either way. 0 traces turns the in-memory store off.
    trace_store_max_traces: int = Field(default=500, ge=0, le=20000)
    trace_store_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    # The browser reports how its round actions ended (no answers, no ids beyond trace/request
    # ids) to this API only. Off: the browser sends nothing and the endpoint returns 404.
    ui_telemetry_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        return v

    @field_validator("secret_key_previous", mode="before")
    @classmethod
    def _split_keys(cls, v: object) -> object:
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        # Messages name the setting, never its value.
        for old in self.secret_key_previous:
            if len(old.get_secret_value()) < 32:
                raise ValueError("Each SECRET_KEY_PREVIOUS key must be at least 32 characters")
        if self.environment == "production":
            if self.signing_key == _INSECURE_DEFAULT_SECRET:
                raise ValueError("SECRET_KEY must be set to a unique random value in production")
            for name, key in [("SECRET_KEY", self.signing_key)] + [
                ("SECRET_KEY_PREVIOUS", k.get_secret_value()) for k in self.secret_key_previous
            ]:
                if reason := weak_secret_reason(key):
                    raise ValueError(
                        f"{name} {reason}; generate one with: "
                        'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                    )
            if default_db_password(self.database_url):
                raise ValueError(
                    "DATABASE_URL uses an example password from this repository; set a unique one in production"
                )
            if self.metrics_enabled and (
                not self.metrics_token or len(self.metrics_token.get_secret_value()) < 32
            ):
                raise ValueError(
                    "METRICS_ENABLED=true in production needs METRICS_TOKEN (at least 32 characters) "
                    "for the scraper, or METRICS_ENABLED=false"
                )
            if self.auto_migrate_setting:
                raise ValueError(
                    "AUTO_MIGRATE=true isn't allowed in production: run `alembic upgrade head` and "
                    "`python -m app.cli seed` instead"
                )
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must list explicit origins in production")
            if self.email_backend == "smtp" and self.smtp_tls_mode == "none":
                raise ValueError(
                    "SMTP_SECURITY=none (or SMTP_STARTTLS=false) isn't allowed in production: emailed reset "
                    "links would cross the network unencrypted. Use starttls or ssl"
                )
            if _address_domain(self.email_from) in ("", "localhost"):
                raise ValueError(
                    "EMAIL_FROM must be an address on a domain you send from, e.g. "
                    "'CodeCoach AI <no-reply@example.com>' (not @localhost)"
                )
            if self.email_backend != "smtp" or not self.smtp_host:
                raise ValueError(
                    "Production needs EMAIL_BACKEND=smtp and SMTP_HOST (other backends expose reset links)"
                )
            if not self.app_base_url.startswith("https://"):
                raise ValueError("APP_BASE_URL must be https in production (it goes into emailed links)")
            if self.refresh_cookie_secure is False:
                raise ValueError("REFRESH_COOKIE_SECURE can't be false in production (cookies need HTTPS)")
        if self.execution_enabled and (
            not self.runner_token or len(self.runner_token.get_secret_value()) < 32
        ):
            raise ValueError("EXECUTION_ENABLED=true requires RUNNER_TOKEN (at least 32 characters)")
        if self.execution_enabled:
            check_runner_url(self.runner_url)
        if self.ai_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        return self

    @property
    def auto_migrate(self) -> bool:
        if self.auto_migrate_setting is not None:
            return self.auto_migrate_setting
        return self.environment != "production"

    @property
    def smtp_tls_mode(self) -> str:
        if self.smtp_security is not None:
            return self.smtp_security
        return "starttls" if self.smtp_starttls else "none"

    @property
    def signing_key(self) -> str:
        """The current SECRET_KEY: the only key anything is signed with."""
        return self.secret_key.get_secret_value()

    @property
    def verification_keys(self) -> list[str]:
        """Keys accepted when checking a signature: the current one first, then previous ones."""
        return [self.signing_key, *(k.get_secret_value() for k in self.secret_key_previous)]

    @property
    def runner_token_value(self) -> str:
        return self.runner_token.get_secret_value() if self.runner_token else ""

    @property
    def cookie_secure(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
