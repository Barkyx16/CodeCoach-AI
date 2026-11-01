"""Personal data export ("download my data")."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AIInteraction, PracticeSession, Problem, ProgressEvent, Submission, User

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
            "created_at": iso(user.created_at),
            "last_login_at": iso(user.last_login_at),
        },
        "submissions": [
            {
                "id": s.id,
                "problem": slugs.get(s.problem_id),
                "language": s.language,
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
                "problem": slugs.get(s.problem_id) if s.problem_id else None,
                "status": s.status.value,
                "started_at": iso(s.started_at),
                "ended_at": iso(s.ended_at),
                "final_code": s.final_code,
                "evaluation": s.evaluation,
                "transcript": [
                    {
                        "role": t.role.value,
                        "phase": t.phase.value,
                        "content": t.content,
                        "at": iso(t.created_at),
                    }
                    for t in s.turns
                ],
            }
            for s in sessions
            if s.mode.value == "interview"
        ],
        "activity": [
            {"type": e.event_type.value, "problem": slugs.get(e.problem_id), "at": iso(e.created_at)}
            for e in events
        ],
    }
