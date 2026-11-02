"""SQLAlchemy ORM models. Mirrors the data model in the product blueprint (section 08).

Design notes
- Problems and test cases are seeded from JSON in app/seed/problems and upserted by slug,
  so the curated library is version-controlled and reviewable in pull requests.
- Hidden test cases live only in the database; API schemas never serialize them.
- Every user-owned row (Submission, AIInteraction, ProgressEvent, PracticeSession) carries
  user_id, and every query for those rows filters by it (ownership checks, M08).
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Difficulty(enum.StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TestVisibility(enum.StrEnum):
    PUBLIC = "public"
    HIDDEN = "hidden"


class SubmissionStatus(enum.StrEnum):
    """Judge status model from the blueprint (section 07)."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_LIMIT = "TIME_LIMIT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    @property
    def is_terminal(self) -> bool:
        return self not in (SubmissionStatus.QUEUED, SubmissionStatus.RUNNING)


class SubmissionMode(enum.StrEnum):
    """`submit` is a real attempt (all tests, counts toward progress). `run` checks the code
    against the public tests only, for quick feedback, and never counts as an attempt."""

    SUBMIT = "submit"
    RUN = "run"


class AIAction(enum.StrEnum):
    HINT = "hint"
    REVIEW = "review"
    EXPLAIN_FAILURE = "explain_failure"
    MOCK_INTERVIEW = "mock_interview"


class ProgressEventType(enum.StrEnum):
    OPENED = "opened"
    SUBMITTED = "submitted"
    SOLVED = "solved"
    HINT_USED = "hint_used"
    REVIEW_REQUESTED = "review_requested"
    INTERVIEW_COMPLETED = "interview_completed"


class PracticeMode(enum.StrEnum):
    PRACTICE = "practice"
    INTERVIEW = "interview"  # a coding mock interview (problem + phases)
    QUESTIONS = "questions"  # a mock interview made of one career's written questions


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC timestamps on every database.

    PostgreSQL stores timestamptz natively. SQLite has no timezone support and hands back
    naive datetimes, so we normalize on the way in and out. The API therefore always emits
    ISO-8601 timestamps with an explicit UTC offset, whichever database is used.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("naive datetime; use datetime.now(UTC)")
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


# JSONB on PostgreSQL (binary, indexable), plain JSON elsewhere (SQLite in quick local runs).
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _enum(e: type[enum.Enum], name: str) -> Enum:
    # native_enum=False stores plain strings: portable across SQLite and Postgres and
    # avoids ALTER TYPE migrations when a status is added.
    return Enum(e, name=name, native_enum=False, length=32, values_callable=lambda x: [m.value for m in x])


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Stored lower-cased; NULL for guest (demo) accounts.
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    # "password" for email/password accounts, "guest" for demo sessions. Leaves room for
    # OAuth providers ("github:<id>") without a schema change.
    auth_provider_id: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    # Bumped on logout / password change; tokens carrying an older version are rejected.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Set when the owner clicks the link sent to `email`; cleared whenever the email changes.
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # The job they're preparing for: a slug from app.careers.CATALOG.
    career_track: Mapped[str] = mapped_column(
        String(64), default="software-engineer", server_default="software-engineer"
    )


class RefreshToken(Base):
    """One refresh token. Only its SHA-256 hash is stored, so a database leak can't be replayed.

    Tokens rotate on every use: the old row is marked `used_at` and a new row joins the same
    `family_id`. Presenting a token that was already used (outside a short grace window for
    concurrent tabs) means it was copied, so the whole family is revoked.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # The user's token_version when issued: logout-everywhere / password change invalidate it.
    token_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class PasswordResetToken(Base):
    """Single-use, short-lived password reset link. Only the SHA-256 hash is stored."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RateLimitCounter(Base):
    """Attempts per key per fixed window, shared by every API replica (see services/rate_limit)."""

    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)  # epoch seconds // window length
    count: Mapped[int] = mapped_column(Integer, default=0)


class EmailVerificationToken(Base):
    """Proves the user controls `email`. Only valid while it's still the account's address."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # The same email also carries a 6-digit code (HMAC-ed with the server secret). Only a few
    # wrong guesses are allowed before the code stops working.
    code_hash: Mapped[str] = mapped_column(String(64))
    code_attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[Difficulty] = mapped_column(_enum(Difficulty, "difficulty"), index=True)
    topics: Mapped[list[str]] = mapped_column(JSONType, default=list)
    summary: Mapped[str] = mapped_column(String(240))
    statement: Mapped[str] = mapped_column(Text)
    constraints: Mapped[list[str]] = mapped_column(JSONType, default=list)
    examples: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    starter_code: Mapped[str] = mapped_column(Text)
    # {"method": "max", "params": [{"name": "nums", "type": "int[]"}], "returns": "int"}
    signature: Mapped[dict] = mapped_column(JSONType)
    # Server-only coaching material. Never serialized directly to clients.
    hints: Mapped[list[str]] = mapped_column(JSONType, default=list)
    expected_complexity: Mapped[dict] = mapped_column(JSONType, default=dict)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    test_cases: Mapped[list[TestCase]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", order_by="TestCase.position"
    )


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False  # stop pytest trying to collect this class

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[dict] = mapped_column(JSONType)
    expected_output: Mapped[object] = mapped_column(JSONType)
    visibility: Mapped[TestVisibility] = mapped_column(_enum(TestVisibility, "test_visibility"))
    version: Mapped[int] = mapped_column(Integer, default=1)

    problem: Mapped[Problem] = relationship(back_populates="test_cases")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_user_created", "user_id", "created_at"),
        # The worker's queue scan: oldest QUEUED first.
        Index("ix_submissions_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    language: Mapped[str] = mapped_column(String(16), default="java")
    source_code: Mapped[str] = mapped_column(Text)
    status: Mapped[SubmissionStatus] = mapped_column(
        _enum(SubmissionStatus, "submission_status"), default=SubmissionStatus.QUEUED
    )
    status_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mode: Mapped[SubmissionMode] = mapped_column(
        _enum(SubmissionMode, "submission_mode"), default=SubmissionMode.SUBMIT, server_default="submit"
    )
    # Judge bookkeeping: infrastructure failures are retried (bounded); learner failures never are.
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    judge_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    judged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    test_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    problem: Mapped[Problem] = relationship()
    result: Mapped[ExecutionResult | None] = relationship(
        back_populates="submission", uselist=False, cascade="all, delete-orphan"
    )


class ExecutionResult(Base):
    __tablename__ = "execution_results"

    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True
    )
    runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    # Per-test feedback for PUBLIC tests only; hidden tests are reported as counts.
    public_results: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    stderr_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission: Mapped[Submission] = relationship(back_populates="result")


class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    __table_args__ = (
        Index("ix_ai_user_created", "user_id", "created_at"),
        Index("ix_ai_user_problem_action", "user_id", "problem_id", "action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AIAction] = mapped_column(_enum(AIAction, "ai_action"))
    hint_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    # The structured feedback shown to the learner is kept so they can revisit it.
    # The prompt (which contains their code) is NOT stored: data minimization.
    response: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class InterviewStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ABANDONED = "abandoned"


class InterviewPhase(enum.StrEnum):
    """A realistic coding-interview arc. Phases only move forward."""

    CLARIFY = "clarify"
    APPROACH = "approach"
    CODING = "coding"
    COMPLEXITY = "complexity"
    WRAP_UP = "wrap_up"

    @property
    def next(self) -> InterviewPhase | None:
        order = list(InterviewPhase)
        i = order.index(self)
        return order[i + 1] if i + 1 < len(order) else None


class TurnRole(enum.StrEnum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class PracticeSession(Base):
    """A timed session. mode=interview sessions carry the mock-interview state machine."""

    __tablename__ = "practice_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[PracticeMode] = mapped_column(_enum(PracticeMode, "practice_mode"))
    problem_id: Mapped[int | None] = mapped_column(ForeignKey("problems.id"), nullable=True)
    status: Mapped[InterviewStatus] = mapped_column(
        _enum(InterviewStatus, "interview_status"), default=InterviewStatus.IN_PROGRESS
    )
    phase: Mapped[InterviewPhase | None] = mapped_column(
        _enum(InterviewPhase, "interview_phase"), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    final_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Rubric scores + written feedback, produced once when the interview ends.
    evaluation: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # mode=questions: the career and the questions picked for the round, in order.
    track: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    problem: Mapped[Problem | None] = relationship()
    turns: Mapped[list[InterviewTurn]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewTurn.seq"
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[TurnRole] = mapped_column(_enum(TurnRole, "turn_role"))
    # Coding interviews only; question rounds have no phases.
    phase: Mapped[InterviewPhase | None] = mapped_column(
        _enum(InterviewPhase, "interview_phase"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    # Question rounds: which question this turn asks or answers, and the graded answer it saved.
    question_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_id: Mapped[str | None] = mapped_column(
        ForeignKey("practice_answers.id", ondelete="SET NULL"), nullable=True
    )
    # Candidate turns: how the answer was produced (typed/voice), whether it was skipped, and the
    # simulated-engagement read of it. Never audio: audio is not sent to or stored by the server.
    meta: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    session: Mapped[PracticeSession] = relationship(back_populates="turns")


class ProgressEvent(Base):
    __tablename__ = "progress_events"
    __table_args__ = (
        Index("ix_progress_user_created", "user_id", "created_at"),
        # Events that must happen at most once (e.g. "opened" once per problem per day) carry a key;
        # the unique index makes that atomic even when two requests race. NULL keys never collide.
        Index("uq_progress_user_dedupe", "user_id", "dedupe_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    event_type: Mapped[ProgressEventType] = mapped_column(_enum(ProgressEventType, "progress_event_type"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    dedupe_key: Mapped[str | None] = mapped_column(String(80), nullable=True)


__all__ = [
    "AIAction",
    "AIInteraction",
    "Difficulty",
    "ExecutionResult",
    "PracticeMode",
    "InterviewPhase",
    "InterviewStatus",
    "InterviewTurn",
    "PracticeSession",
    "TurnRole",
    "Problem",
    "ProgressEvent",
    "ProgressEventType",
    "Submission",
    "SubmissionStatus",
    "TestCase",
    "TestVisibility",
    "User",
]


class PracticeAnswer(Base):
    """A written answer to a career interview question, with the feedback it received.

    Questions are generated from the career catalog (app/careers), so they're referenced by
    (track, question_id) rather than a foreign key."""

    __tablename__ = "practice_answers"
    __table_args__ = (Index("ix_practice_user_track_question", "user_id", "track", "question_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    track: Mapped[str] = mapped_column(String(64))
    question_id: Mapped[str] = mapped_column(String(64))
    difficulty: Mapped[str] = mapped_column(String(16))
    answer: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[dict] = mapped_column(JSONType)
    provider: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PracticeGoal(Base):
    """A learner's goals for one career. Every field is optional; a row with only `track` (or no
    row at all) still gets a starter plan. Editing goals never touches recorded progress."""

    __tablename__ = "practice_goals"
    __table_args__ = (UniqueConstraint("user_id", "track", name="uq_goal_user_track"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    track: Mapped[str] = mapped_column(String(64))
    specialty: Mapped[str | None] = mapped_column(String(120), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(16), nullable=True)  # new|early|mid|senior
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    focus_areas: Mapped[list] = mapped_column(JSONType, default=list)
    formats: Mapped[list] = mapped_column(JSONType, default=list)  # written|voice|coding
    # Self-reported confidence per skill (1-5). Kept apart from evaluated scores, never blended.
    confidence: Mapped[dict] = mapped_column(JSONType, default=dict)
    setup_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class PracticePlan(Base):
    """One version of a learner's plan for a career. A new version is made when completed work
    changes the evidence; old versions are kept so changes can be explained."""

    __tablename__ = "practice_plans"
    __table_args__ = (UniqueConstraint("user_id", "track", "version", name="uq_plan_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    track: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    changes: Mapped[list] = mapped_column(JSONType, default=list)  # why this version differs
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    items: Mapped[list[PlanItem]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanItem.position"
    )


class PlanItem(Base):
    __tablename__ = "plan_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("practice_plans.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))
    skill: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text)
    completion: Mapped[str] = mapped_column(Text)  # what counts as done, in plain words
    minutes: Mapped[int] = mapped_column(Integer)
    target: Mapped[dict] = mapped_column(JSONType, default=dict)  # question/problem ids, difficulty
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|done|skipped|replaced
    evidence: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # what completed it
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    plan: Mapped[PracticePlan] = relationship(back_populates="items")


class RoleTarget(Base):
    """A specific role a learner is preparing for, built from a pasted job description.

    The description is untrusted text: it is only stored, shown back and pattern-matched, never
    executed or treated as instructions. Editing it keeps every recorded attempt."""

    __tablename__ = "role_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    track: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(120))
    employer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    interview_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)  # the one active target
    extractor: Mapped[str] = mapped_column(String(32), default="rule-based")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    requirements: Mapped[list[TargetRequirement]] = relationship(
        back_populates="target", cascade="all, delete-orphan", order_by="TargetRequirement.position"
    )


class TargetRequirement(Base):
    __tablename__ = "target_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_id: Mapped[str] = mapped_column(ForeignKey("role_targets.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    # required_skill | preferred_skill | responsibility | experience | tool | competency
    category: Mapped[str] = mapped_column(String(24))
    text: Mapped[str] = mapped_column(String(300))
    origin: Mapped[str] = mapped_column(String(12))  # explicit (in the posting) | inferred | user
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)  # the supporting posting text
    skills: Mapped[list] = mapped_column(JSONType, default=list)  # the career skills it maps to
    removed: Mapped[bool] = mapped_column(Boolean, default=False)

    target: Mapped[RoleTarget] = relationship(back_populates="requirements")


class ExperienceEntry(Base):
    """A learner's own example of their work, written by them and linked to requirements."""

    __tablename__ = "experience_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str | None] = mapped_column(
        ForeignKey("role_targets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(120))
    situation: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    requirement_ids: Mapped[list] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class InterviewRetry(Base):
    """A new attempt at one question of a finished question round. The original answer is never
    changed; the retry is its own graded PracticeAnswer."""

    __tablename__ = "interview_retries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True
    )
    question_index: Mapped[int] = mapped_column(Integer)
    original_answer_id: Mapped[str | None] = mapped_column(
        ForeignKey("practice_answers.id", ondelete="SET NULL"), nullable=True
    )
    retry_answer_id: Mapped[str] = mapped_column(ForeignKey("practice_answers.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ReviewItem(Base):
    """A question saved for spaced review. Due dates follow a fixed ladder (1, 3, 7, 14, 30 days)
    and move only when the question is actually answered again; nothing is ever sent."""

    __tablename__ = "review_items"
    __table_args__ = (Index("ix_review_user_due", "user_id", "due_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    track: Mapped[str] = mapped_column(String(64))
    question_id: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="SET NULL"), nullable=True
    )
    step: Mapped[int] = mapped_column(Integer, default=0)  # index into the interval ladder
    due_at: Mapped[datetime] = mapped_column(UTCDateTime())
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)  # when due_at was last set
    last_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviews: Mapped[int] = mapped_column(Integer, default=0)
    snoozed: Mapped[bool] = mapped_column(Boolean, default=False)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
