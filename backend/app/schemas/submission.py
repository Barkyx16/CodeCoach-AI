from datetime import datetime

from pydantic import Field, field_validator

from app.models import SubmissionMode, SubmissionStatus
from app.schemas.careers import AttemptComparison
from app.schemas.common import APIModel, OptionalKey
from app.schemas.conditions import AttemptConditions
from app.schemas.problem_followups import FollowUpOf


class SubmissionCreate(APIModel):
    problem_slug: str = Field(min_length=1, max_length=80)
    language: str = Field(default="java", pattern="^java$")
    source_code: str = Field(min_length=1)
    mode: SubmissionMode = Field(
        default=SubmissionMode.SUBMIT,
        description="`submit`: judge against all tests and record the attempt. "
        "`run`: public tests only, for quick feedback; never counts as an attempt.",
    )
    follows_up_submission_id: str | None = Field(
        default=None,
        max_length=36,
        description="Made from a reviewed follow-up offer (docs/FOLLOW_UPS.md): your passed submission of the "
        "problem this one follows. Stored once, on a submit; its verdict stays its own",
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
    conditions: AttemptConditions | None = Field(
        default=None,
        description="The in-app help shown for this problem and version before this attempt "
        "(docs/ATTEMPT_CONDITIONS.md). It changes no verdict.",
    )


class ComparedSubmission(APIModel):
    """The earlier submission a submission is compared with, as it was judged."""

    id: str
    status: SubmissionStatus
    created_at: datetime
    passed_count: int | None = None
    total_count: int | None = None
    hidden_passed: int | None = None
    hidden_total: int | None = None


class SubmissionComparison(APIModel):
    """A finished submission beside the previous judged one of the same problem and mode, by the one
    comparison contract (docs/COMPARING_ATTEMPTS.md, "Coding submissions"). Both verdicts are given
    as judged; nothing says one improved on the other."""

    previous: ComparedSubmission
    comparison: AttemptComparison


class SubmissionDetail(SubmissionOut):
    source_code: str
    starting_code: str | None = Field(
        default=None, description="A debugging exercise's faulty code as it was when this attempt was made"
    )
    lab_version: int | None = Field(
        default=None, description="The debugging exercise's version for this attempt"
    )
    compared: SubmissionComparison | None = Field(
        default=None,
        description="Once judged: the previous judged submission of the same problem and mode, and how "
        "the two compare. None when there's no earlier one, or while this one is being judged",
    )
    follows_up: FollowUpOf | None = Field(
        default=None,
        description="A follow-up to a different problem (docs/FOLLOW_UPS.md): which one, never compared with it",
    )


class SubmissionListItem(APIModel):
    id: str
    problem_slug: str
    problem_title: str
    mode: SubmissionMode
    status: SubmissionStatus
    created_at: datetime
    duration_ms: int | None = Field(default=None, description="Judge runtime, once execution is enabled")
    conditions: AttemptConditions | None = None
    outcome_text: str | None = Field(
        default=None,
        description="How it compares with the previous judged one, in History's words, or that it's the first; "
        "none while it's being judged or when the judge couldn't run it (docs/COMPARING_ATTEMPTS.md)",
    )
