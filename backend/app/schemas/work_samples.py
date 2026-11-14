"""Work-sample practice: briefs, drafts and the artifacts sent for feedback."""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey, SaveReplay, save_replay_field, update_key_field

MAX_SECTION = 4000


class WorkSampleSummary(APIModel):
    id: str
    title: str
    format_label: str
    careers: list[str]


class WorkSampleSectionOut(APIModel):
    id: str
    label: str
    hint: str


class WorkSampleBrief(APIModel):
    """Everything the learner needs to write the artifact; not the reference artifact."""

    id: str
    version: int
    title: str
    format: str
    format_label: str
    careers: list[str]
    scenario: str
    audience: str
    purpose: str
    facts: list[str]
    required: list[str] = Field(description="The points the brief asks for, by name")
    sections: list[WorkSampleSectionOut] = Field(description="Empty: one plain message")
    min_words: int
    max_words: int
    review_status: str
    scope_note: str


class WorkSampleDraftIn(APIModel):
    sections: dict[str, str] = Field(default_factory=dict)
    expected_revision: int = Field(ge=0, description="0 for the first save")
    client_request_id: OptionalKey = update_key_field()


class WorkSampleDraftOut(APIModel):
    save_replay: SaveReplay | None = save_replay_field()
    brief_id: str
    sections: dict[str, str]
    revision: int
    updated_at: datetime | None


class WorkSampleAttemptIn(APIModel):
    sections: dict[str, str]
    revision_of: str | None = Field(default=None, description="The attempt this revises, if any")


class WorkSampleAttemptOut(APIModel):
    id: str
    brief_id: str
    brief_version: int
    current_version: int | None
    title: str
    format_label: str
    sections: dict[str, str]
    section_labels: dict[str, str]
    feedback: dict[str, Any]
    reference: dict[str, str] = Field(
        description="One good approach, shown after an attempt; wording needn't match"
    )
    revision_of: str | None
    created_at: datetime


class WorkSampleAttemptSummary(APIModel):
    id: str
    brief_version: int
    covered: int
    total: int
    revision_of: str | None
    created_at: datetime
