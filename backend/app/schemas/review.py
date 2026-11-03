"""Post-interview review, single-question retries with comparison, and the spaced review queue."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models import InterviewStatus
from app.schemas.careers import AnswerOut
from app.schemas.common import APIModel
from app.schemas.interview import (
    AnswerSource,
    Engagement,
    FollowupOut,
    InterviewKind,
    InterviewProblem,
    RoundFormatOut,
    SpeakerOut,
)

DimensionStatus = Literal["evaluated", "not_evaluated", "not_applicable"]


class EvidenceLink(APIModel):
    item_key: str = Field(description="The timeline item (question or turn) it refers to, or 'code'")
    label: str
    excerpt: str | None = Field(description="The words (or code line) the feedback is about")


class PracticeAction(APIModel):
    label: str
    href: str | None = None
    retry_index: int | None = Field(default=None, description="Retry this question of the interview")


class Improvement(APIModel):
    title: str
    why: str
    evidence: list[EvidenceLink]
    practice: PracticeAction


class Dimension(APIModel):
    name: str = Field(
        description="Answer content, Structure and clarity, Reasoning, Spoken delivery, Code execution"
    )
    status: DimensionStatus
    summary: str
    points: list[str] = Field(default_factory=list)
    evidence: list[EvidenceLink] = Field(default_factory=list)


class ReviewItem(APIModel):
    key: str
    index: int
    title: str
    prompt: str
    kind: str = Field(description="Question kind, or the coding interview phase")
    role: Literal["question", "interviewer", "candidate"]
    status: Literal["answered", "skipped", "not_reached", "said"]
    asked_at: datetime | None = Field(description="Recorded time; null when none was recorded")
    answer_text: str | None
    answered_at: datetime | None
    source: AnswerSource | None
    transcription_note: str | None
    engagement: Engagement | None
    feedback: AnswerOut | None
    dimensions: list[Dimension]
    retries: int
    in_review_queue: bool
    question_id: str | None = None
    speaker: SpeakerOut | None = Field(
        default=None, description="Panel interviews: the simulated role who asked"
    )
    followup: FollowupOut | None = None


class Perspective(APIModel):
    """One simulated panel role's view: the same rubric, applied to the questions that role asked."""

    role: SpeakerOut
    asked: int
    answered: int
    average_score: int | None
    summary: str


class InterviewReview(APIModel):
    id: str
    kind: InterviewKind
    track: str | None
    career_title: str | None
    problem: InterviewProblem | None
    status: InterviewStatus
    status_label: str
    completed: bool = Field(description="True only for interviews that ran to the end")
    started_at: datetime
    ended_at: datetime | None
    elapsed_seconds: int | None = Field(description="From start to end, as recorded")
    time_limit_seconds: int
    notices: list[str] = Field(
        description="Incomplete sessions, missing answers, unavailable feedback, transcription"
    )
    items: list[ReviewItem]
    overall: list[Dimension]
    improvements: list[Improvement] = Field(description="At most three, each grounded in this interview")
    evaluation_available: bool
    evaluator: str | None
    disclaimer: str
    final_code: str | None
    round_format: RoundFormatOut | None = Field(
        default=None, description="Question rounds: format, roles, versions"
    )
    perspectives: list[Perspective] = Field(
        default_factory=list,
        description="Panel only. Not independent judgments: one rubric, split by who asked.",
    )


class RetryIn(APIModel):
    answer: str = Field(min_length=1, max_length=6000)
    source: AnswerSource = "typed"


class Comparison(APIModel):
    question_title: str
    prompt: str
    original: AnswerOut | None = Field(description="The answer given in the interview (never changed)")
    retries: list[AnswerOut] = Field(description="Every retry, oldest first")
    latest: AnswerOut | None
    comparable: bool = Field(description="Original and latest were scored by the same evaluator and rubric")
    comparability_note: str
    improved: list[str] = Field(description="Points the latest attempt covers that the original missed")
    still_missing: list[str]
    newly_missing: list[str] = Field(description="Points the original covered that the latest misses")
    score_change: int | None


class ReviewAdd(APIModel):
    track: str = Field(max_length=64)
    question_id: str = Field(max_length=64)
    session_id: str | None = Field(default=None, max_length=36)


class SnoozeIn(APIModel):
    days: Literal[1, 3, 7]


class ReviewQueueItem(APIModel):
    id: str
    track: str
    career_title: str
    question_id: str
    title: str
    href: str
    due_at: datetime
    due: bool
    why: str = Field(description="Why it's due now, or when and why it will be")
    interval_days: int
    last_score: int | None
    reviews: int
    snoozed: bool


class ReviewQueue(APIModel):
    due: list[ReviewQueueItem]
    upcoming: list[ReviewQueueItem]
    ladder_days: list[int]
    note: str
