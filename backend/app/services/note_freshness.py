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

The same rule serves saved items and collections (Volume 14, prompt 7; docs/STORY_FRESHNESS.md,
"Saved items and collections"): `SourceFreshness` judges any holder of a versioned source (a
`SourceRef`: which source, and the version it was taken at) and records its reviews under its own
holder kind; only the words differ ("captured" for a note, "saved" for a saved item). There is no
second rule.
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


@dataclass(frozen=True)
class SourceRef:
    """A versioned source as something holds it: which one, and the version it was taken at
    (None: taken before versions were recorded)."""

    kind: str  # question | lesson | problem
    id: str
    track: str | None
    captured: int | None


@dataclass(frozen=True)
class Holder:
    """What holds the source, in the words its notices use."""

    kind: str  # source_reviews.holder_kind
    noun: str
    made: str  # how it got its version: "captured", "saved", "added"
    keeps: str  # what stays, whatever the source does (lower case: it ends a sentence)
    fits: str  # what the learner reviews


NOTE = Holder(
    kind=HOLDER,
    noun="note",
    made="captured",
    keeps="your note keeps what you captured",
    fits="whether your note still fits",
)


def captured_version(n: Note) -> int | None:
    v = (n.source_version or "").strip()
    return int(v) if v.isdigit() else None


def note_ref(n: Note) -> SourceRef | None:
    if n.source_type not in VERSIONED or not n.source_id:
        return None
    return SourceRef(kind=n.source_type, id=n.source_id, track=n.source_track, captured=captured_version(n))


def ref_key(ref: SourceRef) -> str:
    """How a review names a source: its library key."""
    return content_key(ref.track or "", ref.id) if ref.kind == "question" else ref.id


def source_key(n: Note) -> str | None:
    """How a review names the note's source: its library key."""
    ref = note_ref(n)
    return ref_key(ref) if ref is not None else None


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


def source_now(ref: SourceRef, problems: dict[str, int]) -> SourceNow:
    snap = content_state.current()
    if ref.kind == "question":
        track, qid = ref.track or "", ref.id
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
    if ref.kind == "lesson":
        u = get_unit(ref.id)
        if u is None:
            return SourceNow(exists=False)
        return SourceNow(
            exists=True,
            version=u.version,
            history={i + 1: (note, (i + 1) not in u.minor) for i, note in enumerate(u.changes) if i > 0},
        )
    slug = ref.id
    if slug not in problems:
        return SourceNow(exists=False)
    version = problems[slug]
    return SourceNow(
        exists=True,
        version=version,
        retired=snap.retired.get(("problem", slug)),
        history={v: ("", True) for v in range(2, version + 1)},
    )


def _wording(ref: SourceRef, version: int) -> dict[str, str] | None:
    """A question as it read at `version` (title and prompt): what it was taken from."""
    q = get_question(ref.track or "", ref.id, version)
    return {"Title": q.title, "Question": q.prompt} if q is not None else None


def digest_at(ref: SourceRef, version: int) -> str:
    """What the learner reviewed: the question's wording then; for a lesson or a problem, which one
    and which version (their earlier wording isn't kept)."""
    words = _wording(ref, version) if ref.kind == "question" else None
    raw = repr(sorted(words.items())) if words else f"{ref.kind}:{ref_key(ref)}:{version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def known_version(ref: SourceRef, version: object, problems: dict[str, int]) -> int | None:
    """A version read from a file, if it's one this source has had (1 to now); otherwise None, so
    it reads "not known" rather than up to date (a restore never takes the current version)."""
    now = source_now(ref, problems)
    if not isinstance(version, int) or isinstance(version, bool) or now.version is None:
        return None
    return version if 1 <= version <= now.version else None


def _review_text(r: SourceReview) -> str:
    start = f"from version {r.from_revision} " if r.from_revision else ""
    return f"Marked reviewed {start}at version {r.to_revision} on {day(r.created_at)}, by you."


class SourceFreshness:
    """The one rule, for any holder (docs/STORY_FRESHNESS.md): a note, a saved item, an item in a
    collection. Reviews are this account's, under the holder's kind."""

    def __init__(self, db: Session, user_id: str, holder: Holder = NOTE):
        self.db = db
        self.user_id = user_id
        self.holder = holder

    # --- reading ---------------------------------------------------------------------------

    def reviews(self, note_ids: list[str]) -> dict[str, list[SourceReview]]:
        """This account's reviews of these holders, newest first."""
        if not note_ids:
            return {}
        out: dict[str, list[SourceReview]] = {}
        for r in self.db.scalars(
            select(SourceReview)
            .where(
                SourceReview.user_id == self.user_id,
                SourceReview.holder_kind == self.holder.kind,
                SourceReview.holder_id.in_(note_ids),
            )
            .order_by(SourceReview.to_revision.desc(), SourceReview.created_at.desc())
        ):
            out.setdefault(r.holder_id, []).append(r)
        return out

    def problems_for_refs(self, refs: list[SourceRef]) -> dict[str, int]:
        return problem_versions(self.db, {r.id for r in refs if r.kind == "problem"})

    def assess_ref(
        self, ref: SourceRef, rows: list[SourceReview], problems: dict[str, int], *, detail: bool = True
    ) -> NoteFreshness:
        h = self.holder
        kind = ref.kind
        noun = NOUN[kind]
        captured = ref.captured
        reviewed = rows[0].to_revision if rows else None
        reviews = [
            NoteReview(
                from_version=r.from_revision, to_version=r.to_revision, at=r.created_at, text=_review_text(r)
            )
            for r in rows[:5]
        ]
        now = source_now(ref, problems)
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
                text=f"This {noun} is no longer in the library. {h.keeps[0].upper()}{h.keeps[1:]}.",
                **base,
            )
        assert now.version is not None
        if now.retired is not None:
            return NoteFreshness(
                state="retired",
                text=f"This {noun} was retired: {now.retired} It still opens, and {h.keeps}.",
                **base,
            )
        seen = max(v for v in (captured, reviewed) if v is not None) if (captured or reviewed) else None
        if seen is None:
            return NoteFreshness(
                state="unknown",
                text=(
                    f"Whether the {noun} changed since isn't known: this {h.noun} was {h.made} before versions "
                    f"were recorded. It's version {now.version} now; mark it reviewed to be told about later changes."
                ),
                **base,
            )
        newer = {v: hist for v, hist in now.history.items() if seen < v <= now.version}
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
                f"{now.version}). Review {h.fits}."
            )
        else:
            text = (
                f"The {noun} changed since you {h.made} this {h.noun} (version {seen}, now {now.version}). "
                f"Review {h.fits}."
            )
        changes: list[FieldChange] = []
        if detail and now.comparable:
            before, after = _wording(ref, seen), _wording(ref, now.version)
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
        notes = [
            f"Version {v}: {note}{'' if significant else ' (minor)'}"
            for v, (note, significant) in sorted(newer.items())
            if note
        ]
        return NoteFreshness(
            state="needs_review",
            text=text,
            changes=changes,
            change_notes=notes if detail else [],
            comparable=now.comparable,
            **base,
        )

    # --- deciding --------------------------------------------------------------------------

    def review_ref(self, holder_id: str, ref: SourceRef, reviewed_version: int) -> NoteFreshness:
        """Record "Mark reviewed" for the version the learner was shown. A newer version since is
        said (the notice stays for it), never reviewed silently; a repeat records nothing more. What
        holds the source isn't touched."""
        problems = self.problems_for_refs([ref])
        now = source_now(ref, problems)
        if not now.exists or now.version is None:
            raise NotFoundError(f"This {NOUN[ref.kind]} is no longer in the library")
        if reviewed_version > now.version:
            raise AppError(
                f"Version {reviewed_version} doesn't exist yet (it's version {now.version} now).",
                code="invalid_version",
            )
        rows = self.reviews([holder_id]).get(holder_id, [])
        seen = max(
            [v for v in (ref.captured, rows[0].to_revision if rows else None) if v is not None], default=None
        )
        if seen is None or reviewed_version > seen:
            self.db.add(
                SourceReview(
                    user_id=self.user_id,
                    holder_kind=self.holder.kind,
                    holder_id=holder_id,
                    source_kind=ref.kind,
                    source_id=ref_key(ref),
                    from_revision=seen,
                    to_revision=reviewed_version,
                    to_digest=digest_at(ref, reviewed_version),
                    decision="reviewed",
                    created_at=datetime.now(UTC),
                )
            )
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()  # the same review from another tab got there first: one row
            rows = self.reviews([holder_id]).get(holder_id, [])
        return self.assess_ref(ref, rows, problems)

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

    def restore_reviews(self, holder_id: str, ref: SourceRef, rows: object, problems: dict[str, int]) -> int:
        """Bring back a holder's "Mark reviewed" from a backup file, under its new id: only reviews
        of versions this source has had, at most 20, each once. Returns how many."""
        if not isinstance(rows, list):
            return 0
        added: set[int] = set()
        for r in rows[:20]:
            if not isinstance(r, dict) or r.get("decision") != "reviewed":
                continue
            to = known_version(ref, r.get("to_version"), problems)
            if to is None or to in added:
                continue
            frm = known_version(ref, r.get("from_version"), problems)
            at = r.get("at")
            try:
                when = datetime.fromisoformat(at) if isinstance(at, str) else datetime.now(UTC)
            except ValueError:
                when = datetime.now(UTC)
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            self.db.add(
                SourceReview(
                    user_id=self.user_id,
                    holder_kind=self.holder.kind,
                    holder_id=holder_id,
                    source_kind=ref.kind,
                    source_id=ref_key(ref),
                    from_revision=frm,
                    to_revision=to,
                    to_digest=digest_at(ref, to),
                    decision="reviewed",
                    created_at=min(when, datetime.now(UTC)),
                )
            )
            added.add(to)
        return len(added)


class NoteFreshnessService(SourceFreshness):
    """Notes (Volume 13, prompt 6): the rule above, held by a note."""

    def __init__(self, db: Session, user_id: str):
        super().__init__(db, user_id, NOTE)

    def problems_for(self, notes: list[Note]) -> dict[str, int]:
        return self.problems_for_refs([r for r in (note_ref(n) for n in notes) if r is not None])

    def assess(
        self, n: Note, rows: list[SourceReview], problems: dict[str, int], *, detail: bool = True
    ) -> NoteFreshness | None:
        """None for a note without a versioned source (no source, or an interview)."""
        ref = note_ref(n)
        return self.assess_ref(ref, rows, problems, detail=detail) if ref is not None else None

    def mark_reviewed(self, n: Note, reviewed_version: int) -> NoteFreshness:
        ref = note_ref(n)
        if ref is None:
            raise AppError("This note's source has no versions to review.", code="not_versioned")
        return self.review_ref(n.id, ref, reviewed_version)


def forget(db: Session, user_id: str, holder_kind: str, holder_ids: list[str]) -> None:
    """A holder's reviews go with it."""
    if holder_ids:
        db.execute(
            delete(SourceReview).where(
                SourceReview.user_id == user_id,
                SourceReview.holder_kind == holder_kind,
                SourceReview.holder_id.in_(holder_ids),
            )
        )


def forget_notes(db: Session, user_id: str, note_ids: list[str]) -> None:
    """A note's reviews go with it."""
    forget(db, user_id, HOLDER, note_ids)
