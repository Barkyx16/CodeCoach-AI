"""Mock-interview contracts.

`InterviewerReply` and `InterviewEvaluation` double as the structured-output schemas the AI
interviewer must fill, so every provider (offline or Claude) returns the same shapes.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models import Difficulty, InterviewPhase, InterviewStatus, TurnRole
from app.schemas.ai import HintLevel, HintResponse
from app.schemas.careers import AnswerOut
from app.schemas.common import APIModel, OptionalKey
from app.schemas.conditions import AttemptConditions

InterviewKind = Literal["coding", "questions"]
AnswerSource = Literal["typed", "voice", "mixed"]
EngagementState = Literal["following", "more_detail", "explore_further", "not_enough_evidence"]

PHASE_GUIDE: dict[InterviewPhase, str] = {
    InterviewPhase.CLARIFY: "Restate the problem and ask clarifying questions about inputs, outputs and edge cases.",
    InterviewPhase.APPROACH: "Explain your approach out loud before writing code, including alternatives.",
    InterviewPhase.CODING: "Write the solution in the editor and narrate key decisions.",
    InterviewPhase.COMPLEXITY: "State the time and space complexity and justify them.",
    InterviewPhase.WRAP_UP: "Walk through test cases and edge cases, then wrap up.",
}

RubricDimension = Literal[
    "problem_solving", "communication", "code_quality", "complexity_analysis", "testing"
]
RUBRIC_DIMENSIONS: tuple[RubricDimension, ...] = (
    "problem_solving",
    "communication",
    "code_quality",
    "complexity_analysis",
    "testing",
)


class InterviewStart(APIModel):
    kind: InterviewKind = Field(
        default="coding",
        description="coding: one problem with an AI interviewer. questions: five of a career's questions",
    )
    problem_slug: str | None = Field(
        default=None, description="coding: omit to let CodeCoach pick a recommended problem"
    )
    track: str | None = Field(default=None, description="questions: the career (default: your own)")
    difficulty: Difficulty | None = Field(default=None, description="questions: default easy")
    question_ids: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=5,
        description="questions: ask exactly these questions of the career, in this order (a targeted round)",
    )
    purpose: Literal["practice", "baseline"] = Field(
        default="practice",
        description="questions: baseline asks three short questions (knowledge, behavioral, scenario) to "
        "start a practice plan",
    )
    duration_minutes: int = Field(default=30, ge=10, le=60)
    format: Literal["mixed", "behavioral", "situational", "technical", "panel"] = Field(
        default="mixed",
        description="questions: the interview format (see GET /interviews/formats). Can't change once started.",
    )


class FollowupAnswer(APIModel):
    answer: str = Field(min_length=1, max_length=3000)
    source: AnswerSource = Field(default="typed")


class SpeakerOut(APIModel):
    id: str
    title: str = Field(description="A simulated role, never a real person or employer")
    objective: str


class FollowupOut(APIModel):
    question_index: int
    detail: str = Field(description="The detail asked about, e.g. result or ownership")
    question: str
    speaker: SpeakerOut | None
    status: Literal["pending", "answered", "skipped"]
    answer: str | None = None
    covered: bool | None = Field(
        default=None, description="Whether the reply supplied the detail (simple check)"
    )


class FormatSlot(APIModel):
    position: int
    speaker: SpeakerOut | None
    kind_label: str


class FormatOption(APIModel):
    id: Literal["mixed", "behavioral", "situational", "technical", "panel"]
    title: str
    practices: str
    available: bool
    unavailable_reason: str | None
    follow_ups: int = Field(description="Most follow-up questions this format may ask")
    roles: list[SpeakerOut]
    structure: list[FormatSlot] = Field(
        description="Who asks what, in order (no questions or answers revealed)"
    )


class RoundFormatOut(APIModel):
    id: Literal["mixed", "behavioral", "situational", "technical", "panel"]
    title: str
    version: str
    rubric_version: str
    roles: list[SpeakerOut]
    followups_used: int
    followups_max: int
    pending_followup: FollowupOut | None


class RoundAnswer(APIModel):
    question_index: int = Field(ge=0, description="Must be the question currently being asked")
    answer: str = Field(min_length=1, max_length=6000)
    source: AnswerSource = Field(
        default="typed",
        description="How the text was produced. Recorded for review only; it never affects scoring",
    )

    @field_validator("answer")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer must not be blank")
        return v


class RoundSkip(APIModel):
    question_index: int = Field(ge=0)


class Engagement(APIModel):
    """A simulated interviewer's read of one answer, built only from what the answer contains."""

    state: EngagementState
    label: str = Field(description="e.g. 'Looking for more detail'")
    reason: str = Field(description="One actionable sentence that refers to the answer")
    evidence: list[str] = Field(description="The signals found in (or missing from) the answer")


class InterviewMessage(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    code: str | None = Field(default=None, max_length=20_000, description="Current editor contents")
    source: AnswerSource = Field(
        default="typed", description="How the text was produced. Recorded for review only"
    )
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="Send the same id again for the same message (a response lost after the server took it): "
        "you get the current state, the reply included, instead of a second reply. The same id with "
        "other words is refused (409 `idempotency_key_reused`)",
    )
    after_seq: int | None = Field(
        default=None,
        ge=0,
        description="How many turns the transcript had when this was written. If the interview has moved on "
        "since (another tab or device), the message is refused with 409 interview_advanced, not appended",
    )
    approved_context: str | None = Field(
        default=None,
        max_length=128,
        description="The `context_fingerprint` of this message's preview (POST .../message/preview): it's "
        "sent only if what the interviewer would read is still exactly that; otherwise 409 "
        "`context_changed` with a fresh preview, and nothing is stored or spent",
    )

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v


class InterviewFinish(APIModel):
    code: str | None = Field(default=None, max_length=20_000)
    approved_context: str | None = Field(
        default=None,
        max_length=128,
        description="The `context_fingerprint` of the feedback's preview (POST .../feedback/preview with "
        "ending `finished`): the feedback is asked for only if what it reads is still exactly that; "
        "otherwise 409 `context_changed` with a fresh preview, and the interview stays open",
    )


class InterviewAbandon(APIModel):
    approved_context: str | None = Field(
        default=None,
        max_length=128,
        description="The `context_fingerprint` of the feedback's preview with ending `abandoned`, as for finish",
    )


class InterviewMessagePreview(APIModel):
    """The next message as it would be sent (docs/COACH_CONTEXT.md, "The coding interviewer")."""

    message: str = Field(min_length=1, max_length=4000)
    code: str | None = Field(default=None, max_length=20_000, description="Current editor contents")
    after_seq: int | None = Field(default=None, ge=0)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v


class InterviewFeedbackPreview(APIModel):
    """What the end-of-interview feedback would read: on Finish (with the editor's code) or on End
    early (with the code last sent, as ending early always has)."""

    ending: Literal["finished", "abandoned"] = "finished"
    code: str | None = Field(default=None, max_length=20_000, description="Finish only: the editor's code")


class InterviewFeedbackConfirm(InterviewFeedbackPreview):
    """ "I've checked this" (Volume 16, prompt 3): the preview the learner read, by its fingerprint.
    Kept with the interview (its fingerprint, time and the labels it covered, never the text), so a
    time-out can say whether what it read is what was checked."""

    approved_context: str = Field(
        max_length=128,
        description="The `context_fingerprint` of the feedback preview read; refused with 409 "
        "`context_changed` (and a fresh preview) if what the feedback would read has changed since",
    )


class FeedbackCheckOut(APIModel):
    """The check kept: it replaces any earlier one. Confirming sends nothing, scores nothing and
    doesn't stop the clock."""

    at: datetime
    fingerprint: str
    labels: list[str] = Field(description="The parts of what the feedback reads that it covered")
    text: str = Field(description="What happens if time runs out, in one sentence")


class InterviewerReply(BaseModel):
    """What the interviewer says next. Schema for the AI provider."""

    message: str = Field(description="The interviewer's next message: one question or prompt, conversational")
    advance_phase: bool = Field(
        description="True when the candidate has covered the current phase well enough to move on"
    )


class RubricScore(BaseModel):
    dimension: RubricDimension
    score: int = Field(ge=1, le=4, description="1 = needs work, 2 = developing, 3 = solid, 4 = strong")
    evidence: str = Field(description="A specific observation from the transcript or code")


class InterviewEvaluation(BaseModel):
    """End-of-interview feedback. Schema for the AI provider."""

    scores: list[RubricScore] = Field(description="Exactly one score per rubric dimension")
    overall: Literal["needs_work", "developing", "solid", "strong"]
    summary: str
    strengths: list[str]
    improvements: list[str]
    confidence: Literal["low", "medium", "high"]


class TurnOut(APIModel):
    seq: int
    role: TurnRole
    phase: InterviewPhase | None = Field(description="Coding interviews only")
    content: str
    created_at: datetime
    question_index: int | None = None
    source: AnswerSource | None = Field(default=None, description="Candidate turns: typed or voice")
    skipped: bool = False
    engagement: Engagement | None = Field(default=None, description="Candidate turns: simulated engagement")


class RoundQuestion(APIModel):
    index: int
    id: str
    title: str
    prompt: str
    kind: str
    difficulty: Difficulty
    status: Literal["pending", "current", "answered", "skipped"]
    answer: AnswerOut | None = None
    speaker: SpeakerOut | None = Field(default=None, description="Panel interviews: who asks this question")
    followup: FollowupOut | None = None
    conditions_note: str | None = Field(
        default=None, description="For a question the round never reached because it ended early: says so"
    )


class RoundSummary(APIModel):
    answered: int
    skipped: int
    unanswered: int = Field(description="Never reached, e.g. the interview ended early or time ran out")
    average_score: int | None = Field(description="Mean score of answered questions; null if none")
    focus: list[str] = Field(description="Rubric points missed most often, most frequent first")


class InterviewProblem(APIModel):
    slug: str
    title: str
    difficulty: Difficulty


class FeedbackReadItem(APIModel):
    label: str
    chars: int = Field(description="How long it was, in characters, as read (not a copy of the text)")
    notes: list[str] = Field(default_factory=list, description="What was replaced in it, said")


class CheckChange(APIModel):
    """What changed in one part after the check (Volume 17, prompt 1): for the conversation, how many
    messages were sent after it; for another part, how many of its lines were added and removed, and
    the numbers of the added lines in what was read (at most 20; the lines themselves are in your code
    above, never copied here)."""

    label: str
    text: str = Field(description='Said in plain words, e.g. "Your code: 3 lines added, 1 line removed"')
    added: int | None = None
    removed: int | None = None
    added_lines: list[int] = Field(default_factory=list, description="1-based, in the part as read")
    messages_after: int | None = None


class ConfirmedCheck(APIModel):
    """The learner's last "I've checked this" before an unchecked ending (a time-out), compared with
    what the feedback then read: part by part, by label (Volume 16, prompt 3)."""

    at: datetime
    fingerprint: str
    matched: bool = Field(description="What it read is what was checked (how it ended aside)")
    changed: list[str] = Field(default_factory=list, description="The labels of the parts that changed after")
    code_unsent: bool = Field(
        default=False, description="The code checked was in the editor and hadn't been sent when it was read"
    )
    changes: list[CheckChange] = Field(
        default_factory=list,
        description="What changed in each changed part (empty for a check kept before this)",
    )


class FeedbackRead(APIModel):
    """What an interview's feedback read, recorded when it was scored (Volume 15, prompt 7;
    docs/COACH_CONTEXT.md, "What the feedback read"): labels and sizes, never a second copy."""

    recorded: bool = Field(description="False for an interview scored before this was recorded")
    ending: Literal["finished", "abandoned", "time_expired"] | None = None
    checked: bool | None = Field(
        default=None, description="Whether you checked it before it was scored (null: nothing to check)"
    )
    items: list[FeedbackReadItem] = Field(default_factory=list)
    fingerprint: str | None = None
    read_by: str | None = None
    confirmed: ConfirmedCheck | None = Field(
        default=None, description="A check confirmed before an unchecked ending, and whether it still matched"
    )
    text: str = Field(description="What it says, in plain words")


class InterviewHintIn(APIModel):
    """Ask for a hint inside a coding interview (Volume 17, prompt 4): the problem's own ladder, one
    level at a time, recorded with the interview."""

    level: HintLevel = Field(description="1 nudge, 2 concept, 3 pseudocode, 4 full explanation")
    approved_context: str | None = Field(
        default=None,
        max_length=80,
        description="The `context_fingerprint` from POST /ai/hint/preview for this problem, this level and the "
        "code last sent in the interview: sent only if that's still exactly what the coach would read "
        "(409 `context_changed` with a fresh preview otherwise)",
    )
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="One key per request: sent again after a lost response, it gets the same hint back",
    )


class InterviewHintRecord(APIModel):
    """A hint asked for during the interview, as the interview recorded it."""

    level: HintLevel
    level_name: str
    at: datetime = Field(description="When it was shown")
    turn: int = Field(description="How many messages had been exchanged when it was asked for")


class InterviewHintOut(APIModel):
    hint: HintResponse
    record: InterviewHintRecord
    repeated: bool = Field(
        default=False, description="This level was already asked for in this interview: the same hint, again"
    )


class InterviewOut(APIModel):
    id: str
    kind: InterviewKind
    status: InterviewStatus
    phase: InterviewPhase | None
    phase_index: int = Field(description="0-based position of the phase in the arc")
    phase_guide: str | None
    problem: InterviewProblem | None = Field(description="Coding interviews only")
    track: str | None = Field(default=None, description="Question rounds: the career")
    career_title: str | None = None
    questions: list[RoundQuestion] = Field(description="Question rounds only; empty for coding interviews")
    round_summary: RoundSummary | None = Field(default=None, description="Question rounds only")
    round_format: RoundFormatOut | None = Field(default=None, description="Question rounds only")
    duration_seconds: int
    started_at: datetime
    deadline_at: datetime
    ended_at: datetime | None
    seconds_remaining: int
    candidate_turns_remaining: int
    provider: str | None
    turns: list[TurnOut]
    final_code: str | None
    evaluation: InterviewEvaluation | None
    feedback_read: FeedbackRead | None = Field(
        default=None, description="What the feedback read, once the interview is over (null while it's on)"
    )
    feedback_check_margin_seconds: int | None = Field(
        default=None,
        description="How long before time runs out the page offers to check what the feedback will read "
        "(a coding interview in progress; null otherwise)",
    )
    conditions: AttemptConditions | None = Field(
        default=None,
        description="A coding interview once it's over: the in-app help before it ended and its format "
        "(docs/ATTEMPT_CONDITIONS.md). Null while it's on, and for a career interview (each answer has its own)",
    )
    hints: list[InterviewHintRecord] = Field(
        default_factory=list,
        description="Hints asked for in this interview's own hint panel (Volume 17, prompt 4), oldest first",
    )


class InterviewSummary(APIModel):
    id: str
    kind: InterviewKind
    status: InterviewStatus
    problem: InterviewProblem | None
    track: str | None = None
    career_title: str | None = None
    started_at: datetime
    ended_at: datetime | None
    overall: str | None
    average_score: float | None
    # In progress only: enough to recognize the interview and pick it up from any device.
    progress_done: int | None = Field(
        default=None,
        description="In progress: questions answered or skipped (a round), or messages sent (coding)",
    )
    progress_total: int | None = Field(default=None, description="In progress, a round: how many questions")
    seconds_remaining: int | None = Field(default=None, description="In progress: time left, from the server")
    last_activity_at: datetime | None = Field(default=None, description="In progress: the latest turn")
