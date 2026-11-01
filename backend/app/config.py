"""Application settings, loaded from environment variables (or a local .env file).

Every secret (SECRET_KEY, ANTHROPIC_API_KEY, database password) is read here, on the
server, from the environment. Nothing secret is hardcoded or ever sent to the browser.
See .env.example at the repository root for the full list.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me-0000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CodeCoach AI"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # PostgreSQL is the primary database (docker compose starts one). For a zero-dependency
    # local run you may set DATABASE_URL=sqlite:///./codecoach.db
    database_url: str = "postgresql+psycopg://codecoach:codecoach@localhost:5432/codecoach"
    # Create tables + seed problems at startup. Production runs `alembic upgrade head` and
    # the seed command explicitly instead.
    auto_migrate: bool = True

    # --- Auth -----------------------------------------------------------------------------
    secret_key: str = Field(default=_INSECURE_DEFAULT_SECRET, min_length=32)
    access_token_ttl_minutes: int = Field(default=60, ge=5, le=60 * 24)
    allow_guest_sessions: bool = True
    # Per-IP attempts per minute for login/register (brute-force protection).
    auth_rate_limit_per_minute: int = 10

    # Comma-separated list, e.g. "http://localhost:5173,https://codecoach.example.com"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- AI coach ---------------------------------------------------------------------------
    # "offline": curated hint ladder + static analysis; no API key, deterministic, free.
    # "anthropic": Claude via the provider adapter (falls back to offline on errors).
    ai_provider: Literal["offline", "anthropic"] = "offline"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high"] = "low"
    ai_daily_request_limit: int = Field(default=50, ge=0)
    ai_max_code_chars: int = Field(default=12_000, ge=500)

    # --- Code execution ---------------------------------------------------------------------
    # When enabled, submissions are queued in the database and judged by the worker process
    # (python -m app.worker), which sends code to the isolated runner service. The API process
    # itself never executes submitted code. See docs/SECURITY.md §4.
    execution_enabled: bool = False
    runner_url: str = "http://localhost:8100"
    runner_token: str | None = None
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

    # --- Observability ----------------------------------------------------------------------
    metrics_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.environment == "production":
            if self.secret_key == _INSECURE_DEFAULT_SECRET:
                raise ValueError("SECRET_KEY must be set to a unique random value in production")
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must list explicit origins in production")
        if self.execution_enabled and (not self.runner_token or len(self.runner_token) < 32):
            raise ValueError("EXECUTION_ENABLED=true requires RUNNER_TOKEN (at least 32 characters)")
        if self.ai_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
