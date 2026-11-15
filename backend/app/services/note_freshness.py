"""Whether a note's source changed since it was captured (Volume 13, prompt 6;
docs/STORY_FRESHNESS.md, "Notes").

A note captured from a question, a lesson or a coding problem records the source's version
(`notes.source_version`). When the source has a newer version that matters, the note says so,
shows what changed when the content keeps both versions, and lets the learner mark it reviewed.
"Mark reviewed" is recorded in `source_reviews` (holder_kind "note", decision "reviewed"), bound
to the version the learner was shown, and clears the notice until the source changes again. The
note itself is never changed: not its text, not its excerpt, not its revision.

What counts as a change: a question's correction marked significant (a typo fix is published as
not significant and never asks); any new version of a lesson or a coding problem (they don't mark
typo fixes). What can be shown: a question keeps every version's wording, so its title and prompt
are shown side by side; a lesson keeps only its own notes on what changed; a coding problem keeps
neither (its statement is corrected in its seed files). Interview notes have no versions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.questions import content_key, get_question
from app.content import state as content_state
from app.errors import AppError, NotFoundError
from app.learn import get_unit
from app.models import Note, Problem, SourceReview, TestCase
from app.schemas.freshness import FieldChange
from app.schemas.notes import NoteFreshness, NoteReview
from app.services.story_freshness import day

HOLDER = "note"
VERSIONED = ("question", "lesson", "problem")
NOUN = {"question": "question", "lesson": "lesson", "problem": "coding problem"}


def captured_version(n: Note) -> int | None:
    v = (n.source_version or "").strip()
    return int(v) if v.isdigit() else None


def source_key(n: Note) -> str | None:
    """How a review names the note's source: its library key."""
    if n.source_type not in VERSIONED or not n.source_id:
        return None
    if n.source_type == "question":
        return content_key(n.source_track or "", n.source_id)
    return n.source_id


@dataclass
class SourceNow:
    """A versioned source as it is now. `exists` False: it left the library."""

    exists: bool
    version: int | None = None
    retired: str | None = None
    # version -> (what the content says changed, whether it's a reason to ask)
    history: dict[int, tuple[str, bool]] = field(default_factory=dict)
    comparable: bool = False  # the content keeps earlier wording, so it can be shown side by side


def problem_versions(db: Session, slugs: set[str]) -> dict[str, int]:
    """Each coding problem's test version (the version its statement and tests are corrected under)."""
    if not slugs:
        return {}
    rows = db.execute(
        select(Problem.slug, func.max(TestCase.version))
        .join(TestCase, TestCase.problem_id == Problem.id, isouter=True)
        .where(Problem.slug.in_(sorted(slugs)))
        .group_by(Problem.slug)
    ).all()
    return {slug: int(v or 1) for slug, v in rows}


def source_now(n: Note, problems: dict[str, int]) -> SourceNow:
    snap = content_state.current()
    if n.source_type == "question":
        track, qid = n.source_track or "", n.source_id or ""
        q = get_question(track, qid) if track in CATALOG else None
        if q is None:
            return SourceNow(exists=False)
        key = content_key(track, qid)
        return SourceNow(
            exists=True,
            version=q.version,
            retired=snap.retired.get(("question", key)),
            history={
                c.version: (c.change_note, c.significant) for c in snap.corrections.get(("question", key), [])
            },
            comparable=True,
        )
    if n.source_type == "lesson":
        u = get_unit(n.source_id or "")
        if u is None:
            return SourceNow(exists=False)
        return SourceNow(
            exists=True,
            version=u.version,
            history={i + 1: (note, True) for i, note in enumerate(u.changes) if i > 0},
        )
    slug = n.source_id or ""
    if slug not in problems:
        return SourceNow(exists=False)
    version = problems[slug]
    return SourceNow(
        exists=True,
        version=version,
        retired=snap.retired.get(("problem", slug)),
        history={v: ("", True) for v in range(2, version + 1)},
    )


def _wording(n: Note, version: int) -> dict[str, str] | None:
    """A question as it read at `version` (title and prompt): what the note was captured from."""
    q = get_question(n.source_track or "", n.source_id or "", version)
    return {"Title": q.title, "Question": q.prompt} if q is not None else None


def digest_at(n: Note, version: int) -> str:
    """What the learner reviewed: the question's wording then; for a lesson or a problem, which one
    and which version (their earlier wording isn't kept)."""
    words = _wording(n, version) if n.source_type == "question" else None
    raw = repr(sorted(words.items())) if words else f"{n.source_type}:{source_key(n)}:{version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _review_text(r: SourceReview) -> str:
    start = f"from version {r.from_revision} " if r.from_revision else ""
    return f"Marked reviewed {start}at version {r.to_revision} on {day(r.created_at)}, by you."


class NoteFreshnessService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # --- reading ---------------------------------------------------------------------------

    def reviews(self, note_ids: list[str]) -> dict[str, list[SourceReview]]:
        """This account's reviews of these notes, newest first."""
        if not note_ids:
            return {}
        out: dict[str, list[SourceReview]] = {}
        for r in self.db.scalars(
            select(SourceReview)
            .where(
                SourceReview.user_id == self.user_id,
                SourceReview.holder_kind == HOLDER,
                SourceReview.holder_id.in_(note_ids),
            )
            .order_by(SourceReview.to_revision.desc(), SourceReview.created_at.desc())
        ):
            out.setdefault(r.holder_id, []).append(r)
        return out

    def problems_for(self, notes: list[Note]) -> dict[str, int]:
        return problem_versions(
            self.db, {n.source_id for n in notes if n.source_type == "problem" and n.source_id}
        )

    def assess(
        self, n: Note, rows: list[SourceReview], problems: dict[str, int], *, detail: bool = True
    ) -> NoteFreshness | None:
        """None for a note without a versioned source (no source, or an interview)."""
        if n.source_type not in VERSIONED or not n.source_id:
            return None
        kind = n.source_type
        noun = NOUN[kind]
        captured = captured_version(n)
        reviewed = rows[0].to_revision if rows else None
        reviews = [
            NoteReview(
                from_version=r.from_revision, to_version=r.to_revision, at=r.created_at, text=_review_text(r)
            )
            for r in rows[:5]
        ]
        now = source_now(n, problems)
        base = dict(
            kind=kind,
            captured_version=captured,
            reviewed_version=reviewed,
            current_version=now.version,
            reviews=reviews,
        )
        if not now.exists:
            return NoteFreshness(
                state="unavailable",
                text=f"This {noun} is no longer in the library. Your note keeps what you captured.",
                **base,
            )
        assert now.version is not None
        if now.retired is not None:
            return NoteFreshness(
                state="retired",
                text=f"This {noun} was retired: {now.retired} It still opens, and your note keeps what you captured.",
                **base,
            )
        seen = max(v for v in (captured, reviewed) if v is not None) if (captured or reviewed) else None
        if seen is None:
            return NoteFreshness(
                state="unknown",
                text=(
                    f"Whether the {noun} changed since isn't known: this note was captured before versions "
                    f"were recorded. It's version {now.version} now; mark it reviewed to be told about later changes."
                ),
                **base,
            )
        newer = {v: h for v, h in now.history.items() if seen < v <= now.version}
        asks = [v for v, (_, significant) in newer.items() if significant]
        if not asks and seen >= now.version:
            text = (
                f"You marked it reviewed at version {reviewed} on {day(rows[0].created_at)}."
                if reviewed is not None and reviewed >= (captured or 0) and rows
                else f"Up to date with the {noun} (version {now.version})."
            )
            return NoteFreshness(state="current", text=text, **base)
        if not asks:
            return NoteFreshness(
                state="current",
                text=(
                    f"Up to date: the {noun} was corrected since (version {seen}, now {now.version}), but only "
                    "for typos or wording marked minor, so there's nothing to review."
                ),
                **base,
            )
        if reviewed is not None and reviewed >= (captured or 0):
            text = (
                f"The {noun} changed again since you marked it reviewed at version {reviewed} (now version "
                f"{now.version}). Review whether your note still fits."
            )
        else:
            text = (
                f"The {noun} changed since you captured this note (version {seen}, now {now.version}). Review "
                "whether your note still fits."
            )
        changes: list[FieldChange] = []
        if detail and now.comparable:
            before, after = _wording(n, seen), _wording(n, now.version)
            if before is not None and after is not None:
                changes = [
                    FieldChange(field=f, before=before[f], after=after[f])
                    for f in before
                    if " ".join(before[f].split()) != " ".join(after[f].split())
                ]
        if not now.comparable:
            text += (
                f" The {noun} doesn't keep its earlier wording, so what changed can't be shown side by side."
            )
        notes = [f"Version {v}: {note}" for v, (note, _) in sorted(newer.items()) if note]
        return NoteFreshness(
            state="needs_review",
            text=text,
            changes=changes,
            change_notes=notes if detail else [],
            comparable=now.comparable,
            **base,
        )

    # --- deciding --------------------------------------------------------------------------

    def mark_reviewed(self, n: Note, reviewed_version: int) -> NoteFreshness:
        """Record "Mark reviewed" for the version the learner was shown. A newer version since is
        said (the notice stays for it), never reviewed silently; a repeat records nothing more. The
        note isn't touched."""
        problems = self.problems_for([n])
        now = source_now(n, problems)
        key = source_key(n)
        if key is None:
            raise AppError("This note's source has no versions to review.", code="not_versioned")
        if not now.exists or now.version is None:
            raise NotFoundError(f"This {NOUN[n.source_type or 'question']} is no longer in the library")
        if reviewed_version > now.version:
            raise AppError(
                f"Version {reviewed_version} doesn't exist yet (it's version {now.version} now).",
                code="invalid_version",
            )
        rows = self.reviews([n.id]).get(n.id, [])
        captured = captured_version(n)
        seen = max(
            [v for v in (captured, rows[0].to_revision if rows else None) if v is not None], default=None
        )
        if seen is None or reviewed_version > seen:
            self.db.add(
                SourceReview(
                    user_id=self.user_id,
                    holder_kind=HOLDER,
                    holder_id=n.id,
                    source_kind=n.source_type or "",
                    source_id=key,
                    from_revision=seen,
                    to_revision=reviewed_version,
                    to_digest=digest_at(n, reviewed_version),
                    decision="reviewed",
                    created_at=datetime.now(UTC),
                )
            )
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()  # the same review from another tab got there first: one row
            rows = self.reviews([n.id]).get(n.id, [])
        out = self.assess(n, rows, problems)
        assert out is not None
        return out

    def export(self, note_ids: list[str]) -> dict[str, list[dict]]:
        return {
            nid: [
                {
                    "decision": r.decision,
                    "from_version": r.from_revision,
                    "to_version": r.to_revision,
                    "at": r.created_at.isoformat(),
                }
                for r in sorted(rows, key=lambda r: (r.created_at, r.to_revision))
            ]
            for nid, rows in self.reviews(note_ids).items()
        }


def forget_notes(db: Session, user_id: str, note_ids: list[str]) -> None:
    """A note's reviews go with it."""
    if note_ids:
        db.execute(
            delete(SourceReview).where(
                SourceReview.user_id == user_id,
                SourceReview.holder_kind == HOLDER,
                SourceReview.holder_id.in_(note_ids),
            )
        )
