from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey
from app.schemas.conditions import AttemptConditions


class CareerSummary(APIModel):
    slug: str
    title: str
    category: str
    summary: str
    has_coding: bool = Field(description="Also has hands-on coding problems (the code judge)")
    question_count: int
    answer_feedback: Literal["measured", "not_measured"] = Field(
        default="not_measured",
        description="measured: written-answer feedback has been checked against labelled example answers "
        "for this career (app/careers/support.py); not_measured: general structure checks only",
    )


class QuestionSummary(APIModel):
    id: str
    title: str
    prompt: str
    difficulty: str
    kind: str = Field(description="knowledge, behavioral, situational, leadership or motivation")
    best_score: int | None = Field(
        default=None,
        description="Your highest stored score on this question, when signed in, including an answer too "
        "short to score (its stored score is capped). Kept for compatibility; see best_scored.",
    )
    best_scored: int | None = Field(
        default=None,
        description="Your best score among answers long enough to score (app/careers/eligibility.py); None "
        "when you haven't answered or none of your answers could be scored. Prefer this to best_score.",
    )
    score_status: Literal["scored", "too_short", "unknown"] | None = Field(
        default=None,
        description="None: not answered (or signed out). scored: at least one answer has a score. too_short: "
        "answered, but every answer was too short to score. unknown: answered, but how it was graded wasn't "
        "recorded.",
    )


class QuestionDetail(QuestionSummary):
    track: str
    career_title: str
    tips: list[str]
    rubric_labels: list[str] = Field(description="What a strong answer covers (shown after answering)")


class AnswerRequest(APIModel):
    answer: str = Field(min_length=1, max_length=6000)
    story_id: str | None = Field(
        default=None,
        max_length=36,
        description="One of your stories this answer rehearses (it isn't changed)",
    )
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Your key for this request (e.g. a UUID), when the server says it supports them "
        "(`/capabilities` `answer_request_keys`). Resending the same request with the same key returns "
        "the answer it saved (200, `Idempotent-Replayed: true`) instead of saving another; the same key "
        "with a different request is refused (409 `idempotency_key_reused`). Keys belong to your "
        "account: another account's identical key is a different key. Use a new key for a new try.",
    )
    revises_answer_id: str | None = Field(
        default=None,
        max_length=36,
        description="One of your own earlier answers to this same question that this answer revises "
        "(404 if it isn't yours or doesn't exist; 400 `revision_other_question` if it's for another "
        "question). Only set it for an explicit revision.",
    )
    follows_up_answer_id: str | None = Field(
        default=None,
        max_length=36,
        description="Answering an offered follow-up (docs/FOLLOW_UPS.md): your own earlier answer to the "
        "question this one follows up (404 if it isn't yours or doesn't exist; 400 `not_a_follow_up` "
        "if no reviewed relationship links the two questions). Both answers keep their own score.",
    )


class KeyedAnswerRequest(AnswerRequest):
    """The protected route's body: the request key is required (Verification brief 04)."""

    client_request_id: str = Field(
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Your key for this request (required here). Same meaning as on the plain route.",
    )


class FeedbackPoint(APIModel):
    label: str
    covered: bool
    advice: str
    evidence: str | None = Field(
        default=None,
        description="Your own words where it was found, as checked against your answer (none when it "
        "couldn't be checked)",
    )
    span: list[int] | None = Field(
        default=None,
        description="Where the quote is in `answer`: [start, end) in UTF-16 code units (what JavaScript "
        "strings index by). None for older feedback, which stored no position.",
    )
    evidence_status: Literal["verified", "legacy", "omitted"] | None = Field(
        default=None,
        description="verified: the quote is at `span` in your answer; legacy: older feedback, still your "
        "words, position not recorded; omitted: a quote was stored but couldn't be checked, so it isn't "
        "shown. None when the point has no quote.",
    )
    scope_note: str | None = Field(
        default=None,
        description="What the point checks when its wording suggests more (it checks that a subject is "
        "discussed, not that what is said is right)",
    )


class ComparisonReason(APIModel):
    rule: str = Field(
        description="question, scale, source, rubric, question_version, scoring, format or help"
    )
    kind: Literal["incompatible", "unknown", "partial_text", "partial_conditions"]
    text: str


class AttemptComparison(APIModel):
    """One attempt compared with the one before it, by the one comparison contract
    (app/careers/comparability.py; docs/COMPARING_ATTEMPTS.md). The same pair reads the same on
    every page."""

    against: str = Field(
        description="The earlier answer it's compared with (the one it revises, else the one before)"
    )
    outcome: Literal["comparable", "partially_comparable", "incompatible", "unknown"]
    scores_comparable: bool = Field(description="Whether the two scores may be set side by side as a change")
    points_comparable: bool = Field(description="Whether what was written (the points covered) compares")
    reasons: list[ComparisonReason]
    explanation: str
    contract_version: int = Field(description="The version of the comparison rules that decided it")


class AnswerOut(APIModel):
    id: str
    question_id: str
    answer: str
    score: int
    rating: str
    summary: str
    points: list[FeedbackPoint]
    notes: list[str]
    outline: list[str] = Field(description="What a strong answer would include")
    word_count: int
    coach: str = Field(description="Which coach graded it: 'built-in (offline)' or the AI provider")
    created_at: datetime
    content_version: int = Field(default=1, description="The question's version when this was answered")
    story_id: str | None = Field(default=None, description="The story this answer rehearsed, if any")
    rubric_version: str = Field(default="v1", description="The rubric the coach used")
    evidence_level: Literal["sufficient", "insufficient", "unknown"] = Field(
        default="sufficient",
        description=(
            "insufficient: too short to evaluate, so no score should be shown. unknown: an answer stored "
            "without either its evidence level or its word count, so whether it could be scored isn't "
            "known; its score counts nowhere (app/careers/eligibility.py)"
        ),
    )
    track: str | None = Field(default=None, description="The career this answer was written for")
    evaluation_status: Literal["measured", "not_measured"] = Field(
        default="not_measured",
        description="Whether this career's written-answer feedback has been measured (app/careers/support.py)",
    )
    evaluation_note: str = Field(default="", description="One line for the learner about what that means")
    revises_answer_id: str | None = Field(
        default=None,
        description="Your earlier answer to this question that this one explicitly revises (None when it "
        "doesn't, for every answer saved before revision links existed, and when that earlier answer was "
        "deleted). A link says where a try came from; it doesn't make two scores comparable.",
    )
    follows_up_answer_id: str | None = Field(
        default=None,
        description="The earlier answer to a related question this one was offered after (a reviewed follow-up)",
    )
    conditions: AttemptConditions | None = Field(
        default=None,
        description="The in-app help shown for this question and version before this answer "
        "(docs/ATTEMPT_CONDITIONS.md). It changes no score.",
    )
    comparison: AttemptComparison | None = Field(
        default=None,
        description="In a question's list of your answers: this answer compared with the one before it "
        "(none for the first)",
    )


class TrackProgress(APIModel):
    track: str
    answered: int = Field(description="Questions with at least one answer, each counted once")
    strong: int = Field(description="Questions with a best score of 85 or more")
    by_difficulty: dict[str, int]
    total_questions: int
    scored: int = Field(
        default=0, description="Answered questions with at least one answer long enough to score"
    )
    too_short: int = Field(
        default=0, description="Answered questions where every answer was too short to score (no score yet)"
    )
    unknown: int = Field(default=0, description="Answered questions whose grading wasn't recorded (no score)")
