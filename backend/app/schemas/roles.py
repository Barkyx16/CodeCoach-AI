"""Target roles ("Prepare for this role"): the saved posting, its requirements, practice coverage."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel
from app.schemas.freshness import Freshness, SourceReviewIn
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
    version: int = Field(
        default=1, description="1, plus one for each substantive edit (docs/REQUIREMENT_VERSIONS.md)"
    )
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
    requirement_versions: dict[str, int | None] = Field(
        default_factory=dict,
        description="Each linked requirement's version when this was answered (null: not recorded)",
    )


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
        "changed since, 409 stale_revision with the saved fields (details.current). Optional for older "
        "clients, which keep last-write-wins.",
    )


class RequirementLink(APIModel):
    requirement_id: str
    linked_version: int | None = Field(description="The version it was linked to; null: not recorded")
    current_version: int
    status: Literal["current", "earlier_wording", "not_recorded", "removed"]
    label: str = Field(description="About the link, never the learner, e.g. 'Linked to an earlier wording'")
    reused_from: int | None = Field(
        description="Deliberately reused for the current wording, from this version"
    )
    story_freshness: Freshness | None = Field(
        default=None,
        description="Whether the story changed since it was linked, in a way that matters "
        "(docs/STORY_FRESHNESS.md). Separate from the requirement's own version above.",
    )


class StoryLinksReviewIn(SourceReviewIn):
    requirement_ids: list[str] = Field(
        min_length=1, max_length=20, description="The story's links to review, all with the same decision"
    )


class ExperienceOut(ExperienceIn):
    id: str
    requirement_links: list[RequirementLink] = Field(default_factory=list)
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


class LinkedAction(APIModel):
    id: str
    title: str


class ActionLink(APIModel):
    """An accepted improvement that practises a question this requirement maps to, and the version
    of the requirement it was accepted against."""

    action_id: str
    title: str
    requirement_id: str
    linked_version: int | None = Field(
        description="The version in effect when it was accepted; null: not recorded"
    )
    current_version: int
    status: Literal["current", "earlier_wording", "not_recorded", "removed"]
    label: str = Field(description="About the link, never the learner")
    reused_from: int | None


class TargetOut(TargetSummary):
    description: str
    notes: str | None
    extractor: str = Field(description="How requirements were found (rule-based; no AI)")
    requirement_list: list[RequirementOut]
    requirements_revision: int = Field(
        default=1, description="The requirement set's revision, sent back when it's saved"
    )
    next_activity: PracticeLink | None
    targeted_session: SessionPlan
    mock_interview: SessionPlan
    recent_attempts: list[AttemptOut]
    experience: list[ExperienceOut]
    action_links: list[ActionLink] = Field(
        default_factory=list,
        description="Accepted improvements practising a question a requirement maps to, with their version",
    )
    days_to_interview: int | None


# --- versioned requirements (docs/REQUIREMENT_VERSIONS.md) -------------------------------------------


class RequirementDraft(APIModel):
    id: str | None = Field(
        default=None, max_length=36, description="An existing requirement; omit for a new one"
    )
    category: Category
    text: str = Field(min_length=2, max_length=300)
    removed: bool = False


class SameAs(APIModel):
    index: int = Field(ge=0, description="A new requirement's position in `items`")
    requirement_id: str = Field(
        max_length=36, description="The requirement being removed that it is the same as"
    )


class RequirementSetIn(APIModel):
    """The whole requirement set as you want it, against the revision you loaded."""

    expected_revision: int = Field(ge=1)
    items: list[RequirementDraft] = Field(max_length=60)
    same_as: list[SameAs] = Field(
        default_factory=list, description="Suggested matches you accepted; anything not here stays separate"
    )


class LinkedStory(APIModel):
    id: str
    title: str


class RequirementChange(APIModel):
    index: int
    requirement_id: str | None
    state: Literal["unchanged", "cosmetic", "changed", "added", "removed", "restored"]
    text: str
    previous_text: str | None
    version_from: int | None
    version_to: int | None
    stories: list[LinkedStory] = Field(description="Stories linked to it that this change affects")
    actions: list[LinkedAction] = Field(
        default_factory=list, description="Accepted improvements practising it that this change affects"
    )


class SameAsSuggestion(APIModel):
    index: int
    requirement_id: str
    text: str
    question: str = Field(description="A question for you; nothing is linked unless you say so")


class RevisionPreview(APIModel):
    summary: str = Field(
        description="e.g. '2 changed, 1 added, 1 removed, 5 unchanged' (cosmetic edits count as unchanged)"
    )
    counts: dict[str, int]
    changes: list[RequirementChange]
    suggestions: list[SameAsSuggestion]
    revision: int


class RequirementHistoryEntry(APIModel):
    version: int
    state: Literal["original", "added", "changed", "removed", "restored"]
    text: str
    category: str
    at: datetime | None
    same_as: str | None
