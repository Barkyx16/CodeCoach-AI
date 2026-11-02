"""Mock interviews: a timed, phase-based state machine around the AI interviewer.

State machine (status)                Phase arc while IN_PROGRESS
    IN_PROGRESS ──finish──▶ COMPLETED     clarify → approach → coding → complexity → wrap_up
         │ ──deadline──▶ EXPIRED          (forward only; the interviewer decides when to advance,
         └──abandon────▶ ABANDONED         and a phase auto-advances after 3 candidate turns)

Rules
- One interview in progress per user (starting another returns 409 with the active id).
- Time limits are enforced on the server; expiry is applied lazily on the next read or write.
- Every interviewer turn uses the user's AI budget. The final evaluation always runs (falling
  back to the offline scorer when the budget is used up) so a learner never loses feedback for
  a finished session.
- Transcript turns are stored; prompts are not.

Question rounds (kind="questions", see question_rounds.py) share this service's loading, ownership,
deadline and one-active-interview rules; they have no phases and make no AI calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.careers import CATALOG
from app.config import Settings
from app.errors import AppError, ConflictError, NotFoundError, RateLimitedError
from app.models import (
    AIAction,
    InterviewPhase,
    InterviewStatus,
    InterviewTurn,
    PracticeMode,
    PracticeSession,
    Problem,
    ProgressEvent,
    ProgressEventType,
    TurnRole,
    User,
)
from app.schemas.common import Page
from app.schemas.interview import (
    PHASE_GUIDE,
    Engagement,
    InterviewEvaluation,
    InterviewFinish,
    InterviewKind,
    InterviewMessage,
    InterviewOut,
    InterviewProblem,
    InterviewStart,
    InterviewSummary,
    RoundAnswer,
    RoundSkip,
    TurnOut,
)
from app.services import engagement
from app.services.ai.base import CoachProvider, InterviewContext, ProviderResult, TranscriptTurn
from app.services.ai.offline import OfflineCoach
from app.services.ai.service import CoachService, problem_context, sanitize_code
from app.services.ai.static_analysis import analyze
from app.services.progress import ProgressService
from app.services.question_rounds import QuestionRounds

MAX_CANDIDATE_TURNS = 30
PHASES = list(InterviewPhase)
INTERVIEW_MODES = (PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)


def _now() -> datetime:
    return datetime.now(UTC)


class InterviewService:
    def __init__(self, db: Session, settings: Settings, provider: CoachProvider, practice_limiter=None):
        self.db = db
        self.settings = settings
        self.coach = CoachService(db, settings, provider)
        self.rounds = QuestionRounds(db, practice_limiter)

    # --- queries ----------------------------------------------------------------------

    def load(self, user: User, interview_id: str) -> PracticeSession:
        """The user's interview (either kind), with any due expiry applied. 404 for anyone else's."""
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        return session

    def get(self, user: User, interview_id: str) -> InterviewOut:
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        return self._to_out(session)

    def list(self, user: User, page: int, page_size: int) -> Page[InterviewSummary]:
        base = select(PracticeSession).where(
            PracticeSession.user_id == user.id, PracticeSession.mode.in_(INTERVIEW_MODES)
        )
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self.db.scalars(
            base.options(selectinload(PracticeSession.problem))
            .order_by(PracticeSession.started_at.desc(), PracticeSession.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        for s in rows:
            self._expire_if_due(user, s)
        return Page[InterviewSummary](
            items=[self._to_summary(s) for s in rows], total=total, page=page, page_size=page_size
        )

    # --- commands ---------------------------------------------------------------------

    def start(self, user: User, body: InterviewStart) -> InterviewOut:
        active = self.db.scalar(
            select(PracticeSession).where(
                PracticeSession.user_id == user.id,
                PracticeSession.mode.in_(INTERVIEW_MODES),
                PracticeSession.status == InterviewStatus.IN_PROGRESS,
            )
        )
        if active is not None:
            self._expire_if_due(user, active)
            if active.status == InterviewStatus.IN_PROGRESS:
                raise ConflictError(
                    "You already have an interview in progress. Finish or abandon it first.",
                    code="interview_in_progress",
                    details={"interview_id": active.id},
                )

        if body.kind == "questions":
            session = self.rounds.start(user, body)
            self.db.commit()
            return self._to_out(session)

        problem = self._pick_problem(user, body.problem_slug)
        self.coach.check_budget(user)
        now = _now()
        duration = body.duration_minutes * 60
        session = PracticeSession(
            user_id=user.id,
            mode=PracticeMode.INTERVIEW,
            problem_id=problem.id,
            status=InterviewStatus.IN_PROGRESS,
            phase=InterviewPhase.CLARIFY,
            duration_seconds=duration,
            started_at=now,
            deadline_at=now + timedelta(seconds=duration),
        )
        session.problem = problem
        self.db.add(session)
        self.db.flush()

        ctx = self._context(session, code="", is_opening=True)
        result = self.coach.call_with_fallback(lambda p: p.interview_turn(ctx))
        self._add_turn(session, TurnRole.INTERVIEWER, result.content.message)
        session.provider = result.provider
        self._record(user, problem, result)
        self.db.commit()
        return self._to_out(session)

    def respond(self, user: User, interview_id: str, body: InterviewMessage) -> InterviewOut:
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        self._require_in_progress(session)
        self._require_kind(session, PracticeMode.INTERVIEW)
        candidate_turns = sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE)
        if candidate_turns >= MAX_CANDIDATE_TURNS:
            raise AppError(
                "This interview has reached its message limit. Finish it to get feedback.",
                code="turn_limit_reached",
                details={"max_candidate_turns": MAX_CANDIDATE_TURNS},
            )
        self.coach.check_budget(user)

        code = sanitize_code(body.code or session.final_code or "", self.settings.ai_max_code_chars)
        if body.code is not None:
            session.final_code = body.code
        message = body.message.strip()
        expected = (session.problem.expected_complexity or {}).get("time") if session.problem else None
        read = engagement.for_coding_message(session.phase, message, expected)
        self._add_turn(
            session,
            TurnRole.CANDIDATE,
            message,
            meta={"source": body.source, "engagement": read.model_dump(mode="json")},
        )
        self.db.flush()

        ctx = self._context(session, code=code)
        result = self.coach.call_with_fallback(lambda p: p.interview_turn(ctx))
        reply = result.content
        if reply.advance_phase and session.phase is not None:
            session.phase = session.phase.next  # None after wrap-up: ready to finish
        self._add_turn(session, TurnRole.INTERVIEWER, reply.message)
        self._record(user, session.problem, result)
        self.db.commit()
        return self._to_out(session)

    def answer_question(self, user: User, interview_id: str, body: RoundAnswer) -> InterviewOut:
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        self._require_kind(session, PracticeMode.QUESTIONS)
        if not self.rounds._already_handled(session, body.question_index):
            self._require_in_progress(session)
        self.rounds.answer(user, session, body)
        self.db.commit()
        return self._to_out(session)

    def skip_question(self, user: User, interview_id: str, body: RoundSkip) -> InterviewOut:
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        self._require_kind(session, PracticeMode.QUESTIONS)
        if not self.rounds._already_handled(session, body.question_index):
            self._require_in_progress(session)
        self.rounds.skip(session, body)
        self.db.commit()
        return self._to_out(session)

    def finish(self, user: User, interview_id: str, body: InterviewFinish | None = None) -> InterviewOut:
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        if session.status != InterviewStatus.IN_PROGRESS:
            return self._to_out(session)  # idempotent: finishing twice returns the result
        if session.mode == PracticeMode.QUESTIONS:
            # A round completes itself after its last question; ending early is "abandon".
            raise ConflictError(
                "There are questions left. Answer or skip them, or end the interview early.",
                code="questions_remaining",
            )
        if body and body.code is not None:
            session.final_code = body.code
        self._close(user, session, InterviewStatus.COMPLETED, "finished")
        self.db.commit()
        return self._to_out(session)

    def abandon(self, user: User, interview_id: str) -> InterviewOut:
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        if session.status == InterviewStatus.IN_PROGRESS:
            self._close(user, session, InterviewStatus.ABANDONED, "abandoned")
            self.db.commit()
        return self._to_out(session)

    # --- internals --------------------------------------------------------------------

    def _pick_problem(self, user: User, slug: str | None) -> Problem:
        if slug:
            problem = self.db.scalar(select(Problem).where(Problem.slug == slug))
            if problem is None:
                raise NotFoundError(f"Problem '{slug}' not found")
            return problem
        recs = ProgressService(self.db).recommend(user, limit=1)
        chosen = self.db.scalar(
            select(Problem).where(Problem.slug == recs[0].slug)
            if recs
            else select(Problem).order_by(Problem.order_index)
        )
        if chosen is None:
            raise NotFoundError("No problems are available")
        return chosen

    def _load(self, user: User, interview_id: str) -> PracticeSession:
        session = self.db.scalar(
            select(PracticeSession)
            .options(selectinload(PracticeSession.turns), selectinload(PracticeSession.problem))
            .where(PracticeSession.id == interview_id, PracticeSession.mode.in_(INTERVIEW_MODES))
        )
        if session is None or session.user_id != user.id:
            raise NotFoundError("Interview not found")
        return session

    @staticmethod
    def _require_kind(session: PracticeSession, mode: PracticeMode) -> None:
        if session.mode != mode:
            raise ConflictError(
                "That action doesn't apply to this kind of interview.", code="wrong_interview_kind"
            )

    @staticmethod
    def _require_in_progress(session: PracticeSession) -> None:
        if session.status != InterviewStatus.IN_PROGRESS:
            raise ConflictError(
                f"This interview is {session.status.value}.",
                code="interview_closed",
                details={"status": session.status.value},
            )

    def _expire_if_due(self, user: User, session: PracticeSession) -> None:
        if (
            session.status == InterviewStatus.IN_PROGRESS
            and session.deadline_at is not None
            and _now() >= session.deadline_at
        ):
            self._close(user, session, InterviewStatus.EXPIRED, "time_expired")
            self.db.commit()

    def _close(self, user: User, session: PracticeSession, status: InterviewStatus, reason: str) -> None:
        if session.mode == PracticeMode.QUESTIONS:
            # Each answer was graded as it came in; there's no AI evaluation to run.
            session.status = status
            session.ended_at = _now()
            return
        code = sanitize_code(session.final_code or "", self.settings.ai_max_code_chars)
        ctx = self._context(session, code=code, end_reason=reason)
        try:
            self.coach.check_budget(user)
            result = self.coach.call_with_fallback(lambda p: p.evaluate_interview(ctx))
            self._record(user, session.problem, result)
        except RateLimitedError:
            # Never withhold feedback for a finished session: score it offline, free of charge.
            result = OfflineCoach().evaluate_interview(ctx)
        session.evaluation = result.content.model_dump(mode="json")
        session.status = status
        session.ended_at = _now()
        if session.problem is not None:
            self.db.add(
                ProgressEvent(
                    user_id=user.id,
                    problem_id=session.problem.id,
                    event_type=ProgressEventType.INTERVIEW_COMPLETED,
                )
            )

    def _context(
        self, session: PracticeSession, *, code: str, is_opening: bool = False, end_reason: str | None = None
    ) -> InterviewContext:
        problem = session.problem
        assert problem is not None
        phase = session.phase or InterviewPhase.WRAP_UP
        turns_in_phase = sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE and t.phase == phase)
        return InterviewContext(
            problem=problem_context(problem),
            phase=phase,
            transcript=[
                TranscriptTurn(role=t.role.value, phase=t.phase or InterviewPhase.WRAP_UP, content=t.content)
                for t in session.turns
            ],
            code=code,
            analysis=analyze(
                code,
                signature=problem.signature,
                starter_code=problem.starter_code,
                expected_time=(problem.expected_complexity or {}).get("time"),
                constraints=list(problem.constraints),
            ),
            candidate_turns_in_phase=turns_in_phase,
            seconds_remaining=self._seconds_remaining(session),
            is_opening=is_opening,
            end_reason=end_reason,
        )

    def _add_turn(
        self, session: PracticeSession, role: TurnRole, content: str, meta: dict | None = None
    ) -> None:
        session.turns.append(
            InterviewTurn(
                seq=len(session.turns),
                role=role,
                phase=session.phase or InterviewPhase.WRAP_UP,
                content=content,
                meta=meta,
            )
        )

    def _record(self, user: User, problem: Problem | None, result: ProviderResult) -> None:
        if problem is not None:
            # The transcript already stores the text; the usage row only accounts for cost.
            self.coach.record_interaction(
                user, problem, AIAction.MOCK_INTERVIEW, result, store_response=False
            )

    @staticmethod
    def _seconds_remaining(session: PracticeSession) -> int:
        if session.status != InterviewStatus.IN_PROGRESS or session.deadline_at is None:
            return 0
        return max(0, int((session.deadline_at - _now()).total_seconds()))

    @staticmethod
    def _problem_out(session: PracticeSession) -> InterviewProblem | None:
        p = session.problem
        return InterviewProblem(slug=p.slug, title=p.title, difficulty=p.difficulty) if p else None

    @staticmethod
    def _turn_out(t: InterviewTurn) -> TurnOut:
        meta = t.meta or {}
        return TurnOut(
            seq=t.seq,
            role=t.role,
            phase=t.phase,
            content=t.content,
            created_at=t.created_at,
            question_index=t.question_index,
            source=meta.get("source"),
            skipped=bool(meta.get("skipped")),
            engagement=Engagement.model_validate(meta["engagement"]) if meta.get("engagement") else None,
        )

    @staticmethod
    def _kind(session: PracticeSession) -> InterviewKind:
        return "questions" if session.mode == PracticeMode.QUESTIONS else "coding"

    @staticmethod
    def _career_title(session: PracticeSession) -> str | None:
        profile = CATALOG.get(session.track or "")
        return profile.title if profile else None

    def _to_out(self, session: PracticeSession) -> InterviewOut:
        candidate_turns = sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE)
        phase = session.phase if session.status == InterviewStatus.IN_PROGRESS else None
        questions = self.rounds.questions_out(session) if session.mode == PracticeMode.QUESTIONS else []
        return InterviewOut(
            id=session.id,
            kind=self._kind(session),
            track=session.track,
            career_title=self._career_title(session),
            questions=questions,
            round_summary=self.rounds.summary(questions) if session.mode == PracticeMode.QUESTIONS else None,
            status=session.status,
            phase=phase,
            phase_index=PHASES.index(phase) if phase else len(PHASES),
            phase_guide=PHASE_GUIDE[phase] if phase else None,
            problem=self._problem_out(session),
            duration_seconds=session.duration_seconds or 0,
            started_at=session.started_at,
            deadline_at=session.deadline_at or session.started_at,
            ended_at=session.ended_at,
            seconds_remaining=self._seconds_remaining(session),
            candidate_turns_remaining=max(0, MAX_CANDIDATE_TURNS - candidate_turns),
            provider=session.provider,
            turns=[self._turn_out(t) for t in session.turns],
            final_code=session.final_code,
            evaluation=InterviewEvaluation.model_validate(session.evaluation) if session.evaluation else None,
        )

    def _to_summary(self, session: PracticeSession) -> InterviewSummary:
        ev = session.evaluation or {}
        scores = [s["score"] for s in ev.get("scores", [])]
        return InterviewSummary(
            id=session.id,
            kind=self._kind(session),
            track=session.track,
            career_title=self._career_title(session),
            status=session.status,
            problem=self._problem_out(session),
            started_at=session.started_at,
            ended_at=session.ended_at,
            overall=ev.get("overall"),
            average_score=round(sum(scores) / len(scores), 2) if scores else None,
        )
