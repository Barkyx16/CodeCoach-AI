"""Story freshness for preparation that references a story (Volume 12, prompt 8;
docs/STORY_FRESHNESS.md): a kit's chosen story, a requirement linked to a story.

The story is the source; the preparation records the revision (and a digest of the content it
relies on) it was prepared from. A change to that content asks for a review; a change only to
details it doesn't use (tags, competencies, notes, links, career, context) doesn't. The learner
decides: refresh to the revision they reviewed, or keep it as prepared. Each decision is recorded
(`source_reviews`), bound to the reviewed revision, and nothing refreshes by itself.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import ExperienceEntry, SourceReview, StoryRevision
from app.schemas.freshness import FieldChange, Freshness, LineageEntry

# What preparation relies on: the story's words. Everything else a story keeps (tags,
# competencies, private notes, career, context, question and requirement links) is metadata here.
CONTENT_FIELDS = (
    "title",
    "situation",
    "task",
    "action",
    "result",
    "reflection",
    "evidence",
    "short_version",
    "long_version",
)
LABELS = {
    "title": "Title",
    "situation": "Situation",
    "task": "Task",
    "action": "Action",
    "result": "Result",
    "reflection": "Reflection",
    "evidence": "Evidence",
    "short_version": "Short version",
    "long_version": "Long version",
}


def _norm(v: Any) -> str:
    return " ".join(str(v or "").split())  # spacing alone isn't a change


def digest_of(fields: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps([_norm(fields.get(f)) for f in CONTENT_FIELDS]).encode()).hexdigest()


def content(story: ExperienceEntry) -> dict[str, str]:
    return {f: getattr(story, f) or "" for f in CONTENT_FIELDS}


def digest(story: ExperienceEntry) -> str:
    return digest_of(content(story))


def day(at: datetime) -> str:
    at = at.astimezone(UTC) if at.tzinfo else at.replace(tzinfo=UTC)
    return f"{at.day} {at:%B}"


@dataclass(frozen=True)
class Prepared:
    revision: int | None
    digest: str | None = None  # None: read from the story's kept revision, if it's still kept


def lineage_text(r: SourceReview) -> str:
    if r.decision == "kept":
        return f"Kept version {r.from_revision} on {day(r.created_at)} (version {r.to_revision} was the latest then)."
    start = f"from version {r.from_revision} " if r.from_revision else ""
    return f"Refreshed {start}to version {r.to_revision} on {day(r.created_at)}, by you."


class StoryFreshness:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def fields_at(self, story_id: str, revision: int | None) -> dict | None:
        if revision is None:
            return None
        row = self.db.scalar(
            select(StoryRevision).where(
                StoryRevision.story_id == story_id, StoryRevision.revision == revision
            )
        )
        return dict(row.fields) if row is not None else None

    def decisions(self, holder_kind: str, holder_id: str, source_id: str) -> list[SourceReview]:
        return list(
            self.db.scalars(
                select(SourceReview)
                .where(
                    SourceReview.user_id == self.user_id,
                    SourceReview.holder_kind == holder_kind,
                    SourceReview.holder_id == holder_id,
                    SourceReview.source_id == source_id,
                )
                .order_by(SourceReview.created_at.desc(), SourceReview.to_revision.desc())
            )
        )

    def export(self) -> list[dict]:
        return [
            {
                "holder": f"{r.holder_kind}:{r.holder_id}",
                "story": r.source_id,
                "decision": r.decision,
                "from_revision": r.from_revision,
                "to_revision": r.to_revision,
                "at": r.created_at.isoformat(),
            }
            for r in self.db.scalars(
                select(SourceReview)
                .where(SourceReview.user_id == self.user_id)
                .order_by(SourceReview.created_at, SourceReview.id)
            )
        ]

    def assess(
        self,
        holder_kind: str,
        holder_id: str,
        story: ExperienceEntry | None,
        prepared: Prepared,
        since: str,
        decisions: list[SourceReview] | None = None,
    ) -> Freshness:
        """`since` completes "The story changed since …" ("you chose it for this kit")."""
        if story is None or story.user_id != self.user_id:
            return Freshness(
                state="unavailable",
                text="This story is no longer available. What was prepared from it is kept here.",
                prepared_revision=prepared.revision,
                current_revision=None,
            )
        rows = decisions if decisions is not None else self.decisions(holder_kind, holder_id, story.id)
        lineage = [
            LineageEntry(
                decision=r.decision,
                from_revision=r.from_revision,
                to_revision=r.to_revision,
                at=r.created_at,
                text=lineage_text(r),
            )
            for r in rows[:5]
        ]
        now_rev, now_digest = story.revision, digest(story)
        if prepared.revision is None:
            return Freshness(
                state="unknown",
                text="Whether the story changed since isn't known: this was prepared before story versions were recorded.",
                prepared_revision=None,
                current_revision=now_rev,
                lineage=lineage,
            )
        before = self.fields_at(story.id, prepared.revision)
        then_digest = prepared.digest or (digest_of(before) if before is not None else None)
        if then_digest == now_digest:
            if prepared.revision == now_rev:
                text = f"Up to date with the story (version {now_rev})."
            else:
                text = (
                    f"Up to date: the story changed since (version {prepared.revision}, now {now_rev}), "
                    "but only in details this doesn't use, like tags or notes."
                )
            return Freshness(
                state="current",
                text=text,
                prepared_revision=prepared.revision,
                current_revision=now_rev,
                lineage=lineage,
            )
        latest = rows[0] if rows else None
        if latest is not None and latest.decision == "kept" and latest.from_revision == prepared.revision:
            if latest.to_digest == now_digest:
                return Freshness(
                    state="kept",
                    text=(
                        f"You kept version {prepared.revision} on {day(latest.created_at)}; version "
                        f"{latest.to_revision} was the latest then. You'll be asked again only if the story "
                        "changes again."
                    ),
                    prepared_revision=prepared.revision,
                    current_revision=now_rev,
                    changes=self._changes(before, story),
                    lineage=lineage,
                )
            text = (
                f"The story changed again since you kept version {prepared.revision} "
                f"(now version {now_rev}). Review whether it still fits."
            )
        else:
            text = (
                f"The story changed since {since} (version {prepared.revision}, now {now_rev}). Review whether "
                "it still fits."
            )
        if before is None:
            text += " The earlier version isn't kept any more, so what changed can't be shown."
        return Freshness(
            state="needs_review",
            text=text,
            prepared_revision=prepared.revision,
            current_revision=now_rev,
            changes=self._changes(before, story),
            lineage=lineage,
        )

    @staticmethod
    def _changes(before: dict | None, story: ExperienceEntry) -> list[FieldChange]:
        now = content(story)
        if before is None:
            return []
        return [
            FieldChange(field=LABELS[f], before=before.get(f) or "", after=now[f])
            for f in CONTENT_FIELDS
            if _norm(before.get(f)) != _norm(now[f])
        ]

    def decide(
        self,
        holder_kind: str,
        holder_id: str,
        story: ExperienceEntry | None,
        prepared: Prepared,
        reviewed_revision: int,
        decision: str,
    ) -> SourceReview | None:
        """Record a refresh or a keep, bound to the revision the learner reviewed. Access is checked
        again here, and a newer revision is refused, never used silently. Returns None when it's
        already so (a repeat). The caller updates what it prepared and commits, in one transaction."""
        if story is None or story.user_id != self.user_id:
            raise NotFoundError("Story not found")
        if story.revision != reviewed_revision:
            raise ConflictError(
                f"The story changed again while you were reviewing it (now version {story.revision}; you "
                f"reviewed version {reviewed_revision}). Nothing was changed: review version {story.revision}.",
                code="source_changed",
                details={"current_revision": story.revision},
            )
        kind = "refreshed" if decision == "refresh" else "kept"
        rows = self.decisions(holder_kind, holder_id, story.id)
        latest = rows[0] if rows else None
        if kind == "refreshed" and prepared.revision == reviewed_revision:
            return None  # already prepared from this revision: one refresh, not two
        if latest is not None and latest.decision == kind and latest.to_revision == reviewed_revision:
            return None
        row = SourceReview(
            user_id=self.user_id,
            holder_kind=holder_kind,
            holder_id=holder_id,
            source_kind="story",
            source_id=story.id,
            from_revision=prepared.revision,
            to_revision=reviewed_revision,
            to_digest=digest(story),
            decision=kind,
            created_at=datetime.now(UTC),
        )
        self.db.add(row)
        return row


def forget(
    db: Session,
    user_id: str,
    *,
    holder_kind: str,
    holder_ids: list[str] | None = None,
    source_id: str | None = None,
) -> None:
    """Decisions go with what they were about: a kit's with its interview event, a requirement
    link's with its requirement or its story. Nothing else is touched."""
    stmt = delete(SourceReview).where(
        SourceReview.user_id == user_id, SourceReview.holder_kind == holder_kind
    )
    if holder_ids is not None:
        if not holder_ids:
            return
        stmt = stmt.where(SourceReview.holder_id.in_(holder_ids))
    if source_id is not None:
        stmt = stmt.where(SourceReview.source_id == source_id)
    db.execute(stmt)


def stamp_links(e: ExperienceEntry) -> None:
    """New requirement links record the story's revision and content they were made with. Links
    already there keep theirs; links from before requirement versions were kept stay unknown."""
    recorded = dict(e.requirement_versions or {})
    changed = False
    for rid in e.requirement_ids or []:
        rec = recorded.get(rid)
        if isinstance(rec, dict) and "story_revision" not in rec:
            recorded[rid] = {**rec, "story_revision": e.revision, "story_digest": digest(e)}
            changed = True
    if changed:
        e.requirement_versions = recorded


def link_prepared(e: ExperienceEntry, rid: str, decisions: list[SourceReview]) -> Prepared:
    """What a requirement link was prepared from: the story when linked, or the revision it was
    last refreshed to, whichever is newer."""
    rec = (e.requirement_versions or {}).get(rid)
    linked = (
        Prepared(rec["story_revision"], rec.get("story_digest"))
        if isinstance(rec, dict) and rec.get("story_revision") is not None
        else None
    )
    refreshed = next((d for d in decisions if d.decision == "refreshed"), None)
    if refreshed is not None and (linked is None or (linked.revision or 0) <= refreshed.to_revision):
        return Prepared(refreshed.to_revision, refreshed.to_digest)
    return linked or Prepared(None)
