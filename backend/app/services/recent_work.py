"""Recent work to continue (Volume 11, prompt 1; docs/CONTINUE.md): a few of the caller's own
records, newest first, from the times the records really keep. Only ids, titles and timestamps
are read: no note body, story text, transcript or terms. An interview in progress comes first.
Each kind of record is read on its own, in a savepoint: one that fails is named in `unavailable`
and the others are still listed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationEvent,
    ExperienceEntry,
    InterviewKit,
    InterviewStatus,
    Note,
    OfferComparison,
    PracticeMode,
    PracticeSession,
    Problem,
    User,
)
from app.services.activity import career_title

logger = logging.getLogger("codecoach.recent_work")
MAX_LIMIT = 12


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _interviews(db: Session, user: User, n: int) -> list[dict]:
    now = datetime.now(UTC)
    rows = db.execute(
        select(
            PracticeSession.id,
            PracticeSession.mode,
            PracticeSession.status,
            PracticeSession.started_at,
            PracticeSession.ended_at,
            PracticeSession.deadline_at,
            PracticeSession.track,
            Problem.title,
        )
        .outerjoin(Problem, Problem.id == PracticeSession.problem_id)
        .where(
            PracticeSession.user_id == user.id,
            PracticeSession.mode.in_((PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)),
        )
        .order_by(func.coalesce(PracticeSession.ended_at, PracticeSession.started_at).desc())
        .limit(n)
    ).all()
    out = []
    for sid, mode, status, started, ended, deadline, track, problem in rows:
        title = (
            f"{career_title(track or '')} question round"
            if mode == PracticeMode.QUESTIONS
            else f"Coding interview: {problem}"
            if problem
            else "Coding interview"
        )
        if status == InterviewStatus.IN_PROGRESS:
            live = deadline is not None and _aware(deadline) > now
            state, at, meaning = ("in_progress" if live else "time_up"), started, "started"
        else:
            state = {"completed": "finished", "expired": "expired", "abandoned": "ended_early"}[str(status)]
            at, meaning = ended or started, "finished"
        out.append(
            {"type": "interview", "id": sid, "title": title, "state": state, "at": at, "at_meaning": meaning}
        )
    return out


def _notes(db: Session, user: User, n: int) -> list[dict]:
    rows = db.execute(
        select(Note.id, Note.title, Note.updated_at)
        .where(Note.user_id == user.id, Note.deleted_at.is_(None))
        .order_by(Note.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {"type": "note", "id": i, "title": t.strip() or "Untitled note", "at": at, "at_meaning": "saved"}
        for i, t, at in rows
    ]


def _stories(db: Session, user: User, n: int) -> list[dict]:
    rows = db.execute(
        select(ExperienceEntry.id, ExperienceEntry.title, ExperienceEntry.updated_at)
        .where(ExperienceEntry.user_id == user.id)
        .order_by(ExperienceEntry.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {"type": "story", "id": i, "title": t.strip() or "Untitled story", "at": at, "at_meaning": "saved"}
        for i, t, at in rows
    ]


def _kits(db: Session, user: User, n: int) -> list[dict]:
    rows = db.execute(
        select(
            InterviewKit.event_id,
            InterviewKit.updated_at,
            ApplicationEvent.application_id,
            ApplicationEvent.title,
            ApplicationEvent.on_date,
            Application.employer,
        )
        .join(ApplicationEvent, ApplicationEvent.id == InterviewKit.event_id)
        .join(Application, Application.id == ApplicationEvent.application_id)
        .where(InterviewKit.user_id == user.id, Application.user_id == user.id)
        .order_by(InterviewKit.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {
            "type": "kit",
            "id": event_id,
            "parent_id": app_id,
            "title": f"Interview-day kit: {title}" + (f" ({employer})" if employer else ""),
            "detail": f"on {on_date.isoformat()}" if on_date else None,
            "at": at,
            "at_meaning": "saved",
        }
        for event_id, at, app_id, title, on_date, employer in rows
    ]


def _applications(db: Session, user: User, n: int) -> list[dict]:
    rows = db.execute(
        select(
            Application.id,
            Application.role_title,
            Application.employer,
            Application.stage,
            Application.updated_at,
        )
        .where(Application.user_id == user.id)
        .order_by(Application.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {
            "type": "application",
            "id": i,
            "title": f"{role} at {employer}" if role and employer else role or employer or "Application",
            "detail": stage.capitalize(),
            "at": at,
            "at_meaning": "saved",
        }
        for i, role, employer, stage, at in rows
    ]


def _offer_comparisons(db: Session, user: User, n: int) -> list[dict]:
    rows = db.execute(
        select(OfferComparison.id, OfferComparison.title, OfferComparison.updated_at)
        .where(OfferComparison.user_id == user.id)
        .order_by(OfferComparison.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {
            "type": "offer_comparison",
            "id": i,
            "title": t.strip() or "Offer comparison",
            "at": at,
            "at_meaning": "saved",
        }
        for i, t, at in rows
    ]


# What each kind is called when it can't be read ("Your notes couldn't be loaded").
SOURCES: dict[str, tuple[str, Callable[[Session, User, int], list[dict]]]] = {
    "interviews": ("interviews", _interviews),
    "notes": ("notes", _notes),
    "stories": ("stories", _stories),
    "kits": ("interview-day kits", _kits),
    "applications": ("applications", _applications),
    "offer_comparisons": ("offer comparisons", _offer_comparisons),
}


def recent_work(db: Session, user: User, limit: int = 6) -> dict:
    limit = max(1, min(limit, MAX_LIMIT))
    items: list[dict] = []
    unavailable: list[str] = []
    for name, (label, read) in SOURCES.items():
        try:
            with db.begin_nested():  # a failing kind rolls back to here; the others still run
                items.extend(read(db, user, limit))
        except Exception:
            logger.exception("recent work: %s couldn't be read", name)
            unavailable.append(label)
    for i in items:
        i["at"] = _aware(i["at"])
    # An interview whose clock is running comes first; then everything else, newest first.
    items.sort(key=lambda i: (i.get("state") != "in_progress", -i["at"].timestamp()))
    return {"items": items[:limit], "unavailable": unavailable}
