from typing import Literal

from pydantic import Field

from app.models import Difficulty
from app.schemas.common import APIModel


class Example(APIModel):
    input: str
    output: str
    explanation: str | None = None


class Param(APIModel):
    name: str
    type: str


class Signature(APIModel):
    method: str
    params: list[Param]
    returns: str


class PublicTestCase(APIModel):
    """Only PUBLIC test cases are ever serialized. Hidden ones stay server-side."""

    id: int
    input: dict
    expected_output: object


ProblemKind = Literal["problem", "debug"]


class ProblemSummary(APIModel):
    slug: str
    title: str
    difficulty: Difficulty
    topics: list[str]
    summary: str


class LabBrief(APIModel):
    """What a debugging exercise says up front. The defect's explanation and the reference repair
    are only in GET /problems/{slug}/lab/explanation, which the page calls when the learner asks."""

    version: int = Field(description="The exercise's version; attempts record the version they started from")
    intended_behavior: str
    reproduction_test_ids: list[int] = Field(description="Public tests the faulty starter fails")
    review_status: str


class LabExplanation(APIModel):
    version: int
    defect_summary: str
    explanation: str
    why_missed: str = Field(description="Why a simple case doesn't show the defect")
    reference_repair: str = Field(
        description="One correct repair; any repair that passes the tests is accepted"
    )
    follow_up: str


class ProblemDetail(ProblemSummary):
    statement: str
    constraints: list[str]
    examples: list[Example]
    starter_code: str
    signature: Signature
    public_tests: list[PublicTestCase]
    hidden_test_count: int = Field(description="How many hidden tests the judge will also run")
    hint_levels: int = Field(description="How many progressive hint levels are available")
    kind: ProblemKind = Field(
        default="problem", description="problem: write a solution; debug: fix the deliberately faulty starter"
    )
    lab: LabBrief | None = Field(default=None, description="Only for a debugging exercise (kind 'debug')")


class TopicCount(APIModel):
    topic: str
    count: int


class DifficultyCounts(APIModel):
    easy: int
    medium: int
    hard: int
