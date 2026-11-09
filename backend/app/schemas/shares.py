"""Sharing an answer with a trusted reviewer, and the structured feedback they leave."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

MAX_NOTE = 500
MAX_FIELD = 1_500
MAX_COMMENT = 600
MAX_COMMENTS = 8
MAX_GUEST_NAME = 60
TOKEN_MIN, TOKEN_MAX = 32, 64

ShareStatus = Literal["active", "closed", "revoked", "expired"]
ShareSourceType = Literal["practice_answer", "interview_answer"]


class ShareSelection(APIModel):
    """What to share from one of your answers. Nothing else from your account is included."""

    answer_id: str = Field(min_length=1, max_length=36, description="One of your graded answers")
    sentences: list[int] | None = Field(
        default=None,
        max_length=400,
        description="Which sentences of the answer to include (0-based); null means all of them",
    )
    include_ai_feedback: bool = Field(
        default=False, description="Add CodeCoach's automated feedback, labelled"
    )
    include_followup: bool = Field(
        default=True, description="Interview answers: add the follow-up and your reply"
    )
    note: str = Field(default="", max_length=MAX_NOTE, description="A short note to your reviewer")


class ShareCreate(ShareSelection):
    expires_in_days: Literal[1, 7, 30] = 7
    acknowledge_link_access: bool = Field(
        description="Must be true: anyone holding the link can see the selected snapshot until it "
        "expires or is revoked"
    )


class SharedSentence(APIModel):
    index: int = Field(description="Position in the original answer: a stable anchor for comments")
    text: str


class SharedQuestion(APIModel):
    title: str
    prompt: str
    kind: str
    difficulty: str


class SharedFollowup(APIModel):
    asked_by: str
    question: str
    answer: str


class SharedPoint(APIModel):
    label: str
    covered: bool


class SharedAIFeedback(APIModel):
    """CodeCoach's automated rubric feedback, included only when the owner chose to."""

    score: int
    rating: str
    summary: str
    points: list[SharedPoint]
    coach: str


class SharedView(APIModel):
    """Exactly what the reviewer sees. Built from the immutable snapshot."""

    kind: ShareSourceType
    career_title: str
    question: SharedQuestion
    excerpt: list[SharedSentence]
    total_sentences: int
    omitted_sentences: int
    followup: SharedFollowup | None
    ai_feedback: SharedAIFeedback | None
    note: str
    answered_on: str = Field(description="The day the answer was written (YYYY-MM-DD)")
    prompts: list[str] = Field(description="The questions the reviewer is asked to answer")


class RecipientView(APIModel):
    status: Literal["active", "closed"]
    expires_at: datetime
    view: SharedView
    reviewer: "ReviewerIdentity | None" = Field(
        description="Who the feedback will be attributed to, when the reviewer is signed in"
    )


class SharePreview(APIModel):
    source_sentences: list[SharedSentence] = Field(description="Every sentence of the answer, to choose from")
    has_followup: bool
    view: SharedView


class ReviewerIdentity(APIModel):
    kind: Literal["account", "guest", "former_account"]
    label: str = Field(description="How the reviewer is named, e.g. 'Grace (signed-in CodeCoach user)'")


class FeedbackComment(APIModel):
    sentence: int = Field(ge=0, le=400, description="Which shared sentence this is about")
    text: str = Field(min_length=1, max_length=MAX_COMMENT)


class FeedbackCommentOut(FeedbackComment):
    quote: str = Field(description="The sentence it refers to, from the snapshot")


class FeedbackIn(APIModel):
    token: str = Field(min_length=TOKEN_MIN, max_length=TOKEN_MAX)
    client_request_id: str = Field(
        min_length=8,
        max_length=64,
        description="A retry with the same id, from the same reviewer with the same words, returns the "
        "first receipt (`duplicate`); anything else under that id is refused (409 `idempotency_key_reused`)",
    )
    clear: str = Field(default="", max_length=MAX_FIELD, description="What was clear?")
    needs_evidence: str = Field(default="", max_length=MAX_FIELD, description="What needs more evidence?")
    next_step: str = Field(default="", max_length=MAX_FIELD, description="One useful next step")
    comments: list[FeedbackComment] = Field(default_factory=list, max_length=MAX_COMMENTS)
    guest_name: str = Field(default="", max_length=MAX_GUEST_NAME, description="Used only when not signed in")


class TokenIn(APIModel):
    token: str = Field(min_length=TOKEN_MIN, max_length=TOKEN_MAX)


class FeedbackOut(APIModel):
    id: str
    reviewer: ReviewerIdentity
    clear: str
    needs_evidence: str
    next_step: str
    comments: list[FeedbackCommentOut]
    created_at: datetime
    useful: bool


class FeedbackReceipt(APIModel):
    """What the reviewer sent, echoed back so they can see it was received."""

    feedback: FeedbackOut
    duplicate: bool = Field(description="True when this was a retry of feedback already received")


class ShareSummary(APIModel):
    id: str
    status: ShareStatus
    kind: ShareSourceType
    career_title: str
    question_title: str
    source_answer_id: str
    created_at: datetime
    expires_at: datetime
    closed_at: datetime | None
    revoked_at: datetime | None
    last_opened_at: datetime | None = Field(description="When the link was last opened by anyone")
    feedback_count: int
    last_feedback_at: datetime | None


class ShareDetail(ShareSummary):
    view: SharedView
    feedback: list[FeedbackOut]
    source_changed: bool = Field(description="The original answer differs from what was shared")
    source_missing: bool = Field(description="The original answer is no longer in your history")


class ShareCreated(APIModel):
    """The link is in here once. Only a hash is stored, so it can be replaced but never shown again."""

    share: ShareDetail
    token: str
    path: str = Field(description="Append to the site's address, e.g. https://example.com/shared#t=…")


class UsefulIn(APIModel):
    useful: bool


RecipientView.model_rebuild()
