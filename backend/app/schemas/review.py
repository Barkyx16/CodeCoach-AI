"""Post-interview review, single-question retries with comparison, and the spaced review queue."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models import InterviewStatus
from app.schemas.careers import AnswerOut, AttemptComparison
from app.schemas.common import APIModel
from app.schemas.disputes import DisputeNote
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
    key: str = Field(
        default="",
        description="Stable within this interview: what it was suggested from (a missed point, a dimension). "
        "Accepting it uses this key, so accepting again finds the same action.",
    )
    title: str
    why: str
    evidence: list[EvidenceLink]
    practice: PracticeAction
    action_id: str | None = Field(default=None, description="The action you accepted from it, if any")
    dispute: DisputeNote | None = Field(
        default=None,
        description="Some answers it's drawn from have this point disputed (docs/DISPUTES.md): counted, said, "
        "and not used to choose the retry",
    )


class DisputedPoint(APIModel):
    """A point the summary didn't suggest because every answer missing it has it disputed."""

    key: str = Field(description="The improvement's key it would have had (point:<label>)")
    label: str
    missing: int = Field(description="Answers in this interview that missed it")
    disputed: int = Field(description="Of those, how many you disputed")
    text: str
    dispute: DisputeNote


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
    conditions_note: str | None = Field(
        default=None,
        description="A question the round never reached because it ended early: nothing recorded",
    )


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
    disputed_points: list[DisputedPoint] = Field(
        default_factory=list,
        description="Not suggested because of feedback you disputed (docs/DISPUTES.md); the feedback itself is "
        "unchanged",
    )
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
    comparable: bool = Field(
        description="Whether the two scores may be set side by side as a change, by the comparison contract "
        "(docs/COMPARING_ATTEMPTS.md)"
    )
    comparability_note: str = Field(
        description="The contract's explanation (or why there's nothing to compare)"
    )
    classification: AttemptComparison | None = Field(
        default=None, description="The original and the latest retry, classified by the comparison contract"
    )
    improved: list[str] = Field(description="Points the latest attempt covers that the original missed")
    still_missing: list[str]
    newly_missing: list[str] = Field(description="Points the original covered that the latest misses")
    score_change: int | None


class ReviewAdd(APIModel):
    track: str = Field(max_length=64)
    question_id: str = Field(max_length=64)
    session_id: str | None = Field(default=None, max_length=36)
    criterion: str | None = Field(
        default=None,
        max_length=200,
        description="The one feedback point it's saved for (a summary's improvement); a dispute on that point "
        "then holds it like a dispute on the whole feedback",
    )


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
    dispute: DisputeNote | None = Field(
        default=None,
        description="Disputed: why it's here comes only from feedback you disputed (it's under `disputed`, not "
        "scheduled); or, on a scheduled item, one of its reasons does (it keeps the others)",
    )
    criterion: str | None = Field(
        default=None,
        description="The one feedback point it was saved for, or null for the whole answer: a dispute on that "
        "point holds it like a dispute on the whole feedback",
    )
    recounted: str | None = Field(
        default=None,
        description="Set when a dispute changed when it's due: the ladder was recounted without the disputed "
        "scores, and this says what changed (it's also the last sentence of `why`)",
    )


class ReviewQueue(APIModel):
    due: list[ReviewQueueItem]
    upcoming: list[ReviewQueueItem]
    disputed: list[ReviewQueueItem] = Field(
        default_factory=list,
        description="Not scheduled: every reason it's here comes from feedback you disputed (docs/DISPUTES.md). "
        "Counting that feedback again puts it back",
    )
    ladder_days: list[int]
    note: str
