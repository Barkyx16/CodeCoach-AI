"""Personal data export ("download my data")."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AIInteraction,
    PracticeAnswer,
    PracticeMode,
    PracticeSession,
    Problem,
    ProgressEvent,
    Submission,
    User,
)

EXPORT_VERSION = 1


def export_user_data(db: Session, user: User) -> dict:
    """Everything stored about the user, in one JSON document. Credentials (password hash,
    token version) are deliberately excluded."""
    slugs = dict(db.execute(select(Problem.id, Problem.slug)).all())
    subs = db.scalars(
        select(Submission)
        .options(selectinload(Submission.result))
        .where(Submission.user_id == user.id)
        .order_by(Submission.created_at)
    ).all()
    ai = db.scalars(
        select(AIInteraction).where(AIInteraction.user_id == user.id).order_by(AIInteraction.created_at)
    ).all()
    sessions = db.scalars(
        select(PracticeSession)
        .options(selectinload(PracticeSession.turns))
        .where(PracticeSession.user_id == user.id)
        .order_by(PracticeSession.started_at)
    ).all()
    events = db.scalars(
        select(ProgressEvent).where(ProgressEvent.user_id == user.id).order_by(ProgressEvent.created_at)
    ).all()
    answers = db.scalars(
        select(PracticeAnswer).where(PracticeAnswer.user_id == user.id).order_by(PracticeAnswer.created_at)
    ).all()

    def iso(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    return {
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_guest": user.is_guest,
            "career_track": user.career_track,
            "created_at": iso(user.created_at),
            "last_login_at": iso(user.last_login_at),
        },
        "submissions": [
            {
                "id": s.id,
                "problem": slugs.get(s.problem_id),
                "language": s.language,
                "mode": s.mode.value,
                "status": s.status.value,
                "source_code": s.source_code,
                "created_at": iso(s.created_at),
                "judged_at": iso(s.judged_at),
                "result": None
                if s.result is None
                else {
                    "passed_count": s.result.passed_count,
                    "total_count": s.result.total_count,
                    "runtime_ms": s.result.runtime_ms,
                    "public_results": s.result.public_results,
                    "compiler_output": s.result.stderr_excerpt,
                },
            }
            for s in subs
        ],
        "ai_feedback": [
            {
                "id": a.id,
                "problem": slugs.get(a.problem_id),
                "action": a.action.value,
                "hint_level": a.hint_level,
                "provider": a.provider,
                "model": a.model,
                "input_tokens": a.input_tokens,
                "output_tokens": a.output_tokens,
                "response": a.response,
                "created_at": iso(a.created_at),
            }
            for a in ai
        ],
        "interviews": [
            {
                "id": s.id,
                "kind": "questions" if s.mode == PracticeMode.QUESTIONS else "coding",
                "problem": slugs.get(s.problem_id) if s.problem_id else None,
                "track": s.track,
                "questions": (s.plan or {}).get("question_ids"),
                "status": s.status.value,
                "started_at": iso(s.started_at),
                "ended_at": iso(s.ended_at),
                "final_code": s.final_code,
                "evaluation": s.evaluation,
                "transcript": [
                    {
                        "role": t.role.value,
                        "phase": t.phase.value if t.phase else None,
                        "content": t.content,
                        "at": iso(t.created_at),
                        "question_index": t.question_index,
                        "answer_id": t.answer_id,
                        "meta": t.meta,
                    }
                    for t in s.turns
                ],
            }
            for s in sessions
            if s.mode in (PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)
        ],
        "activity": [
            {"type": e.event_type.value, "problem": slugs.get(e.problem_id), "at": iso(e.created_at)}
            for e in events
        ],
        "interview_answers": [
            {
                "career": a.track,
                "question": a.question_id,
                "answer": a.answer,
                "score": a.score,
                "feedback": a.feedback,
                "coach": a.provider,
                "created_at": iso(a.created_at),
            }
            for a in answers
        ],
    }
