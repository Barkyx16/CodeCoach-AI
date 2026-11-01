from typing import Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_FILES = {"Solution.java", "Main.java"}

RunStatus = Literal["ok", "compile_error", "timeout", "memory_limit", "output_limit", "sandbox_error"]


class RunRequest(BaseModel):
    files: dict[str, str]
    nonce: str = Field(pattern=r"^[0-9a-f]{16,64}$")
    time_limit_s: float | None = Field(default=None, gt=0, le=120)

    @field_validator("files")
    @classmethod
    def exact_files(cls, v: dict[str, str]) -> dict[str, str]:
        if set(v) != ALLOWED_FILES:
            raise ValueError(f"files must be exactly {sorted(ALLOWED_FILES)}")
        return v


class RunResponse(BaseModel):
    status: RunStatus
    exit_code: int | None
    # Raw output goes ONLY to the API, which parses the driver lines and never shows the raw
    # run-phase output to learners (it could contain hidden test inputs the code printed).
    stdout: str
    stderr: str
    compile_output: str | None = None
    run_started: bool
    output_truncated: bool
    duration_ms: int
