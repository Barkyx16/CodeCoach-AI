"""A process-wide snapshot of published corrections and retired content.

The career question bank is generated in code, so corrections and retirement live in the
database and are applied on top. Reading them on every lookup would mean a query per question;
instead each request makes sure the snapshot is at most a few seconds old (`refresh`, called
from the database dependency), and a change made in this process invalidates it at once. With
several API replicas, other replicas see a change within `MAX_AGE_S`.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentStatus, ContentVersion

MAX_AGE_S = 5.0


@dataclass(frozen=True)
class Correction:
    version: int
    fields: dict
    change_note: str
    significant: bool
    created_at: object


@dataclass
class Snapshot:
    # (content_type, content_id) -> corrections, oldest first
    corrections: dict[tuple[str, str], list[Correction]] = field(default_factory=dict)
    # (content_type, content_id) -> public reason
    retired: dict[tuple[str, str], str] = field(default_factory=dict)
    loaded_at: float = 0.0
    source: str = ""
    # Changes whenever what's published changes: response caches key on it (app/http_cache.py).
    fingerprint: str = ""


_lock = threading.Lock()
_snapshot = Snapshot()


def current() -> Snapshot:
    return _snapshot


def invalidate() -> None:
    global _snapshot
    with _lock:
        _snapshot = Snapshot()


def _source(db: Session) -> str:
    bind = db.get_bind()
    return str(getattr(bind, "url", id(bind)))


def load(db: Session) -> Snapshot:
    snap = Snapshot(loaded_at=time.monotonic(), source=_source(db))
    for row in db.scalars(select(ContentVersion).order_by(ContentVersion.version)):
        snap.corrections.setdefault((row.content_type, row.content_id), []).append(
            Correction(row.version, dict(row.fields), row.change_note, row.significant, row.created_at)
        )
    for status in db.scalars(select(ContentStatus).where(ContentStatus.status == "retired")):
        snap.retired[(status.content_type, status.content_id)] = status.reason
    digest = hashlib.sha256(snap.source.encode())
    for key in sorted(snap.corrections):
        digest.update(repr((key, [c.version for c in snap.corrections[key]])).encode())
    for key in sorted(snap.retired):
        digest.update(repr(("retired", key)).encode())
    snap.fingerprint = digest.hexdigest()[:16]
    return snap


def refresh(db: Session, force: bool = False) -> Snapshot:
    """Reload when stale, forced, or when this is a different database (tests make many)."""
    global _snapshot
    source = _source(db)
    snap = _snapshot
    if force or snap.source != source or time.monotonic() - snap.loaded_at > MAX_AGE_S:
        fresh = load(db)
        with _lock:
            _snapshot = fresh
        return fresh
    return snap
