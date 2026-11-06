"""Branching scenarios: catalog, attempts, steps and the debrief."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.learn import ReferenceOut, ReviewOut

Quality = Literal["strong", "acceptable", "risky"]


class ScenarioSummary(APIModel):
    id: str
    track: str
    career_title: str
    title: str
    role: str
    objective: str
    minutes: int = Field(description="Author's estimate of the time it takes")
    scope: str
    version: int
    regulated: bool
    validated: bool = Field(
        description="Always false: no scenario has been validated by an outside professional body"
    )
    decisions: int = Field(description="How many choices the longest path asks for")
    endings: int
    review: ReviewOut


class ScenarioDetail(ScenarioSummary):
    references: list[ReferenceOut]
    changes: list[str]


class CareerCount(APIModel):
    track: str
    title: str
    scenarios: int


class ScenarioCatalog(APIModel):
    track: str
    career_title: str
    scenarios: list[ScenarioSummary]
    coverage_note: str
    careers_with_scenarios: list[CareerCount]


class OptionOut(APIModel):
    id: str
    label: str


class NodeView(APIModel):
    """The node the learner is on. Choice quality and feedback are only revealed after choosing."""

    id: str
    kind: Literal["info", "choice", "written"]
    title: str
    text: str
    options: list[OptionOut]


class StepOut(APIModel):
    node_id: str
    kind: Literal["info", "choice", "written"]
    title: str
    text: str
    choice_id: str | None = None
    choice_label: str | None = None
    quality: Quality | None = None
    feedback: str | None = Field(default=None, description="The authored decision rule for this choice")
    response: str | None = None
    covered: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    at: datetime


class Alternative(APIModel):
    label: str
    quality: Quality
    rule: str


class DecisionOut(APIModel):
    step_index: int
    title: str
    chosen: str
    quality: Quality
    rule: str
    alternatives: list[Alternative]


class WrittenOut(APIModel):
    step_index: int
    title: str
    response: str
    covered: list[str]
    missing: list[str]


class Debrief(APIModel):
    outcome: str
    ending_title: str
    ending_text: str
    summary: str
    path: list[str] = Field(description="Titles of the steps you went through, in order")
    decisions: list[DecisionOut]
    strengths: list[str]
    written: list[WrittenOut]
    references: list[ReferenceOut]
    feedback_source: str
    disclaimer: str


class ScenarioAttemptOut(APIModel):
    id: str
    scenario: ScenarioSummary
    version: int
    mode: Literal["assessed", "exploration"]
    parent_id: str | None
    status: Literal["in_progress", "completed"]
    retired: bool = Field(
        description="The scenario has a newer version; this attempt is kept but can't continue"
    )
    current: NodeView | None
    steps: list[StepOut]
    debrief: Debrief | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ScenarioAttemptSummary(APIModel):
    id: str
    scenario_id: str
    title: str
    version: int
    mode: Literal["assessed", "exploration"]
    status: Literal["in_progress", "completed"]
    outcome: str | None
    retired: bool
    created_at: datetime
    completed_at: datetime | None


class StartIn(APIModel):
    mode: Literal["assessed", "exploration"] = "assessed"
    parent_id: str | None = Field(
        default=None, description="Exploration: the completed attempt you're trying another approach to"
    )


class StepIn(APIModel):
    node_id: str = Field(max_length=64, description="The node you're answering (must be the current one)")
    choice_id: str | None = Field(default=None, max_length=64)
    text: str | None = Field(default=None, max_length=2000)
