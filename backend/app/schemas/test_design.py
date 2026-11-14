"""Test design against authored faulty versions: exercises, cases and run reports."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey

Label = Literal["boundary", "equivalence", "edge", "other"]


class TestDesignSummary(APIModel):
    __test__ = False
    slug: str
    title: str
    summary: str
    variant_count: int


class TestDesignParam(APIModel):
    name: str
    type: Literal["int[]", "int"]


class TestDesignLimits(APIModel):
    max_cases: int
    max_length: int
    min_value: int
    max_value: int


class TestDesignExample(APIModel):
    input: dict[str, Any]
    expected: Any


class TestDesignExercise(APIModel):
    """What the learner sees before running anything: the specification, its shape and limits,
    and how many faulty versions there are. Not the versions or their defects."""

    __test__ = False
    slug: str
    version: int
    title: str
    summary: str
    spec: str
    method: str
    params: list[TestDesignParam]
    returns: Literal["int", "boolean"]
    limits: TestDesignLimits
    examples: list[TestDesignExample]
    variant_count: int
    review_status: str
    execution_enabled: bool = Field(description="False: cases can be written and saved, but not run here")


class TestDesignVariant(APIModel):
    __test__ = False
    key: str = Field(description="A, B, C…: how the run reports name it")
    title: str
    defect: str


class TestCaseIn(APIModel):
    __test__ = False
    input: dict[str, Any]
    expected: Any = Field(description="The output the specification calls for, as you read it")
    label: Label | None = None
    note: str = Field(default="", max_length=500, description="What the case covers, in your words")


class TestDesignRunIn(APIModel):
    __test__ = False
    cases: list[TestCaseIn] = Field(min_length=1, max_length=50)
    client_request_id: OptionalKey = Field(default=None, min_length=8, max_length=64)


class TestDesignRunOut(APIModel):
    __test__ = False
    id: str
    slug: str
    exercise_version: int
    current_version: int | None
    status: Literal["queued", "running", "done", "not_run", "failed"]
    status_detail: str
    cases: list[dict[str, Any]]
    report: dict[str, Any] | None
    created_at: datetime
    judged_at: datetime | None


class TestDesignRunSummary(APIModel):
    __test__ = False
    id: str
    exercise_version: int
    status: str
    cases: int
    caught: int | None
    total: int | None
    created_at: datetime
