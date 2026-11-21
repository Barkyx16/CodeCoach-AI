"""Runner settings (environment variables). The runner holds NO database credentials and no
application secrets: only the token the API uses to call it."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunnerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Shared secret the API sends as a bearer token. Required.
    runner_token: str = Field(min_length=32)

    # gVisor by default. "runc" (plain Docker) is NOT a security boundary for hostile code and
    # is refused unless explicitly allowed for local development on machines without gVisor.
    sandbox_runtime: str = "runsc"
    allow_insecure_runtime: bool = False
    sandbox_image: str = "codecoach-java-sandbox:21"
    docker_bin: str = "docker"

    # Hard ceilings. Requests may ask for less, never more.
    max_concurrency: int = Field(default=2, ge=1, le=64)
    wall_timeout_s: float = Field(default=20.0, gt=0, le=120)
    memory_mb: int = Field(default=512, ge=128, le=4096)
    heap_mb: int = Field(default=192, ge=64, le=2048)
    pids_limit: int = Field(default=64, ge=16, le=1024)
    cpus: float = Field(default=1.0, gt=0, le=8)
    tmpfs_mb: int = Field(default=64, ge=16, le=1024)
    output_limit_bytes: int = Field(default=64 * 1024, ge=1024, le=4 * 1024 * 1024)
    max_source_bytes: int = Field(default=64 * 1024, ge=1024)

    # Compile and run one trivial program before accepting work. The first sandbox start after
    # boot is much slower (cold image, page cache, JVM), and because time limits are wall-clock,
    # skipping this can hand the first learner a wrong TIME_LIMIT for correct code.
    warmup_on_start: bool = True

    @model_validator(mode="after")
    def _runtime_guard(self) -> "RunnerSettings":
        if self.sandbox_runtime != "runsc" and not self.allow_insecure_runtime:
            raise ValueError(
                f"SANDBOX_RUNTIME={self.sandbox_runtime!r} is not an isolation boundary for untrusted "
                "code. Use runsc (gVisor), or set ALLOW_INSECURE_RUNTIME=true for local development only."
            )
        return self


@lru_cache
def get_settings() -> RunnerSettings:
    return RunnerSettings()  # type: ignore[call-arg]  # values come from the environment
