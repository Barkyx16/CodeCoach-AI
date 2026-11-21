"""Search your own saved work (Volume 11, prompt 3; docs/WORKSPACE_SEARCH.md): notes, stories,
interview-day kits and applications, by words typed.

Every query names the caller (`user_id = :me`) before anything is matched, counted, ranked or
quoted, and PostgreSQL row-level security applies on top; another account's rows are never read.
Matching is in two steps: the database narrows each kind to the caller's rows where every word
appears in one of the searched columns (parameterized LIKE, with % and _ escaped, at most
CANDIDATES rows per kind), then Python checks each candidate exactly, ranks it and cuts a snippet.

The fields searched for each kind are the ones its own page already searches (the notebook, the
story bank), or, for kits and applications, their names only; see FIELDS. Nothing typed is logged
here, and the terms travel in a request body, not a URL.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import Application, ApplicationEvent, ExperienceEntry, InterviewKit, Note, User
from app.services.stories import TEXT_FIELDS as STORY_FIELDS

logger = logging.getLogger("codecoach.workspace_search")

MAX_QUERY = 200
MAX_WORDS = 8
MAX_WORD = 60
MAX_LIMIT = 50
CANDIDATES = 200  # per kind: a learner's own records are few (notes are capped at 2,000)
SNIPPET = 160
KINDS = ("notes", "stories", "kits", "applications")

# Which columns each kind is searched in, by name (for the docs and the API description).
FIELDS: dict[str, tuple[str, ...]] = {
    "notes": ("title", "body", "reflection", "tags", "source_title"),
    "stories": (*STORY_FIELDS, "tags"),
    "kits": ("event title", "employer", "role title"),
    "applications": ("employer", "role title", "next step"),
}

_SPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def words_of(q: str) -> list[str]:
    """The words of a query, folded the same way as the text they're matched against: unique,
    at most MAX_WORDS, each cut to MAX_WORD characters."""
    folded = _fold(q)
    out: list[str] = []
    for w in folded.split(" "):
        w = w[:MAX_WORD]
        if w and w not in out:
            out.append(w)
    return out[:MAX_WORDS]


def _fold(text: str) -> str:
    return _SPACE.sub(" ", _CONTROL.sub(" ", unicodedata.normalize("NFKC", text or ""))).strip().lower()


@dataclass
class _Hit:
    type: str
    id: str
    title: str
    texts: list[tuple[str, str]]  # (field label, text) searched besides the title, in snippet order
    at: datetime
    parent_id: str | None = None
    state: str | None = None
    detail: str | None = None
    tags: list[str] = field(default_factory=list)


def _all_words(columns: Sequence[Any], words: list[str]) -> ColumnElement[bool]:
    """Every word in at least one of the columns: lower(col) LIKE '%word%', escaped and bound."""
    return and_(*[or_(*[func.lower(c).contains(w, autoescape=True) for c in columns]) for w in words])


def _notes(db: Session, user: User, words: list[str], archived: bool) -> list[_Hit]:
    cols = [Note.title, Note.body, Note.reflection, Note.source_title, cast(Note.tags, String)]
    q = select(
        Note.id,
        Note.title,
        Note.body,
        Note.reflection,
        Note.tags,
        Note.source_title,
        Note.updated_at,
        Note.archived,
        Note.pinned,
    ).where(Note.user_id == user.id, Note.deleted_at.is_(None), _all_words(cols, words))
    if not archived:
        q = q.where(Note.archived.is_(False))
    rows = db.execute(q.order_by(Note.updated_at.desc()).limit(CANDIDATES)).all()
    return [
        _Hit(
            "note",
            i,
            (t or "").strip() or "Untitled note",
            [("text", body or ""), ("reflection", refl or ""), ("source", src or "")],
            at,
            state="archived" if arch else "pinned" if pin else None,
            tags=list(tags or []),
        )
        for i, t, body, refl, tags, src, at, arch, pin in rows
    ]


def _stories(db: Session, user: User, words: list[str], archived: bool) -> list[_Hit]:
    columns = [getattr(ExperienceEntry, f) for f in STORY_FIELDS]
    q = select(ExperienceEntry).where(
        ExperienceEntry.user_id == user.id,
        _all_words([*columns, cast(ExperienceEntry.tags, String)], words),
    )
    if not archived:
        q = q.where(ExperienceEntry.archived.is_(False))
    rows = db.scalars(q.order_by(ExperienceEntry.updated_at.desc()).limit(CANDIDATES)).all()
    return [
        _Hit(
            "story",
            e.id,
            (e.title or "").strip() or "Untitled story",
            [(f, getattr(e, f) or "") for f in STORY_FIELDS if f != "title"],
            e.updated_at,
            state="archived" if e.archived else None,
            tags=list(e.tags or []),
        )
        for e in rows
    ]


def _kits(db: Session, user: User, words: list[str], archived: bool) -> list[_Hit]:
    cols = [ApplicationEvent.title, Application.employer, Application.role_title]
    q = (
        select(
            InterviewKit.event_id,
            InterviewKit.updated_at,
            ApplicationEvent.application_id,
            ApplicationEvent.title,
            ApplicationEvent.on_date,
            Application.employer,
            Application.role_title,
            Application.archived,
        )
        .join(ApplicationEvent, ApplicationEvent.id == InterviewKit.event_id)
        .join(Application, Application.id == ApplicationEvent.application_id)
        .where(InterviewKit.user_id == user.id, Application.user_id == user.id, _all_words(cols, words))
    )
    if not archived:
        q = q.where(Application.archived.is_(False))
    rows = db.execute(q.order_by(InterviewKit.updated_at.desc()).limit(CANDIDATES)).all()
    return [
        _Hit(
            "kit",
            event_id,
            f"Interview-day kit: {title}",
            [("employer", employer or ""), ("role", role or "")],
            at,
            parent_id=app_id,
            state="archived" if arch else None,
            detail=" · ".join(x for x in (employer, f"on {on_date.isoformat()}" if on_date else None) if x)
            or None,
        )
        for event_id, at, app_id, title, on_date, employer, role, arch in rows
    ]


def _applications(db: Session, user: User, words: list[str], archived: bool) -> list[_Hit]:
    cols = [Application.employer, Application.role_title, Application.next_action]
    q = select(
        Application.id,
        Application.role_title,
        Application.employer,
        Application.stage,
        Application.next_action,
        Application.updated_at,
        Application.archived,
    ).where(Application.user_id == user.id, _all_words(cols, words))
    if not archived:
        q = q.where(Application.archived.is_(False))
    rows = db.execute(q.order_by(Application.updated_at.desc()).limit(CANDIDATES)).all()
    return [
        _Hit(
            "application",
            i,
            f"{role} at {employer}" if role and employer else role or employer or "Application",
            [("employer", employer or ""), ("role", role or ""), ("next step", nxt or "")],
            at,
            state="archived" if arch else None,
            detail=f"Stage: {stage.capitalize()}",
        )
        for i, role, employer, stage, nxt, at, arch in rows
    ]


# The label each kind has when it can't be read ("Your notes couldn't be searched just now").
SOURCES: dict[str, tuple[str, Callable[[Session, User, list[str], bool], list[_Hit]]]] = {
    "notes": ("notes", _notes),
    "stories": ("stories", _stories),
    "kits": ("interview-day kits", _kits),
    "applications": ("applications", _applications),
}


def _snippet(text: str, words: list[str]) -> str:
    """A short plain-text window around the first word found (whitespace collapsed). Plain text:
    the page shows it as text and marks the words itself."""
    flat = _SPACE.sub(" ", _CONTROL.sub(" ", unicodedata.normalize("NFKC", text))).strip()
    low = flat.lower()
    found = [p for p in (low.find(w) for w in words) if p >= 0]
    if not found:
        return ""
    at = min(found)
    start = max(0, at - SNIPPET // 3)
    if start:
        space = flat.find(" ", start)
        start = space + 1 if 0 <= space < at else start
    end = min(len(flat), start + SNIPPET)
    if end < len(flat):
        space = flat.rfind(" ", start, end)
        end = space if space > at else end
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


def _lead(text: str) -> str:
    flat = _SPACE.sub(" ", _CONTROL.sub(" ", unicodedata.normalize("NFKC", text))).strip()
    if len(flat) <= SNIPPET:
        return flat
    space = flat.rfind(" ", 0, SNIPPET)
    return flat[: space if space > 0 else SNIPPET] + "…"


def _score(hit: _Hit, words: list[str]) -> tuple[int, list[str]] | None:
    """None unless every word is in the title, the searched text or a tag (checked exactly, after
    the database's rough cut); otherwise a score (title words count most) and where it matched."""
    title = _fold(hit.title)
    texts = [(label, _fold(t)) for label, t in hit.texts]
    tags = [_fold(t) for t in hit.tags]
    score, where = 0, []
    for w in words:
        if w in title:
            score += 3
            where.append("title")
        elif any(w in t for _, t in texts):
            score += 1
            where.append(next(label for label, t in texts if w in t))
        elif any(w in t for t in tags):
            score += 2
            where.append("tags")
        else:
            return None
    return score, list(dict.fromkeys(where))


def search(
    db: Session,
    user: User,
    q: str,
    *,
    kinds: Sequence[str] = KINDS,
    include_archived: bool = False,
    limit: int = 20,
) -> dict:
    words = words_of(q)
    limit = max(1, min(limit, MAX_LIMIT))
    counts: dict[str, int] = {}
    capped: list[str] = []
    unavailable: list[str] = []
    scored: list[tuple[int, datetime, dict]] = []
    if not words:
        return {"items": [], "counts": {}, "capped": [], "unavailable": [], "words": []}
    for name in (k for k in KINDS if k in kinds):
        label, read = SOURCES[name]
        try:
            with db.begin_nested():  # a failing kind rolls back to here; the others still run
                hits = read(db, user, words, include_archived)
        except Exception:
            # The kind, never the words: what someone searched for isn't logged.
            logger.warning("workspace search: %s couldn't be read", name, exc_info=True)
            unavailable.append(name)
            continue
        if len(hits) >= CANDIDATES:
            capped.append(name)
        n = 0
        for hit in hits:
            result = _score(hit, words)
            if result is None:
                continue
            n += 1
            score, where = result
            snippet = next((s for _, t in hit.texts if (s := _snippet(t, words))), "")
            if not snippet:  # matched by title or tag: the start of its text, for context
                snippet = next((_lead(t) for _, t in hit.texts if t.strip()), "")
            scored.append(
                (
                    score,
                    hit.at,
                    {
                        "type": hit.type,
                        "id": hit.id,
                        "parent_id": hit.parent_id,
                        "title": hit.title,
                        "snippet": snippet or None,
                        "matched": where,
                        "state": hit.state,
                        "detail": hit.detail,
                        "tags": hit.tags[:6],
                        "at": hit.at,
                    },
                )
            )
        counts[name] = n
    scored.sort(key=lambda s: (-s[0], -s[1].timestamp()))
    return {
        "items": [s[2] for s in scored[:limit]],
        "counts": counts,
        "capped": capped,
        "unavailable": unavailable,
        "words": words,
    }
