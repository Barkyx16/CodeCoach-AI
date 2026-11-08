"""Target roles ("Prepare for this role"): the saved posting, its requirements, practice coverage."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel
from app.schemas.roadmap import RoundStart

Category = Literal["required_skill", "preferred_skill", "responsibility", "experience", "tool", "competency"]
Origin = Literal["explicit", "inferred", "user"]
MAX_DESCRIPTION = 20_000


def _strip(v: str | None) -> str | None:
    return v.strip() if isinstance(v, str) else v


class TargetIn(APIModel):
    title: str = Field(min_length=1, max_length=120)
    employer: str | None = Field(default=None, max_length=120)
    description: str = Field(
        min_length=1, max_length=MAX_DESCRIPTION, description="Pasted job description (plain text)"
    )
    track: str | None = Field(default=None, max_length=64, description="Default: your current career")
    interview_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    _strip_title = field_validator("title", "employer", "notes", mode="before")(_strip)

    @field_validator("title", "description")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class TargetPatch(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    employer: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION)
    interview_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None
    selected: bool | None = Field(default=None, description="Make this your active target")


class RequirementIn(APIModel):
    category: Category
    text: str = Field(min_length=2, max_length=300)
    skills: list[str] | None = Field(
        default=None, max_length=6, description="Career skills it maps to (default: matched)"
    )


class RequirementPatch(APIModel):
    category: Category | None = None
    text: str | None = Field(default=None, min_length=2, max_length=300)
    skills: list[str] | None = Field(default=None, max_length=6)
    removed: bool | None = None


class PracticeLink(APIModel):
    kind: Literal["question", "problem"]
    title: str
    href: str
    why: str
    answered: bool = False
    best_score: int | None = None


class Coverage(APIModel):
    level: Literal["practised", "some", "limited", "gap"]
    label: str
    answers: int
    questions_answered: int
    average_best_score: int | None
    judged_attempts: int = 0
    passed: int = 0


class RequirementOut(APIModel):
    id: str
    category: Category
    text: str
    origin: Origin
    quote: str | None = Field(description="The line of the posting this came from (explicit only)")
    quote_in_description: bool = Field(description="False if the description was edited and the line is gone")
    skills: list[str]
    removed: bool
    coverage: Coverage
    practice: list[PracticeLink]


class AttemptOut(APIModel):
    answer_id: str
    question_title: str
    score: int
    created_at: datetime
    href: str
    requirement_ids: list[str]


class ExperienceIn(APIModel):
    title: str = Field(min_length=1, max_length=120)
    situation: str = Field(default="", max_length=1500)
    action: str = Field(default="", max_length=1500)
    result: str = Field(default="", max_length=1500)
    requirement_ids: list[str] = Field(default_factory=list, max_length=20)


class ExperienceEdit(ExperienceIn):
    expected_revision: int | None = Field(
        default=None,
        ge=1,
        description="The story revision you started from (ExperienceOut.revision). If the story "
        "changed since, 409 stale_revision. Optional for older clients, which keep last-write-wins.",
    )


class ExperienceOut(ExperienceIn):
    id: str
    revision: int = Field(
        default=1, description="This example is a story in the story bank: its revision there"
    )
    created_at: datetime
    updated_at: datetime


class SessionPlan(APIModel):
    title: str
    scope: str = Field(description="What the session covers, shown before it starts")
    round: RoundStart | None = Field(description="Null when there's nothing in the bank to practise")


class TargetSummary(APIModel):
    id: str
    title: str
    employer: str | None
    track: str
    career_title: str
    interview_date: date | None
    archived: bool
    selected: bool
    requirements: int
    gaps: int
    created_at: datetime
    updated_at: datetime


class TargetOut(TargetSummary):
    description: str
    notes: str | None
    extractor: str = Field(description="How requirements were found (rule-based; no AI)")
    requirement_list: list[RequirementOut]
    next_activity: PracticeLink | None
    targeted_session: SessionPlan
    mock_interview: SessionPlan
    recent_attempts: list[AttemptOut]
    experience: list[ExperienceOut]
    days_to_interview: int | None
