"""Content metadata, trust labels, issue reports and triage."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

ContentType = Literal["question", "problem"]
ReportCategory = Literal[
    "ambiguous_wording",
    "incorrect_example",
    "outdated_guidance",
    "wrong_career_topic",
    "accessibility",
    "technical_bug",
    "other",
]
ReportStatus = Literal["open", "investigating", "resolved", "not_actionable"]
MAX_DETAILS = 2000
MAX_EXCERPT = 1500
MAX_NOTE = 1000


class TrustLabel(APIModel):
    key: Literal[
        "generated", "authored", "not_expert_reviewed", "reference_verified", "tests_not_checked", "corrected"
    ]
    text: str


class ContentChange(APIModel):
    version: int
    note: str
    significant: bool
    at: datetime


class ContentMeta(APIModel):
    """What a learner should know about where this content came from and its state."""

    content_type: ContentType
    content_id: str
    version: int
    version_label: str = Field(description="e.g. 'Version 2' or 'Test version 3'")
    career: str | None
    topic: str | None
    level: str | None
    status: Literal["active", "retired"]
    retired_reason: str | None
    labels: list[TrustLabel]
    changes: list[ContentChange] = Field(description="Published corrections, oldest first")


class QuestionVersionOut(APIModel):
    version: int
    title: str
    prompt: str


class ReportIn(APIModel):
    content_type: ContentType
    content_id: str = Field(min_length=1, max_length=160, description="'track/question_id' or a problem slug")
    content_version: int = Field(ge=1, description="The version the reporter saw")
    category: ReportCategory
    details: str = Field(default="", max_length=MAX_DETAILS)
    context: Literal["content", "feedback"] = "content"
    answer_id: str | None = Field(default=None, max_length=36, description="Feedback reports: your answer")
    excerpt: str | None = Field(
        default=None, max_length=MAX_EXCERPT, description="Only what you reviewed and chose to attach"
    )


class MyReport(APIModel):
    """A reporter's view: their own words and the public outcome, never internal notes."""

    id: str
    content_type: ContentType
    content_id: str
    content_title: str
    content_href: str | None
    content_version: int
    category: ReportCategory
    context: Literal["content", "feedback"]
    details: str
    excerpt: str | None
    status: ReportStatus
    resolution: str | None
    created_at: datetime
    updated_at: datetime


class AuditEntry(APIModel):
    action: str
    actor: str | None
    detail: dict
    internal_note: str | None
    created_at: datetime


class AdminReport(MyReport):
    reporter: str = Field(description="Who reported it: display name or 'A learner'; never an email")
    duplicate_of: str | None
    duplicates: list[str]
    current_version: int


class AdminReportDetail(AdminReport):
    audit: list[AuditEntry]
    meta: ContentMeta


class ReportGroup(APIModel):
    content_type: ContentType
    content_id: str
    content_title: str
    open_count: int
    reports: list[AdminReport]


class StatusIn(APIModel):
    status: ReportStatus
    resolution: str | None = Field(default=None, max_length=MAX_NOTE, description="Shown to the reporter")
    internal_note: str | None = Field(default=None, max_length=MAX_NOTE, description="Admins only")
    include_duplicates: bool = True


class DuplicateIn(APIModel):
    duplicate_of: str | None = Field(description="Another report's id, or null to ungroup")
    internal_note: str | None = Field(default=None, max_length=MAX_NOTE)


class CorrectionIn(APIModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    prompt: str | None = Field(default=None, min_length=10, max_length=2000)
    tips: list[str] | None = Field(default=None, max_length=8)
    outline: list[str] | None = Field(default=None, max_length=10)
    change_note: str = Field(
        min_length=5, max_length=MAX_NOTE, description="Plain language, shown to learners"
    )
    significant: bool = True
    report_ids: list[str] = Field(default_factory=list, max_length=50)
    internal_note: str | None = Field(default=None, max_length=MAX_NOTE)


class RetireIn(APIModel):
    reason: str = Field(min_length=5, max_length=MAX_NOTE, description="Shown to learners")
    report_ids: list[str] = Field(default_factory=list, max_length=50)
    internal_note: str | None = Field(default=None, max_length=MAX_NOTE)


class RestoreIn(APIModel):
    internal_note: str | None = Field(default=None, max_length=MAX_NOTE)
