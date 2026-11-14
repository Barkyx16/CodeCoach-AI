"""Code-review practice: exercises, the learner's findings, and the authored review."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.models import Difficulty
from app.schemas.common import APIModel, OptionalKey, SaveReplay, save_replay_field, update_key_field

MAX_FINDINGS = 20


class ReviewExerciseSummary(APIModel):
    slug: str
    title: str
    difficulty: Difficulty
    problem_slug: str
    problem_title: str


class ReviewPublicTest(APIModel):
    position: int = Field(description="1-based, as the authored review cites it")
    input: dict[str, Any]
    expected_output: Any


class ReviewExerciseOut(APIModel):
    """The exercise as the learner sees it before reviewing: no authored findings."""

    slug: str
    version: int
    title: str
    context: str
    code: str
    line_count: int
    problem_slug: str
    problem_title: str
    difficulty: Difficulty
    statement: str
    constraints: list[str]
    public_tests: list[ReviewPublicTest]
    review_status: str


class FindingIn(APIModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    problem: str = Field(default="", max_length=2000, description="What's wrong")
    consequence: str = Field(default="", max_length=2000, description="What happens because of it")
    repair: str = Field(default="", max_length=2000, description="A change, or a test that would show it")

    @model_validator(mode="after")
    def _ordered(self) -> "FindingIn":
        if self.end_line < self.start_line:
            raise ValueError("end_line comes before start_line")
        return self


class FindingOut(FindingIn):
    excerpt: str = Field(description="The cited lines as they were when the finding was saved")
    anchor: Literal["same", "moved", "missing"] = Field(
        default="same",
        description="For a draft written against an earlier version: whether the cited lines were found again",
    )


class ReviewDraftIn(APIModel):
    findings: list[FindingIn] = Field(default_factory=list, max_length=MAX_FINDINGS)
    summary: str = Field(default="", max_length=2000)
    expected_revision: int = Field(ge=0, description="0 for the first save")
    client_request_id: OptionalKey = update_key_field()


class ReviewDraftOut(APIModel):
    save_replay: SaveReplay | None = save_replay_field()
    slug: str
    exercise_version: int = Field(description="The version the findings were written against")
    current_version: int
    findings: list[FindingOut]
    summary: str
    revision: int
    revealed: bool = Field(description="True once you've seen the authored review for this version")
    updated_at: datetime | None


class ReviewEvidence(APIModel):
    public_test: int
    input: dict[str, Any]
    expected: Any
    actual: Any


class ReviewReferenceFinding(APIModel):
    id: str
    kind: Literal["defect", "observation"]
    lines: list[int]
    related_lines: list[list[int]]
    excerpt: str
    title: str
    explanation: str
    consequence: str
    repair: str
    why_preference: str | None
    evidence: list[ReviewEvidence]


class ReviewReference(APIModel):
    version: int
    findings: list[ReviewReferenceFinding]
    repaired_code: str | None
    debrief: str


class ReviewAttemptIn(APIModel):
    findings: list[FindingIn] = Field(default_factory=list, max_length=MAX_FINDINGS)
    summary: str = Field(default="", max_length=2000)


class ReviewAttemptOut(APIModel):
    id: str
    slug: str
    exercise_version: int
    current_version: int | None = Field(description="None if the exercise is no longer offered")
    title: str
    problem_title: str
    code: str = Field(description="The code as it was reviewed")
    findings: list[FindingOut]
    summary: str
    reference: ReviewReference
    feedback: dict
    after_reveal: bool = Field(description="Written after the authored review had been seen")
    created_at: datetime


class ReviewAttemptSummary(APIModel):
    id: str
    exercise_version: int
    findings: int
    defects_raised: int
    defects_total: int
    after_reveal: bool
    created_at: datetime
