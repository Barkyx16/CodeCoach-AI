"""Learn mode: units, the learner's progress events and comprehension checks."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

EventKind = Literal["started", "read", "check_attempted", "check_passed", "practiced"]


class ReferenceOut(APIModel):
    title: str
    publisher: str
    url: str | None = Field(description="Null when no stable link is recorded (links are never guessed)")
    published: str | None
    kind: Literal["external", "repository"]
    note: str | None


class ReviewOut(APIModel):
    status: Literal["author_reviewed", "generated_draft"]
    by: str
    on: str
    note: str


class ExampleOut(APIModel):
    title: str
    intro: str
    code: str | None
    language: str | None
    walkthrough: list[str]


class CheckQuestionOut(APIModel):
    """A check question without its answer: answers are graded on the server."""

    id: str
    prompt: str
    options: list[str]


class ExerciseOut(APIModel):
    prompt: str
    draft_label: str
    guided_steps: list[str] = Field(
        description="Think, concept, example, fuller explanation: revealed in order"
    )
    solution: str = Field(description="Shown only when the learner asks for it, behind a spoiler warning")
    solution_language: str | None


class PracticeOut(APIModel):
    kind: Literal["question", "problem"]
    ref_id: str
    label: str
    href: str


class UnitLink(APIModel):
    id: str
    title: str


class UnitSummary(APIModel):
    id: str
    track: str
    title: str
    skill: str | None
    topics: list[str]
    minutes: int
    objective: str
    prerequisites: list[UnitLink]
    version: int
    review_status: Literal["author_reviewed", "generated_draft"]
    regulated: bool = Field(description="Has a scope and jurisdiction note (e.g. nursing)")


class UnitOut(UnitSummary):
    career_title: str
    changes: list[str] = Field(description="What changed in each version, oldest first")
    scope_note: str | None
    explanation: list[str]
    example: ExampleOut
    mistakes: list[str]
    exercise: ExerciseOut
    check: list[CheckQuestionOut]
    pass_rule: str
    practice: PracticeOut
    references: list[ReferenceOut]
    review: ReviewOut
    question_ids: list[str]


class CareerCoverage(APIModel):
    track: str
    title: str
    units: int


class LearnCatalog(APIModel):
    track: str
    career_title: str
    units: list[UnitSummary]
    coverage_note: str
    careers_with_units: list[CareerCoverage]


class EventOut(APIModel):
    kind: EventKind
    version: int
    at: datetime
    detail: str | None


class NextAction(APIModel):
    kind: Literal["read", "check", "practice", "done"]
    label: str


class UnitProgress(APIModel):
    unit_id: str
    current_version: int
    versions_used: list[int] = Field(description="Unit versions you have events on")
    started: bool
    read: bool = Field(description="Read the current version (reading alone is not mastery)")
    check_attempts: int
    check_passed: bool = Field(description="Passed the check on the current version")
    passed_versions: list[int]
    practiced: bool = Field(
        description="A real answer or submission to the linked practice since you started"
    )
    practiced_evidence: str | None
    events: list[EventOut]
    next_action: NextAction


class EventIn(APIModel):
    kind: Literal["started", "read"]
    version: int = Field(ge=1, description="The unit version on screen")


class CheckIn(APIModel):
    version: int = Field(ge=1)
    answers: dict[str, int] = Field(description="Check question id -> chosen option index")


class CheckItemResult(APIModel):
    id: str
    chosen: int | None
    correct: bool
    answer: int
    explanation: str


class CheckResult(APIModel):
    passed: bool
    correct: int
    total: int
    pass_rule: str
    results: list[CheckItemResult]
    progress: UnitProgress
