"""Mock interviews: a timed, phase-based state machine around the AI interviewer.

State machine (status)                Phase arc while IN_PROGRESS
    IN_PROGRESS ──finish──▶ COMPLETED     clarify → approach → coding → complexity → wrap_up
         │ ──deadline──▶ EXPIRED          (forward only; the interviewer decides when to advance,
         └──abandon────▶ ABANDONED         and a phase auto-advances after 3 candidate turns)

Rules
- One interview in progress per user, of either kind. The database enforces it (a partial unique
  index), so two Starts at once can't both succeed. Starting another returns 409
  `interview_in_progress` with the active interview's id and what's needed to recognize and resume
  it (kind, title, progress, time left, last activity), before any AI call is made.
- Time limits are enforced on the server; expiry is applied lazily on the next read or write.
- Moving out of in_progress (finish, abandon, expiry) is one compare-and-set: if two requests
  close the same interview at once, one runs the evaluation and the other returns its result.
- Each turn has a unique position (session_id, seq), so two answers sent at once from two tabs
  can't both be stored. A coding message can carry the transcript length it was written against
  (`after_seq`): if the interview moved on since (another tab or device), it's refused with 409
  `interview_advanced` rather than appended out of context. Its `client_request_id` makes a resend
  of the same message (a response lost after the server accepted it) return the current state
  instead of a second reply.
- Every interviewer turn uses the user's AI budget. The final evaluation always runs (falling
  back to the offline scorer when the budget is used up) so a learner never loses feedback for
  a finished session.
- Transcript turns are stored; prompts are not.
- What the interviewer reads can be previewed (a message, and the feedback on Finish or End early):
  the preview is built by the same code as the request, with secret-looking strings replaced in
  messages and code, and a request carrying its fingerprint (`approved_context`) is sent only if
  what would be read is still exactly that (docs/COACH_CONTEXT.md, "The coding interviewer").

Question rounds (kind="questions", see question_rounds.py) share this service's loading, ownership,
deadline and one-active-interview rules; they have no phases and make no AI calls.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import tracing
from app.careers import CATALOG
from app.careers.formats import FORMATS, KIND_LABEL, MAX_FOLLOWUPS, PANEL_ORDER, availability, panel_roles
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
from app.schemas.ai import CoachPreview, ContextItem
from app.schemas.common import Page
from app.schemas.interview import (
    PHASE_GUIDE,
    Engagement,
    FeedbackRead,
    FeedbackReadItem,
    FollowupAnswer,
    FormatOption,
    FormatSlot,
    InterviewAbandon,
    InterviewEvaluation,
    InterviewFeedbackPreview,
    InterviewFinish,
    InterviewKind,
    InterviewMessage,
    InterviewMessagePreview,
    InterviewOut,
    InterviewProblem,
    InterviewStart,
    InterviewSummary,
    RoundAnswer,
    RoundSkip,
    SpeakerOut,
    TurnOut,
)
from app.services import engagement, request_keys
from app.services.ai.base import CoachProvider, InterviewContext, ProviderResult, TranscriptTurn
from app.services.ai.context_text import ending_text, interview_phase_text, transcript_line, transcript_text
from app.services.ai.offline import OfflineCoach
from app.services.ai.service import CoachService, problem_context, redact_secrets_counted
from app.services.ai.static_analysis import analyze
from app.services.listed_names import names_for, names_note, replace_names
from app.services.progress import ProgressService
from app.services.question_rounds import ROUND, QuestionRounds

MAX_CANDIDATE_TURNS = 30
# How long before time runs out the page offers to check what the feedback will read (Volume 15,
# prompt 8; docs/COACH_CONTEXT.md, "What the feedback read"). Checking doesn't stop the clock.
FEEDBACK_CHECK_MARGIN_SECONDS = 120
PHASES = list(InterviewPhase)
INTERVIEW_MODES = (PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)

# What the interviewer reads, previewed and bound (docs/COACH_CONTEXT.md, "The coding interviewer").
CHANGED = (
    "What the interviewer would read changed since you checked it, so nothing was sent. "
    "Check it again before sending."
)
BUILT_IN_FALLBACK = "If it can't be reached, the built-in interviewer answers from this same material."


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _replaced_note(n: int) -> list[str]:
    return [f"{_plural(n, 'secret-looking string')} replaced with [REDACTED]."] if n else []


def _as_read(
    turns: Sequence[InterviewTurn], names: tuple[str, ...] = ()
) -> tuple[list[TranscriptTurn], int, int]:
    """The stored conversation as the interviewer reads it: every turn, in order, with
    secret-looking strings and names you listed replaced (the stored turns keep what was written),
    and how many of each were."""
    out: list[TranscriptTurn] = []
    replaced = named = 0
    for t in turns:
        text, n = redact_secrets_counted(t.content)
        text, m = replace_names(text, names)
        replaced += n
        named += m
        out.append(TranscriptTurn(role=t.role.value, phase=t.phase or InterviewPhase.WRAP_UP, content=text))
    return out, replaced, named


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

    def _live(self, user: User) -> PracticeSession | None:
        return self.db.scalar(
            select(PracticeSession)
            .options(selectinload(PracticeSession.turns), selectinload(PracticeSession.problem))
            .where(
                PracticeSession.user_id == user.id,
                PracticeSession.mode.in_(INTERVIEW_MODES),
                PracticeSession.status == InterviewStatus.IN_PROGRESS,
            )
        )

    def _in_progress(self, session: PracticeSession) -> ConflictError:
        """The 409 for a Start while another interview is live: enough to recognize and resume it."""
        return ConflictError(
            "You already have an interview in progress. Resume it, or end it to start another.",
            code="interview_in_progress",
            details={
                "interview_id": session.id,
                "interview": self._to_summary(session).model_dump(mode="json"),
            },
        )

    def start(self, user: User, body: InterviewStart) -> InterviewOut:
        active = self._live(user)
        if active is not None:
            self._expire_if_due(user, active)
            if active.status == InterviewStatus.IN_PROGRESS:
                raise self._in_progress(active)

        try:
            if body.kind == "questions":
                session = self.rounds.start(user, body)
                self.db.commit()
                return self._to_out(session)

            problem = self._pick_problem(user, body.problem_slug)
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
            # The one-live-interview index applies here, before the AI is asked anything (and before
            # the per-user AI lock, so a second Start gets the useful 409, not "request in progress").
            self.db.flush()
            self.coach.check_budget(user)
        except IntegrityError:
            # Another Start (a second tab, a double click, a retry) got there first.
            self.db.rollback()
            winner = self._live(user)
            if winner is None:
                raise
            raise self._in_progress(winner) from None

        ctx = self._opening_context(session)
        result = self.coach.call_with_fallback(lambda p: p.interview_turn(ctx))
        self._add_turn(session, TurnRole.INTERVIEWER, result.content.message)
        session.provider = result.provider
        self._record(user, problem, result)
        self.db.commit()
        return self._to_out(session)

    def respond(self, user: User, interview_id: str, body: InterviewMessage) -> InterviewOut:
        session = self._load(user, interview_id)
        sent = next(
            (
                t
                for t in session.turns
                if body.client_request_id
                and (t.meta or {}).get("client_request_id") == body.client_request_id
            ),
            None,
        )
        if sent is not None:
            # The same key again: its response was lost after the server took it. The same message
            # is reconciled (the current state, the reply included) instead of asking the
            # interviewer twice; other words under that key are refused, never taken as sent.
            if sent.content != body.message.strip():
                raise request_keys.reused("message")
            self._expire_if_due(user, session)
            return self._to_out(session)
        self._expire_if_due(user, session)
        self._require_message_allowed(session, body.after_seq)
        # What the interviewer reads, built once: compared with the approved preview (if any) before
        # anything is stored or spent, then sent exactly as built.
        ctx, preview = self._message_material(
            user, session, body.message, body.code or session.final_code or "", body.code is not None
        )
        self._require_approved(preview, body.approved_context)
        self.coach.check_budget(user)

        if body.code is not None:
            session.final_code = body.code
        message = body.message.strip()
        expected = (session.problem.expected_complexity or {}).get("time") if session.problem else None
        read = engagement.for_coding_message(session.phase, message, expected)
        meta: dict[str, Any] = {"source": body.source, "engagement": read.model_dump(mode="json")}
        if body.client_request_id:
            meta["client_request_id"] = body.client_request_id
        self._add_turn(session, TurnRole.CANDIDATE, message, meta=meta)
        try:
            self.db.flush()  # a turn's position is unique: a message sent at the same moment elsewhere loses here
        except IntegrityError:
            self.db.rollback()
            raise self._advanced(self._load(user, interview_id)) from None

        result = self.coach.call_with_fallback(lambda p: p.interview_turn(ctx))
        reply = result.content
        if reply.advance_phase and session.phase is not None:
            session.phase = session.phase.next  # None after wrap-up: ready to finish
        self._add_turn(session, TurnRole.INTERVIEWER, reply.message)
        self._record(user, session.problem, result)
        self.db.commit()
        return self._to_out(session)

    def message_preview(self, user: User, interview_id: str, body: InterviewMessagePreview) -> CoachPreview:
        """Exactly what the interviewer would read with this message. No provider call, no budget,
        nothing stored; an interview past its time isn't closed by a preview (the next read does)."""
        session = self._load(user, interview_id)
        self._require_open_for_preview(session)
        self._require_message_allowed(session, body.after_seq)
        return self._message_material(
            user, session, body.message, body.code or session.final_code or "", body.code is not None
        )[1]

    def feedback_preview(self, user: User, interview_id: str, body: InterviewFeedbackPreview) -> CoachPreview:
        """Exactly what the end-of-interview feedback would read, on Finish or on End early."""
        session = self._load(user, interview_id)
        self._require_open_for_preview(session)
        self._require_kind(session, PracticeMode.INTERVIEW)
        code, from_editor = self._ending_code(session, body.ending, body.code)
        return self._feedback_material(user, session, code, body.ending, from_editor)[1]

    def answer_question(self, user: User, interview_id: str, body: RoundAnswer) -> InterviewOut:
        with tracing.round_action("answer") as step:
            session = self._load(user, interview_id)
            step.set(format=(session.plan or {}).get("format"))
            self._expire_if_due(user, session)
            self._require_kind(session, PracticeMode.QUESTIONS)
            duplicate = self.rounds._already_handled(session, body.question_index)
            if duplicate:
                self._same_answer_or_conflict(session, body)
            else:
                self._require_in_progress(session)
            try:
                self.rounds.answer(user, session, body)
                self._commit()
            except IntegrityError:
                # Answered at the same moment in another tab: that answer was stored first.
                self.db.rollback()
                session = self._load(user, interview_id)
                self._same_answer_or_conflict(session, body)
                duplicate = True
            step.set(result=self._round_result(session, duplicate))
            return self._to_out(session)

    def _same_answer_or_conflict(self, session: PracticeSession, body: RoundAnswer) -> None:
        """A repeat of the stored answer is a retry: fine. A different text means this question was
        answered (or skipped) elsewhere: refused, so the caller keeps its text instead of losing it."""
        stored = next(
            (
                t
                for t in session.turns
                if t.role == TurnRole.CANDIDATE and t.question_index == body.question_index
            ),
            None,
        )
        if stored is not None and " ".join(stored.content.split()) == " ".join(body.answer.split()):
            return
        current = next((q.index for q in self.rounds.questions_out(session) if q.status == "current"), None)
        raise ConflictError(
            "This question already has an answer: sent earlier, or from another tab or device. "
            "Your text here wasn't sent, and it's still in the box.",
            code="question_answered_elsewhere",
            details={
                "question_index": body.question_index,
                "skipped": bool(stored is not None and (stored.meta or {}).get("skipped")),
                "current_question_index": current,
                "status": session.status.value,
            },
        )

    def _advanced(self, session: PracticeSession) -> ConflictError:
        return ConflictError(
            "This interview moved on in another tab or on another device. Your message wasn't sent, "
            "and it's still in the box.",
            code="interview_advanced",
            details={"turns": len(session.turns), "status": session.status.value},
        )

    def skip_question(self, user: User, interview_id: str, body: RoundSkip) -> InterviewOut:
        with tracing.round_action("skip") as step:
            session = self._load(user, interview_id)
            step.set(format=(session.plan or {}).get("format"))
            self._expire_if_due(user, session)
            self._require_kind(session, PracticeMode.QUESTIONS)
            duplicate = self.rounds._already_handled(session, body.question_index)
            if not duplicate:
                self._require_in_progress(session)
            self.rounds.skip(session, body)
            self._commit()
            step.set(result=self._round_result(session, duplicate))
            return self._to_out(session)

    def followup(self, user: User, interview_id: str, body: FollowupAnswer | None) -> InterviewOut:
        with tracing.round_action("reply" if body is not None else "skip_followup") as step:
            session = self._load(user, interview_id)
            step.set(format=(session.plan or {}).get("format"))
            self._expire_if_due(user, session)
            self._require_kind(session, PracticeMode.QUESTIONS)
            waiting = bool((session.plan or {}).get("pending_followup"))
            if waiting:
                self._require_in_progress(session)
            self.rounds.answer_followup(session, body)
            self._commit()
            step.set(result=self._round_result(session, duplicate=not waiting))
            return self._to_out(session)

    def _commit(self) -> None:
        with tracing.span("db.commit"):
            self.db.commit()

    @staticmethod
    def _round_result(session: PracticeSession, duplicate: bool) -> str:
        """What a round action did, for traces and metrics (a fixed set of values)."""
        if duplicate:
            return "duplicate"  # a repeated submit: nothing changed, nothing graded again
        if session.status != InterviewStatus.IN_PROGRESS:
            return "completed"
        if (session.plan or {}).get("pending_followup"):
            return "followup"
        return "advanced"

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
        code = body.code if body else None
        if body and body.approved_context is not None:
            text, from_editor = self._ending_code(session, "finished", code)
            self._require_approved(
                self._feedback_material(user, session, text, "finished", from_editor)[1],
                body.approved_context,
            )
        if code is not None:
            session.final_code = code
        checked = bool(body and body.approved_context is not None)
        self._close(user, session, InterviewStatus.COMPLETED, "finished", checked=checked)
        self.db.commit()
        return self._to_out(session)

    def abandon(self, user: User, interview_id: str, body: InterviewAbandon | None = None) -> InterviewOut:
        session = self._load(user, interview_id)
        self._expire_if_due(user, session)
        if session.status == InterviewStatus.IN_PROGRESS:
            if body and body.approved_context is not None and session.mode == PracticeMode.INTERVIEW:
                text, from_editor = self._ending_code(session, "abandoned", None)
                self._require_approved(
                    self._feedback_material(user, session, text, "abandoned", from_editor)[1],
                    body.approved_context,
                )
            checked = bool(
                body and body.approved_context is not None and session.mode == PracticeMode.INTERVIEW
            )
            self._close(user, session, InterviewStatus.ABANDONED, "abandoned", checked=checked)
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
            else select(Problem).where(Problem.kind == "problem").order_by(Problem.order_index)
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

    @staticmethod
    def _remember_read(session: PracticeSession, record: dict[str, Any]) -> None:
        session.plan = {**(session.plan or {}), "feedback_read": {"v": 1, **record, "at": _now().isoformat()}}

    @staticmethod
    def feedback_read(session: PracticeSession) -> FeedbackRead | None:
        """What the feedback read, as recorded when it was scored; for one scored before this was
        recorded, said so rather than rebuilt."""
        if session.status == InterviewStatus.IN_PROGRESS:
            return None
        rec = (session.plan or {}).get("feedback_read")
        if not isinstance(rec, dict):
            return FeedbackRead(recorded=False, text="What it read wasn't recorded then.")
        ending, checked = rec.get("ending"), rec.get("checked")
        if checked is None:
            text = "Scored by CodeCoach's own rules from these; nothing left CodeCoach, so there was nothing to check."
            if ending == "time_expired":
                text = "Time ran out, so it was scored from what you'd answered. " + text
        elif checked:
            text = "You checked this before it was scored."
        elif ending == "time_expired":
            text = "You didn't check this before it was scored: time ran out."
        else:
            text = "You didn't check this before it was scored."
        return FeedbackRead(
            recorded=True,
            ending=ending if ending in ("finished", "abandoned", "time_expired") else None,
            checked=checked,
            items=[FeedbackReadItem(**i) for i in rec.get("items") or []],
            fingerprint=rec.get("fingerprint"),
            read_by=rec.get("read_by"),
            text=text,
        )

    def _claim_close(self, session: PracticeSession, status: InterviewStatus) -> bool:
        """Move this interview out of in_progress, atomically. False: another request (a second
        tab, a retry, the deadline seen twice) closed it first; `session` then holds its result."""
        won = self.db.execute(
            update(PracticeSession)
            .where(PracticeSession.id == session.id, PracticeSession.status == InterviewStatus.IN_PROGRESS)
            .values(status=status, ended_at=_now())
            .execution_options(synchronize_session=False)
        )
        if int(getattr(won, "rowcount", 0) or 0) == 0:
            self.db.refresh(session)
            return False
        return True

    def _close(
        self,
        user: User,
        session: PracticeSession,
        status: InterviewStatus,
        reason: str,
        checked: bool = False,
    ) -> None:
        if not self._claim_close(session, status):
            return
        if session.mode == PracticeMode.QUESTIONS:
            # Each answer was graded as it came in; there's no AI evaluation to run. What the round's
            # summary read is recorded all the same (labels and sizes; the answers stay where they are).
            self._remember_read(
                session,
                {
                    "ending": reason,
                    "checked": None,  # nothing left CodeCoach, so there was nothing to check first
                    "read_by": "CodeCoach's own fixed rules, on its server: nothing left it",
                    "items": [
                        {"label": f"Your answer to question {n}", "chars": len(t.content), "notes": []}
                        for n, t in enumerate(
                            (t for t in session.turns if t.role == TurnRole.CANDIDATE and t.content), 1
                        )
                    ],
                },
            )
            session.status = status
            session.ended_at = _now()
            return
        ctx, preview = self._feedback_material(user, session, session.final_code or "", reason, False)
        read_by = preview.recipient
        try:
            self.coach.check_budget(user)
            result = self.coach.call_with_fallback(lambda p: p.evaluate_interview(ctx))
            self._record(user, session.problem, result)
        except RateLimitedError:
            # Never withhold feedback for a finished session: score it offline, free of charge.
            result = OfflineCoach().evaluate_interview(ctx)
            read_by = "The built-in interviewer, on CodeCoach's own server (no coaching requests were left that day)"
        # What it read, recorded with the feedback (docs/COACH_CONTEXT.md, "What the feedback read"):
        # labels, sizes and what was replaced, never a second copy of the text.
        self._remember_read(
            session,
            {
                "ending": reason,
                "checked": checked,
                "fingerprint": preview.context_fingerprint,
                "read_by": read_by,
                "items": [
                    {"label": i.label, "chars": len(i.text), "notes": list(i.notes)} for i in preview.items
                ],
            },
        )
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

    # --- what the interviewer reads (docs/COACH_CONTEXT.md, "The coding interviewer") ------------

    def _require_message_allowed(self, session: PracticeSession, after_seq: int | None) -> None:
        self._require_in_progress(session)
        self._require_kind(session, PracticeMode.INTERVIEW)
        if after_seq is not None and after_seq != len(session.turns):
            raise self._advanced(session)
        candidate_turns = sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE)
        if candidate_turns >= MAX_CANDIDATE_TURNS:
            raise AppError(
                "This interview has reached its message limit. Finish it to get feedback.",
                code="turn_limit_reached",
                details={"max_candidate_turns": MAX_CANDIDATE_TURNS},
            )

    def _require_open_for_preview(self, session: PracticeSession) -> None:
        self._require_in_progress(session)
        if session.deadline_at is not None and _now() >= session.deadline_at:
            raise ConflictError(
                "This interview's time is up, so there's nothing more to send.",
                code="interview_closed",
                details={"status": InterviewStatus.EXPIRED.value},
            )

    @staticmethod
    def _require_approved(preview: CoachPreview, approved: str | None) -> None:
        """Bound to a preview: sent only if what would be read now is exactly what was checked."""
        if approved is not None and not hmac.compare_digest(preview.context_fingerprint, approved):
            raise ConflictError(
                CHANGED, code="context_changed", details={"preview": preview.model_dump(mode="json")}
            )

    @staticmethod
    def _ending_code(session: PracticeSession, ending: str, code: str | None) -> tuple[str, bool]:
        """The code the feedback reads: on Finish the editor's (if sent), otherwise the code last
        sent with a message, as ending early has always used."""
        if ending == "finished" and code is not None:
            return code, True
        return session.final_code or "", False

    def _conversation_item(
        self, turns: Sequence[TranscriptTurn], replaced: int, why: str, named: int = 0
    ) -> ContextItem:
        mine = sum(1 for t in turns if t.role == TurnRole.CANDIDATE.value)
        return ContextItem(
            key="conversation",
            label="The conversation so far",
            source=(
                f"Every message in this interview, in order: {_plural(mine, 'message')} of yours and "
                f"{_plural(len(turns) - mine, 'message')} from the interviewer. An interview has at most "
                f"{MAX_CANDIDATE_TURNS} of yours, each up to 4,000 characters."
            ),
            text=transcript_text([transcript_line(t.phase.value, t.role, t.content) for t in turns]),
            derived=False,
            required=True,
            why_required=why,
            notes=[*_replaced_note(replaced), *[n for n in [names_note(named)] if n]],
            names_replaced=named,
        )

    @staticmethod
    def _code_source(from_editor: bool) -> Callable[[int], str]:
        def source(lines: int) -> str:
            where = "As in the editor when you checked" if from_editor else "As last sent with a message"
            return f"{where}: {_plural(lines, 'line')}. Sent with line numbers added."

        return source

    def _message_material(
        self, user: User, session: PracticeSession, message: str, source_code: str, from_editor: bool
    ) -> tuple[InterviewContext, CoachPreview]:
        """The interviewer's next turn: the context it's given and the preview of exactly that."""
        problem = session.problem
        assert problem is not None
        phase = session.phase or InterviewPhase.WRAP_UP
        listed = names_for(self.db, user.id)
        earlier, earlier_replaced, earlier_named = _as_read(session.turns, listed)
        sent, replaced = redact_secrets_counted(message.strip())
        sent, named = replace_names(sent, listed)
        in_phase = 1 + sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE and t.phase == phase)
        code, analysis, code_items = self.coach._code_items(
            problem,
            source_code,
            names=listed,
            label="Your code",
            source=self._code_source(from_editor),
            why="The interviewer reads your code as it stands with each message.",
        )
        if not source_code.strip():
            code_items[0].notes.append("Your editor is empty: the interviewer is told so.")
        items = [
            ContextItem(
                key="message",
                label="Your message",
                source=f"As you wrote it: {_plural(len(message.strip()), 'character')}.",
                text=sent,
                derived=False,
                required=True,
                why_required="It's what the interviewer answers.",
                notes=[*_replaced_note(replaced), *[n for n in [names_note(named)] if n]],
                names_replaced=named,
            ),
            self._conversation_item(
                earlier,
                earlier_replaced,
                "The interviewer answers in the context of what's been said.",
                earlier_named,
            ),
            *code_items,
            ContextItem(
                key="phase",
                label="Where the interview is",
                source="Worked out by CodeCoach from this interview. The time left isn't sent with a message.",
                text=interview_phase_text(phase.value, PHASE_GUIDE[phase], in_phase),
                derived=True,
                required=True,
                why_required="The interviewer's next question depends on the phase.",
            ),
        ]
        mine = sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE) + 1
        preview = self.coach._preview(
            user,
            "interview_message",
            items,
            [],
            [self._public_problem(problem)],
            self._fingerprint(session, "message", items),
            about=[f"Your message {mine} of the {MAX_CANDIDATE_TURNS} an interview allows."],
            reader="interviewer",
            fallback=BUILT_IN_FALLBACK,
        )
        ctx = InterviewContext(
            problem=problem_context(problem),
            phase=phase,
            transcript=[*earlier, TranscriptTurn(role=TurnRole.CANDIDATE.value, phase=phase, content=sent)],
            code=code,
            analysis=analysis,
            candidate_turns_in_phase=in_phase,
            seconds_remaining=self._seconds_remaining(session),
        )
        return ctx, preview

    def _feedback_material(
        self, user: User, session: PracticeSession, source_code: str, ending: str, from_editor: bool
    ) -> tuple[InterviewContext, CoachPreview]:
        """The end-of-interview feedback: the context it's given and the preview of exactly that.
        Built the same way however the interview ends (finished, ended early, out of time)."""
        problem = session.problem
        assert problem is not None
        phase = session.phase or InterviewPhase.WRAP_UP
        listed = names_for(self.db, user.id)
        turns, replaced, named = _as_read(session.turns, listed)
        code, analysis, code_items = self.coach._code_items(
            problem,
            source_code,
            names=listed,
            label="Your code",
            source=self._code_source(from_editor),
            why="The feedback covers your code as well as the conversation.",
        )
        if not source_code.strip():
            code_items[0].notes.append("No code: the feedback is told none was written.")
        items = [
            self._conversation_item(turns, replaced, "The feedback is on the whole interview.", named),
            *code_items,
            ContextItem(
                key="ending",
                label="How it ended",
                source="Worked out by CodeCoach from how you're ending it.",
                text=ending_text(ending),
                derived=True,
                required=True,
                why_required="Feedback on an interview ended early takes that into account.",
            ),
        ]
        preview = self.coach._preview(
            user,
            "interview_feedback",
            items,
            [],
            [self._public_problem(problem)],
            self._fingerprint(session, f"feedback:{ending}", items),
            about=[
                "Feedback on the whole interview, scored on the rubric's dimensions.",
                "With no coaching requests left today, the built-in interviewer scores it from this same "
                "material, free.",
            ],
            reader="interviewer",
            fallback=BUILT_IN_FALLBACK,
        )
        ctx = InterviewContext(
            problem=problem_context(problem),
            phase=phase,
            transcript=turns,
            code=code,
            analysis=analysis,
            candidate_turns_in_phase=sum(
                1 for t in session.turns if t.role == TurnRole.CANDIDATE and t.phase == phase
            ),
            seconds_remaining=self._seconds_remaining(session),
            end_reason=ending,
        )
        return ctx, preview

    @staticmethod
    def _public_problem(problem: Problem) -> str:
        return (
            f"The problem “{problem.title}”: its statement, constraints, method signature and expected "
            "complexity. Public, the same for everyone, and needed to interview you on it."
        )

    @staticmethod
    def _fingerprint(session: PracticeSession, operation: str, items: Sequence[ContextItem]) -> str:
        return request_keys.fingerprint(
            "ai.interview.context",
            {"interview": session.id, "operation": operation, "sent": [[i.key, i.text] for i in items]},
        )

    def _opening_context(self, session: PracticeSession) -> InterviewContext:
        """The opening turn: the problem and the time available, nothing of the learner's yet."""
        problem = session.problem
        assert problem is not None
        return InterviewContext(
            problem=problem_context(problem),
            phase=session.phase or InterviewPhase.WRAP_UP,
            transcript=[],
            code="",
            analysis=analyze(
                "",
                signature=problem.signature,
                starter_code=problem.starter_code,
                expected_time=(problem.expected_complexity or {}).get("time"),
                constraints=list(problem.constraints),
            ),
            candidate_turns_in_phase=0,
            seconds_remaining=self._seconds_remaining(session),
            is_opening=True,
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
            round_format=self.rounds.format_out(session) if session.mode == PracticeMode.QUESTIONS else None,
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
            feedback_read=self.feedback_read(session),
            feedback_check_margin_seconds=(
                FEEDBACK_CHECK_MARGIN_SECONDS
                if session.status == InterviewStatus.IN_PROGRESS and session.mode == PracticeMode.INTERVIEW
                else None
            ),
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
            **self._live_context(session),
        )

    def _live_context(self, session: PracticeSession) -> dict[str, Any]:
        """Progress, time left and last activity, for an interview in progress (a Resume card)."""
        if session.status != InterviewStatus.IN_PROGRESS:
            return {}
        replies = sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE)
        return {
            "progress_done": replies,
            "progress_total": len((session.plan or {}).get("question_ids") or [])
            if session.mode == PracticeMode.QUESTIONS
            else None,
            "seconds_remaining": self._seconds_remaining(session),
            "last_activity_at": max((t.created_at for t in session.turns), default=session.started_at),
        }


def format_options(track: str, difficulty: str) -> list[FormatOption]:
    """Every format with its availability for this career and level, and a preview of who asks what."""
    if track not in CATALOG:
        raise NotFoundError(f"Career '{track}' not found")
    roles = panel_roles(track) or ()
    by_id = {r.id: SpeakerOut(id=r.id, title=r.title, objective=r.objective) for r in roles}
    out = []
    for fmt_id, d in FORMATS.items():
        ok, reason = availability(track, fmt_id, difficulty)
        if fmt_id == "panel":
            slots = (
                [
                    FormatSlot(
                        position=i + 1,
                        speaker=by_id.get(rid),
                        kind_label=" or ".join(
                            KIND_LABEL[k] for k in next(r for r in roles if r.id == rid).kinds[:2]
                        )
                        if roles
                        else "",
                    )
                    for i, rid in enumerate(PANEL_ORDER)
                ]
                if roles
                else []
            )
        elif fmt_id == "mixed":
            slots = [
                FormatSlot(position=i + 1, speaker=None, kind_label=KIND_LABEL[k])
                for i, k in enumerate(ROUND)
            ]
        else:
            label = " or ".join(KIND_LABEL[k] for k in d.kinds)
            slots = [FormatSlot(position=i + 1, speaker=None, kind_label=label) for i in range(5)]
        out.append(
            FormatOption(
                id=d.id,
                title=d.title,
                practices=d.practices,
                available=ok,
                unavailable_reason=reason,
                follow_ups=MAX_FOLLOWUPS if d.followups else 0,
                roles=list(by_id.values()) if fmt_id == "panel" else [],
                structure=slots,
            )
        )
    return out
