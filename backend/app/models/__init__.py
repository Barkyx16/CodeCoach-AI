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
    false,
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
    # Content triage (reports, corrections, retirement). Granted only from the command line
    # (python -m app.cli grant-admin EMAIL); no API can set it.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
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
        UniqueConstraint("user_id", "client_request_id", name="uq_submission_client_request"),
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
    # Set by the client so a retried request (network failure, double send) returns the same
    # submission instead of judging twice. Unique per user.
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # The question's content version when it was answered (None: before versions existed, i.e. 1).
    content_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The learner's own story this answer rehearsed (the story itself is never changed by it).
    story_id: Mapped[str | None] = mapped_column(
        ForeignKey("experience_entries.id", ondelete="SET NULL", name="fk_answer_story"),
        nullable=True,
        index=True,
    )


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
    """A learner's own story: an experience from work, study, volunteering or their own projects,
    written by them in Situation / Task / Action / Result form with an optional reflection.

    One model serves both the story bank and job targets (a story can be linked to one target and
    to that target's requirements), so there are never two diverging copies. Deleting a target
    unlinks its stories; it never deletes them. Every save is kept in `story_revisions`."""

    __tablename__ = "experience_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str | None] = mapped_column(
        ForeignKey("role_targets.id", ondelete="SET NULL", name="fk_experience_target"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120))
    track: Mapped[str | None] = mapped_column(String(64), nullable=True)  # career context
    context: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # work|study|volunteering|personal|other
    situation: Mapped[str] = mapped_column(Text, default="")
    task: Mapped[str] = mapped_column(Text, default="", server_default="")
    action: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    reflection: Mapped[str] = mapped_column(Text, default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")  # private supporting notes
    evidence: Mapped[str] = mapped_column(Text, default="", server_default="")  # optional outcome evidence
    competencies: Mapped[list] = mapped_column(JSONType, default=list, server_default="[]")
    tags: Mapped[list] = mapped_column(JSONType, default=list, server_default="[]")
    question_refs: Mapped[list] = mapped_column(
        JSONType, default=list, server_default="[]"
    )  # "track/question_id"
    short_version: Mapped[str] = mapped_column(Text, default="", server_default="")  # rehearsal, user-written
    long_version: Mapped[str] = mapped_column(Text, default="", server_default="")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    requirement_ids: Mapped[list] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class StoryRevision(Base):
    """A saved version of a story. Restoring one creates a new revision; none is ever changed."""

    __tablename__ = "story_revisions"
    __table_args__ = (UniqueConstraint("story_id", "revision", name="uq_story_revision"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    story_id: Mapped[str] = mapped_column(ForeignKey("experience_entries.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(16))  # created | edited | assisted | restored
    fields: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


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


class Bookmark(Base):
    """A private bookmark on a career question (track + id) or a coding problem (slug)."""

    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "item_type", "track", "ref_id", name="uq_bookmark"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_type: Mapped[str] = mapped_column(String(12))  # question | problem
    track: Mapped[str] = mapped_column(String(64), default="")  # "" for coding problems
    ref_id: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    # Career questions: the content version when saved, so a significant change can be shown later.
    content_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PracticeCollection(Base):
    """A private, ordered set of practice items. Its queue position and "done in this queue" marks
    are separate from mastery: finishing a queue doesn't mean a skill is mastered."""

    __tablename__ = "practice_collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    queue_position: Mapped[int] = mapped_column(Integer, default=0)
    queue_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    items: Mapped[list[CollectionItem]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", order_by="CollectionItem.position"
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "item_type", "track", "ref_id", name="uq_collection_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("practice_collections.id", ondelete="CASCADE"), index=True
    )
    item_type: Mapped[str] = mapped_column(String(12))
    track: Mapped[str] = mapped_column(String(64), default="")
    ref_id: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    queue_done_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    collection: Mapped[PracticeCollection] = relationship(back_populates="items")


class LearnEvent(Base):
    """One step of a learner's progress through a Learn unit, on a specific unit version.

    Kinds are distinct on purpose: started, read, check_attempted, check_passed, practiced. Only
    check_passed (graded by the unit's rubric) and practiced (a real answer or submission) are
    evidence of anything; reading is never mastery. `dedupe_key` makes the once-per-version kinds
    race-free; check attempts have none, so every attempt is kept."""

    __tablename__ = "learn_events"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_learn_event_dedupe"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[str] = mapped_column(String(64), index=True)
    unit_version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Note(Base):
    """A private notebook entry, optionally captured from a question, problem, lesson or interview.

    The source is referenced by stable id (plus the version when one exists) and a title snapshot,
    so a retired source never destroys the note. `excerpt` is a snapshot, not a live reference.
    `revision` increments on every save; a save based on an older revision is refused (409) so
    newer text is never silently replaced. `deleted_at` gives a short undo window before purge."""

    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    reflection: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_track: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt_kind: Mapped[str | None] = mapped_column(String(8), nullable=True)  # quote | code
    key_points: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)  # accepted only
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ScenarioAttempt(Base):
    """One run through a branching scenario, on one scenario version.

    `steps` records every node shown and every decision with the authored feedback as it was at
    the time, so the debrief survives later edits or retirement of the scenario. Attempts are
    append-only: a decision can't be changed; "try another approach" makes a new attempt
    (`mode = exploration`, linked by `parent_id`)."""

    __tablename__ = "scenario_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(12), default="assessed")  # assessed | exploration
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="in_progress")  # in_progress | completed
    current_node: Mapped[str] = mapped_column(String(64))
    steps: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    ending: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Share(Base):
    """A learner's answer, shared for feedback through an unlisted link.

    The link's secret is never stored: only its SHA-256 (`token_hash`), so a database leak doesn't
    expose working links and a lost link can only be replaced (`rotate`), not recovered. What the
    reviewer sees is `snapshot`, built once from the owner's selection and never changed, so later
    edits to the source can't silently change it (`source_digest` lets the owner see that the
    source changed). `revoked_at` turns the link off on the server; `closed_at` keeps it readable
    but stops new feedback. The row and its feedback stay, for the owner only, until the owner
    deletes the share or the account."""

    __tablename__ = "shares"
    __table_args__ = (Index("ix_shares_owner_created", "owner_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    source_type: Mapped[str] = mapped_column(String(20))  # practice_answer | interview_answer
    source_id: Mapped[str] = mapped_column(String(36))  # the PracticeAnswer id
    source_digest: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSONType)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    link_rotated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    feedback: Mapped[list[ShareFeedback]] = relationship(
        back_populates="share", cascade="all, delete-orphan", order_by="ShareFeedback.created_at"
    )


class ShareFeedback(Base):
    """Structured feedback a person left on a share. Human feedback, kept apart from AI scores:
    it never changes the answer, its score, the plan or progress.

    `reviewer_id` is set when the reviewer was signed in with a registered account (their display
    name is read live, so deleting that account leaves "a former CodeCoach user"); otherwise
    `guest_name` is whatever the reviewer typed, shown as unverified."""

    __tablename__ = "share_feedback"
    __table_args__ = (UniqueConstraint("share_id", "client_request_id", name="uq_share_feedback_request"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    share_id: Mapped[str] = mapped_column(ForeignKey("shares.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewer_kind: Mapped[str] = mapped_column(String(8))  # account | guest
    guest_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    clear: Mapped[str] = mapped_column(Text, default="")
    needs_evidence: Mapped[str] = mapped_column(Text, default="")
    next_step: Mapped[str] = mapped_column(Text, default="")
    comments: Mapped[list[dict]] = mapped_column(JSONType, default=list)  # [{sentence, text}]
    client_request_id: Mapped[str] = mapped_column(String(64))
    useful: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    share: Mapped[Share] = relationship(back_populates="feedback")


class ContentReport(Base):
    """A learner's report of a problem with a question, a coding problem or the feedback on an
    answer. Pinned to the content id and version it was made against. Never changes any score.

    `duplicate_of` groups likely duplicates under the first open report; nothing is deleted.
    `resolution` is the plain-language explanation the reporter sees; internal notes live only
    in `content_audit`."""

    __tablename__ = "content_reports"
    __table_args__ = (Index("ix_reports_content", "content_type", "content_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_type: Mapped[str] = mapped_column(String(12))  # question | problem
    content_id: Mapped[str] = mapped_column(String(160))  # "track/question_id" or problem slug
    content_version: Mapped[int] = mapped_column(Integer)
    context: Mapped[str] = mapped_column(String(12), default="content")  # content | feedback
    answer_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )  # feedback reports: whose feedback
    category: Mapped[str] = mapped_column(String(32))
    details: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)  # only what the reporter chose to attach
    status: Mapped[str] = mapped_column(
        String(16), default="open"
    )  # open|investigating|resolved|not_actionable
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of: Mapped[str | None] = mapped_column(
        ForeignKey("content_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ContentAudit(Base):
    """Append-only record of every triage action: who, what, when, and internal notes."""

    __tablename__ = "content_audit"
    __table_args__ = (Index("ix_audit_content", "content_type", "content_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(32))
    content_type: Mapped[str] = mapped_column(String(12))
    content_id: Mapped[str] = mapped_column(String(160))
    report_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    detail: Mapped[dict] = mapped_column(JSONType, default=dict)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ContentVersion(Base):
    """A published correction: the next version of a career question, with the changed fields
    and a short note for learners. Version 1 is the generated original; versions only grow."""

    __tablename__ = "content_versions"
    __table_args__ = (UniqueConstraint("content_type", "content_id", "version", name="uq_content_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String(12))
    content_id: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer)
    fields: Mapped[dict] = mapped_column(JSONType)  # only the corrected fields, e.g. {"prompt": "..."}
    change_note: Mapped[str] = mapped_column(Text)
    significant: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ContentStatus(Base):
    """Retired content: kept readable in history and private collections, but no longer offered
    for practice or assessment. No row means active."""

    __tablename__ = "content_status"

    content_type: Mapped[str] = mapped_column(String(12), primary_key=True)
    content_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    status: Mapped[str] = mapped_column(String(12), default="retired")
    reason: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ContentCheck(Base):
    """Recorded result of an automated check (e.g. the reference solution passing every test).
    Trust labels are shown only from rows like these, never assumed."""

    __tablename__ = "content_checks"
    __table_args__ = (UniqueConstraint("content_type", "content_id", "check", name="uq_content_check"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String(12))
    content_id: Mapped[str] = mapped_column(String(160))
    check: Mapped[str] = mapped_column(String(40))  # e.g. reference_solution
    content_version: Mapped[int | None] = mapped_column(Integer, nullable=True)  # problems: the test version
    passed: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class OnboardingState(Base):
    """Where a learner is in the optional first-session introduction. One row per account,
    created on first use. It records only the learner's choices about the introduction (never
    answer text): whether the guided tour was started, paused, finished or skipped and at which
    step, which start they chose, which careers' format introductions they've seen, and which
    banners they dismissed. Whether they've done a real activity is worked out from their actual
    answers and submissions, not stored here."""

    __tablename__ = "user_onboarding"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # not_started | in_progress | paused | completed | skipped
    tour_status: Mapped[str] = mapped_column(String(16), default="not_started")
    tour_kind: Mapped[str | None] = mapped_column(String(12), nullable=True)  # written | coding
    tour_step: Mapped[int] = mapped_column(Integer, default=0)
    tour_version: Mapped[int] = mapped_column(Integer, default=1)
    start_choice: Mapped[str | None] = mapped_column(
        String(12), nullable=True
    )  # practice | intro | library | later
    intro_track: Mapped[str | None] = mapped_column(String(64), nullable=True)  # career when they started
    career_intros_seen: Mapped[list[str]] = mapped_column(JSONType, default=list)
    dismissed: Mapped[list[str]] = mapped_column(JSONType, default=list)
    welcomed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    tour_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    tour_finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Application(Base):
    """A real job application as the learner describes it: facts they enter, never inferred.

    It's separate from a job target (which describes preparation) and can link to one. Nothing
    here is sent anywhere or submitted to anyone; "applied" is only ever what the learner records.
    """

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_application_client_request"),
        Index("ix_applications_user_stage", "user_id", "stage"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    employer: Mapped[str] = mapped_column(String(120))
    role_title: Mapped[str] = mapped_column(String(120))
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)  # http(s) only, never fetched
    applied_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # as recorded; unknown is fine
    # saved | applied | interviewing | offer | closed | withdrawn
    stage: Mapped[str] = mapped_column(String(16), default="saved")
    next_action: Mapped[str] = mapped_column(Text, default="")
    next_action_due: Mapped[date | None] = mapped_column(Date, nullable=True)  # a calendar date, no time
    notes: Mapped[str] = mapped_column(Text, default="")
    target_id: Mapped[str | None] = mapped_column(
        ForeignKey("role_targets.id", ondelete="SET NULL", name="fk_application_target"), nullable=True
    )
    story_ids: Mapped[list] = mapped_column(JSONType, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    history: Mapped[list[ApplicationStageChange]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationStageChange.id"
    )
    events: Mapped[list[ApplicationEvent]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.id"
    )


class ApplicationStageChange(Base):
    """Every stage change, append-only, with the title and employer as they were at the time, so
    later edits never rewrite history. A correction is recorded as its own change."""

    __tablename__ = "application_stage_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    from_stage: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(16))
    correction: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    role_title: Mapped[str] = mapped_column(String(120))
    employer: Mapped[str] = mapped_column(String(120))
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="history")


class ApplicationEvent(Base):
    """An interview (or other) event for an application, as the learner records it. Each
    interview is its own event. Times are the learner's: a date, an optional local time and the
    IANA time zone it's in; `starts_at` is derived (UTC) only when all three are known."""

    __tablename__ = "application_events"
    __table_args__ = (
        UniqueConstraint("application_id", "client_request_id", name="uq_event_client_request"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # phone_screen | interview | assessment | other
    title: Mapped[str] = mapped_column(String(120))
    on_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    local_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM"
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="events")


class ScheduleSettings(Base):
    """How a learner's schedule is shown, and their reminder choices (off unless turned on)."""

    __tablename__ = "schedule_settings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64))  # IANA; new entries default to it
    reminders: Mapped[bool] = mapped_column(Boolean, default=False)  # in-app only, while a tab is open
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=10)
    quiet_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "22:00"
    quiet_end: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "07:00"
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ScheduleEntry(Base):
    """A time the learner set aside for an existing activity (a plan item, a review, a question, a
    problem, or preparation for an interview). It points at the activity by id; scheduling it
    is not doing it, and completion comes from the activity's own rules.

    Timed entries keep what the learner chose (date, wall-clock time, IANA zone) and the exact
    instant; all-day entries are just a date. `uid` and `sequence` let a calendar file update or
    cancel the same event."""

    __tablename__ = "schedule_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_schedule_client_request"),
        Index("ix_schedule_user_date", "user_id", "on_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    uid: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(
        String(20)
    )  # plan_item | review_item | question | problem | application_event
    ref: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    on_date: Mapped[date] = mapped_column(Date)
    local_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(12), default="scheduled")  # scheduled | cancelled
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class InterviewKit(Base):
    """The interview-day kit for one recorded interview event: logistics, an editable checklist,
    questions to ask and the stories to bring. Everything here is the learner's own (suggestions
    are labelled); a ticked item means they ticked it, not that anything was checked for them."""

    __tablename__ = "interview_kits"

    event_id: Mapped[str] = mapped_column(
        ForeignKey("application_events.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(12), default="unknown")  # remote | in_person | phone | unknown
    location: Mapped[str] = mapped_column(Text, default="")
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)  # http(s), never fetched
    interviewers: Mapped[list] = mapped_column(JSONType, default=list)  # [{name, role}], as typed
    notes: Mapped[str] = mapped_column(Text, default="")
    checklist: Mapped[list] = mapped_column(JSONType, default=list)  # [{id, text, origin, done, hidden}]
    questions: Mapped[list] = mapped_column(JSONType, default=list)  # [{id, text, group, origin, excluded}]
    story_ids: Mapped[list] = mapped_column(JSONType, default=list)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class WhiteboardDraft(Base):
    """A learner's working diagram for one prompt. Saving checks the revision, so a stale tab
    can't overwrite newer work."""

    __tablename__ = "whiteboard_drafts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    diagram: Mapped[dict] = mapped_column(JSONType)
    explanation: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class WhiteboardAttempt(Base):
    """A diagram submitted for feedback: a frozen copy with the prompt and rubric versions and the
    feedback it got. Later edits to the draft never change it."""

    __tablename__ = "whiteboard_attempts"
    __table_args__ = (Index("ix_whiteboard_user_prompt", "user_id", "prompt_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    prompt_id: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[int] = mapped_column(Integer)
    rubric_version: Mapped[int] = mapped_column(Integer)
    diagram: Mapped[dict] = mapped_column(JSONType)
    digest: Mapped[str] = mapped_column(String(32))
    explanation: Mapped[str] = mapped_column(Text)
    feedback: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class DrillAttempt(Base):
    """One go at a communication drill: the words sent (typed, or a transcript the learner checked
    and edited), how they were given, and the feedback. Attempts are never changed afterwards."""

    __tablename__ = "drill_attempts"
    __table_args__ = (
        Index("ix_drill_user_drill", "user_id", "drill_id"),
        UniqueConstraint("user_id", "client_request_id", name="uq_drill_client_request"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    drill_id: Mapped[str] = mapped_column(String(32))
    track: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(8))  # typed | voice
    spoken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)  # measured while recording
    rubric_version: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[dict] = mapped_column(JSONType)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
