from datetime import datetime

from pydantic import Field, field_validator

from app.models import SubmissionMode, SubmissionStatus
from app.schemas.common import APIModel, OptionalKey


class SubmissionCreate(APIModel):
    problem_slug: str = Field(min_length=1, max_length=80)
    language: str = Field(default="java", pattern="^java$")
    source_code: str = Field(min_length=1)
    mode: SubmissionMode = Field(
        default=SubmissionMode.SUBMIT,
        description="`submit`: judge against all tests and record the attempt. "
        "`run`: public tests only, for quick feedback; never counts as an attempt.",
    )
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Idempotency key chosen by the client: resending the same request (e.g. after a network "
        "error) returns the original submission instead of judging twice",
    )

    @field_validator("source_code")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_code must not be blank")
        return v


class PublicCaseResult(APIModel):
    """Detailed result for one PUBLIC test. Hidden tests are only ever counted."""

    index: int
    passed: bool
    input: dict | None = None
    expected_output: object | None = None
    actual_output: object | None = None
    exception: str | None = Field(default=None, description="Simple class name, e.g. ArithmeticException")
    exception_message: str | None = None
    missing: bool = Field(default=False, description="The test never reported (crash or time limit first)")
    line: int | None = Field(default=None, description="Line in your code where the exception was thrown")
    runtime_ms: float | None = None


class ExecutionResultOut(APIModel):
    runtime_ms: int | None
    memory_kb: int | None
    passed_count: int
    total_count: int
    hidden_passed: int
    hidden_total: int
    public_results: list[PublicCaseResult]
    stderr_excerpt: str | None = Field(default=None, description="Compiler output (compile errors only)")


class SubmissionOut(APIModel):
    id: str
    problem_slug: str
    problem_title: str
    language: str
    mode: SubmissionMode
    status: SubmissionStatus
    status_detail: str | None
    is_terminal: bool
    execution_enabled: bool
    created_at: datetime
    updated_at: datetime
    result: ExecutionResultOut | None = None


class SubmissionDetail(SubmissionOut):
    source_code: str


class SubmissionListItem(APIModel):
    id: str
    problem_slug: str
    problem_title: str
    mode: SubmissionMode
    status: SubmissionStatus
    created_at: datetime
    duration_ms: int | None = Field(default=None, description="Judge runtime, once execution is enabled")
