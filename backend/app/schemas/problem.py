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


class ProblemSummary(APIModel):
    slug: str
    title: str
    difficulty: Difficulty
    topics: list[str]
    summary: str


class ProblemDetail(ProblemSummary):
    statement: str
    constraints: list[str]
    examples: list[Example]
    starter_code: str
    signature: Signature
    public_tests: list[PublicTestCase]
    hidden_test_count: int = Field(description="How many hidden tests the judge will also run")
    hint_levels: int = Field(description="How many progressive hint levels are available")


class TopicCount(APIModel):
    topic: str
    count: int
