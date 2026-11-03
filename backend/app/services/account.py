"""Personal data export ("download my data")."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AIInteraction,
    Bookmark,
    ContentReport,
    ExperienceEntry,
    InterviewRetry,
    LearnEvent,
    Note,
    PracticeAnswer,
    PracticeCollection,
    PracticeGoal,
    PracticeMode,
    PracticePlan,
    PracticeSession,
    Problem,
    ProgressEvent,
    ReviewItem,
    RoleTarget,
    ScenarioAttempt,
    Share,
    ShareFeedback,
    StoryRevision,
    Submission,
    User,
)
from app.services.applications import Applications
from app.services.onboarding import Onboarding
from app.services.shares import status_of
from app.services.stories import snapshot

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
    goals = db.scalars(select(PracticeGoal).where(PracticeGoal.user_id == user.id)).all()
    plans = db.scalars(
        select(PracticePlan)
        .options(selectinload(PracticePlan.items))
        .where(PracticePlan.user_id == user.id)
        .order_by(PracticePlan.track, PracticePlan.version)
    ).all()
    targets = db.scalars(
        select(RoleTarget).options(selectinload(RoleTarget.requirements)).where(RoleTarget.user_id == user.id)
    ).all()
    experience = db.scalars(select(ExperienceEntry).where(ExperienceEntry.user_id == user.id)).all()
    retries = db.scalars(select(InterviewRetry).where(InterviewRetry.user_id == user.id)).all()
    queue = db.scalars(select(ReviewItem).where(ReviewItem.user_id == user.id)).all()
    scenario_attempts = db.scalars(
        select(ScenarioAttempt).where(ScenarioAttempt.user_id == user.id).order_by(ScenarioAttempt.created_at)
    ).all()
    notes = db.scalars(
        select(Note).where(Note.user_id == user.id, Note.deleted_at.is_(None)).order_by(Note.created_at)
    ).all()
    learn_events = db.scalars(
        select(LearnEvent).where(LearnEvent.user_id == user.id).order_by(LearnEvent.created_at)
    ).all()
    bookmarks = db.scalars(
        select(Bookmark).where(Bookmark.user_id == user.id).order_by(Bookmark.created_at)
    ).all()
    collections = db.scalars(
        select(PracticeCollection)
        .options(selectinload(PracticeCollection.items))
        .where(PracticeCollection.user_id == user.id)
        .order_by(PracticeCollection.created_at)
    ).all()
    events = db.scalars(
        select(ProgressEvent).where(ProgressEvent.user_id == user.id).order_by(ProgressEvent.created_at)
    ).all()
    answers = db.scalars(
        select(PracticeAnswer).where(PracticeAnswer.user_id == user.id).order_by(PracticeAnswer.created_at)
    ).all()
    reports = db.scalars(
        select(ContentReport).where(ContentReport.reporter_id == user.id).order_by(ContentReport.created_at)
    ).all()
    shares = db.scalars(
        select(Share)
        .options(selectinload(Share.feedback))
        .where(Share.owner_id == user.id)
        .order_by(Share.created_at)
    ).all()
    given = db.execute(
        select(ShareFeedback, Share.snapshot)
        .join(Share, Share.id == ShareFeedback.share_id)
        .where(ShareFeedback.reviewer_id == user.id)
        .order_by(ShareFeedback.created_at)
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
                "question_version": a.content_version or 1,
                "story": a.story_id,
                "created_at": iso(a.created_at),
            }
            for a in answers
        ],
        "practice_goals": [
            {
                "career": g.track,
                "specialty": g.specialty,
                "experience": g.experience,
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "weekly_minutes": g.weekly_minutes,
                "focus_areas": g.focus_areas,
                "formats": g.formats,
                "confidence": g.confidence,
                "setup_skipped": g.setup_skipped,
                "updated_at": iso(g.updated_at),
            }
            for g in goals
        ],
        "practice_plans": [
            {
                "career": p.track,
                "version": p.version,
                "created_at": iso(p.created_at),
                "changes": p.changes,
                "activities": [
                    {
                        "kind": i.kind,
                        "skill": i.skill,
                        "title": i.title,
                        "status": i.status,
                        "evidence": i.evidence,
                        "target": i.target,
                        "planned_at": iso(i.created_at),
                        "resolved_at": iso(i.resolved_at),
                    }
                    for i in p.items
                ],
            }
            for p in plans
        ],
        "target_roles": [
            {
                "career": t.track,
                "title": t.title,
                "employer": t.employer,
                "description": t.description,
                "interview_date": t.interview_date.isoformat() if t.interview_date else None,
                "notes": t.notes,
                "archived": t.archived,
                "requirements": [
                    {
                        "category": r.category,
                        "text": r.text,
                        "origin": r.origin,
                        "quote": r.quote,
                        "skills": r.skills,
                        "removed": r.removed,
                    }
                    for r in t.requirements
                ],
                "experience": [
                    {"title": e.title, "situation": e.situation, "action": e.action, "result": e.result}
                    for e in experience
                    if e.target_id == t.id
                ],
                "created_at": iso(t.created_at),
            }
            for t in targets
        ],
        "interview_retries": [
            {
                "interview": r.session_id,
                "question_index": r.question_index,
                "original_answer": r.original_answer_id,
                "retry_answer": r.retry_answer_id,
                "created_at": iso(r.created_at),
            }
            for r in retries
        ],
        "review_queue": [
            {
                "career": q.track,
                "question": q.question_id,
                "due_at": iso(q.due_at),
                "step": q.step,
                "last_score": q.last_score,
                "reviews": q.reviews,
                "removed": q.removed,
                "created_at": iso(q.created_at),
            }
            for q in queue
        ],
        "bookmarks": [
            {
                "type": b.item_type,
                "career": b.track or None,
                "item": b.ref_id,
                "created_at": iso(b.created_at),
            }
            for b in bookmarks
        ],
        "collections": [
            {
                "name": c.name,
                "queue_position": c.queue_position,
                "queue_started_at": iso(c.queue_started_at),
                "created_at": iso(c.created_at),
                "items": [
                    {
                        "type": i.item_type,
                        "career": i.track or None,
                        "item": i.ref_id,
                        "position": i.position,
                        "added_at": iso(i.added_at),
                        "queue_done_at": iso(i.queue_done_at),
                    }
                    for i in c.items
                ],
            }
            for c in collections
        ],
        "learn_events": [
            {
                "unit": e.unit_id,
                "version": e.unit_version,
                "kind": e.kind,
                "detail": (e.detail or {}).get("label"),
                "at": iso(e.created_at),
            }
            for e in learn_events
        ],
        "notes": [
            {
                "title": n.title,
                "body": n.body,
                "reflection": n.reflection,
                "tags": n.tags,
                "source": (
                    {
                        "type": n.source_type,
                        "id": n.source_id,
                        "career": n.source_track,
                        "version": n.source_version,
                        "title": n.source_title,
                    }
                    if n.source_type
                    else None
                ),
                "excerpt": n.excerpt,
                "key_points": n.key_points,
                "pinned": n.pinned,
                "archived": n.archived,
                "created_at": iso(n.created_at),
                "updated_at": iso(n.updated_at),
            }
            for n in notes
        ],
        # Your story bank: every story (also the examples written in a job target) and every saved version.
        "stories": [
            {
                "id": e.id,
                **snapshot(e),
                "revision": e.revision,
                "archived": e.archived,
                "created_at": iso(e.created_at),
                "updated_at": iso(e.updated_at),
                "revisions": [
                    {
                        "revision": r.revision,
                        "reason": r.reason,
                        "fields": r.fields,
                        "created_at": iso(r.created_at),
                    }
                    for r in db.scalars(
                        select(StoryRevision)
                        .where(StoryRevision.story_id == e.id)
                        .order_by(StoryRevision.revision)
                    )
                ],
            }
            for e in experience
        ],
        # Applications you recorded, with their interview events and stage history.
        "applications": Applications(db, user).export(),
        # Your choices about the first-session introduction (no answer text is part of it).
        "onboarding": Onboarding(db, user).export(),
        # Problems you reported in questions or feedback, and what happened (no internal notes).
        "content_reports": [
            {
                "content": f"{r.content_type}:{r.content_id}",
                "version": r.content_version,
                "category": r.category,
                "context": r.context,
                "details": r.details,
                "excerpt": r.excerpt,
                "status": r.status,
                "resolution": r.resolution,
                "created_at": iso(r.created_at),
            }
            for r in reports
        ],
        # Answers you shared for feedback: the exact snapshot, link status and feedback received.
        # Link secrets aren't stored, so none can be exported.
        "shares": [
            {
                "status": status_of(sh),
                "snapshot": sh.snapshot,
                "created_at": iso(sh.created_at),
                "expires_at": iso(sh.expires_at),
                "closed_at": iso(sh.closed_at),
                "revoked_at": iso(sh.revoked_at),
                "feedback": [
                    {
                        "reviewer": "signed-in user" if f.reviewer_kind == "account" else "guest",
                        "guest_name": f.guest_name,
                        "clear": f.clear,
                        "needs_evidence": f.needs_evidence,
                        "next_step": f.next_step,
                        "comments": f.comments,
                        "useful": f.useful,
                        "created_at": iso(f.created_at),
                    }
                    for f in sh.feedback
                ],
            }
            for sh in shares
        ],
        # Feedback you wrote on someone else's shared answer (your words, and which question).
        "feedback_given": [
            {
                "question": (snap or {}).get("question", {}).get("title"),
                "clear": f.clear,
                "needs_evidence": f.needs_evidence,
                "next_step": f.next_step,
                "comments": f.comments,
                "created_at": iso(f.created_at),
            }
            for f, snap in given
        ],
        "scenario_attempts": [
            {
                "scenario": a.scenario_id,
                "version": a.version,
                "mode": a.mode,
                "status": a.status,
                "steps": a.steps,
                "created_at": iso(a.created_at),
                "completed_at": iso(a.completed_at),
            }
            for a in scenario_attempts
        ],
    }
