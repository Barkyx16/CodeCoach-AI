"""The personal practice notebook.

- Notes are private: every operation loads the note by id *and* owner; anything else is a 404.
- A note's source (question, problem, lesson, interview) is checked when the note is created and
  stored as a stable id, version (when one exists) and title snapshot. When the source later
  leaves the library the note stays, marked "source no longer available".
- Text edits carry the revision they started from; an edit based on an older revision is refused
  with 409 `note_conflict` and the current note, so the client can show both versions instead of
  silently replacing newer text. Pin and archive don't touch text and don't need a revision.
- Deleting starts a 10-minute undo window; after it the note is purged.
- "Key points" is a deterministic helper (no AI model): it lists the note's own sentences that
  state an action or a conclusion. Nothing is saved until the learner accepts the points.
- Note text is never logged.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.questions import get_question
from app.db.locking import lock_for_update
from app.errors import AppError, ConflictError, GoneError, NotFoundError
from app.learn import get_unit
from app.models import Note, PracticeSession, Problem, User, new_id
from app.schemas.common import SaveReplay
from app.schemas.notes import (
    MAX_TAG,
    DeletedOut,
    KeyPoints,
    NoteIn,
    NoteOut,
    NotePage,
    NotePatch,
    NoteSummary,
    SourceIn,
    SourceOut,
    TagCount,
)
from app.services import request_keys, update_receipts
from app.services.lifecycle import archive_note_now

UNDO_WINDOW = timedelta(minutes=10)
MAX_NOTES = 2_000
MAX_PINNED = 5
_TAG_RE = re.compile(r"[^a-z0-9 +#.\-]")


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for t in tags:
        tag = _TAG_RE.sub("", t.strip().lower())[:MAX_TAG].strip()
        if tag and tag not in out:
            out.append(tag)
    return out


def _snippet(n: Note) -> str:
    text = re.sub(r"[#*_`>\[\]()!-]+", " ", n.body or n.reflection or "")
    text = " ".join(text.split())
    return text[:160] + ("…" if len(text) > 160 else "")


class Notebook:
    def __init__(self, db: Session):
        self.db = db

    # --- sources -------------------------------------------------------------------------------

    def _resolve(self, user: User, src: SourceIn) -> tuple[str, str | None, str | None, str]:
        """(stored id, track, version, title) for a source the user may reference, or 404."""
        if src.type == "question":
            q = get_question(src.track or "", src.id) if src.track in CATALOG else None
            if q is None:
                raise NotFoundError("That question isn't in the library")
            return src.id, src.track, None, q.title
        if src.type == "problem":
            title = self.db.scalar(select(Problem.title).where(Problem.slug == src.id))
            if title is None:
                raise NotFoundError("That problem isn't in the library")
            return src.id, None, None, title
        if src.type == "lesson":
            u = get_unit(src.id)
            if u is None:
                raise NotFoundError("That lesson doesn't exist")
            return src.id, u.track, str(u.version), u.title
        s = self.db.get(PracticeSession, src.id)
        if s is None or s.user_id != user.id:
            raise NotFoundError("Interview not found")
        career = CATALOG[s.track].title if s.track in CATALOG else None
        title = f"{career} interview" if career else "Mock interview"
        if src.question_index is not None:
            title += f", question {src.question_index + 1}"
            return f"{s.id}#q{src.question_index}", s.track, None, title
        return s.id, s.track, None, title

    def _source_out(self, n: Note) -> SourceOut | None:
        if not n.source_type or not n.source_id:
            return None
        sid, track, available, href = n.source_id, n.source_track, True, None
        if n.source_type == "question":
            available = track in CATALOG and get_question(track or "", sid) is not None
            href = f"/careers/{track}/questions/{sid}"
        elif n.source_type == "problem":
            available = self.db.scalar(select(Problem.id).where(Problem.slug == sid)) is not None
            href = f"/problems/{sid}"
        elif n.source_type == "lesson":
            available = get_unit(sid) is not None
            href = f"/learn/{sid}"
        else:
            session_id, _, q = sid.partition("#")
            s = self.db.get(PracticeSession, session_id)
            available = s is not None and s.user_id == n.user_id
            href = f"/interviews/{session_id}" + (f"?item={q}" if q else "")
        return SourceOut(
            type=n.source_type,
            id=sid,
            track=track,
            version=n.source_version,
            title=n.source_title,
            href=href if available else None,
            available=available,
            career_title=CATALOG[track].title if track in CATALOG else None,
        )

    # --- reading -------------------------------------------------------------------------------

    def _purge(self, user: User) -> None:
        cutoff = _now() - UNDO_WINDOW
        self.db.execute(
            delete(Note).where(
                Note.user_id == user.id, Note.deleted_at.is_not(None), Note.deleted_at < cutoff
            )
        )
        self.db.commit()

    def _note(self, user: User, note_id: str) -> Note:
        n = self.db.get(Note, note_id)
        if n is None or n.user_id != user.id or n.deleted_at is not None:
            raise NotFoundError("Note not found")
        return n

    def _summary(self, n: Note) -> NoteSummary:
        return NoteSummary(
            id=n.id,
            title=n.title or "Untitled note",
            snippet=_snippet(n),
            tags=list(n.tags or []),
            source=self._source_out(n),
            pinned=n.pinned,
            archived=n.archived,
            revision=n.revision,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )

    def out(self, n: Note) -> NoteOut:
        return NoteOut(
            **self._summary(n).model_dump(),
            body=n.body,
            reflection=n.reflection,
            excerpt=n.excerpt,
            excerpt_kind=n.excerpt_kind,
            key_points=n.key_points,
        )

    def get(self, user: User, note_id: str) -> NoteOut:
        return self.out(self._note(user, note_id))

    def search(
        self,
        user: User,
        *,
        q: str | None,
        career: str | None,
        source_type: str | None,
        tag: str | None,
        status: str,
        page: int,
        source_id: str | None = None,
        page_size: int,
    ) -> NotePage:
        self._purge(user)
        rows = list(
            self.db.scalars(
                select(Note)
                .where(Note.user_id == user.id, Note.deleted_at.is_(None))
                .order_by(Note.updated_at.desc(), Note.id)
            ).all()
        )
        live = [n for n in rows if status == "all" or n.archived == (status == "archived")]
        tags = Counter(t for n in live for t in (n.tags or []))
        careers = Counter(n.source_track for n in live if n.source_track)
        words = [w for w in (q or "").lower().split() if w]

        def keep(n: Note) -> bool:
            hay = " ".join(
                (n.title, n.body, n.reflection, " ".join(n.tags or []), n.source_title or "")
            ).lower()
            return (
                all(w in hay for w in words)
                and (not career or n.source_track == career)
                and (not source_type or n.source_type == source_type)
                and (not tag or tag in (n.tags or []))
                and (
                    not source_id
                    or n.source_id == source_id
                    or (n.source_id or "").startswith(f"{source_id}#")
                )
            )

        hits = [n for n in live if keep(n)]
        hits.sort(key=lambda n: not n.pinned)  # stable: pinned first, then most recently updated
        start = (page - 1) * page_size
        return NotePage(
            items=[self._summary(n) for n in hits[start : start + page_size]],
            total=len(hits),
            page=page,
            page_size=page_size,
            tags=[TagCount(tag=t, count=c) for t, c in sorted(tags.items(), key=lambda x: (-x[1], x[0]))],
            careers=[TagCount(tag=t, count=c) for t, c in sorted(careers.items())],
            pinned_limit=MAX_PINNED,
        )

    # --- writing -------------------------------------------------------------------------------

    def create(self, user: User, body: NoteIn, *, commit: bool = True) -> NoteOut:
        """With commit=False the note joins the caller's transaction (flushed, not committed), so it
        is saved together with whatever the caller saves, or not at all. A create repeated with the
        same `client_request_id` returns the note the first one made.

        A note's key stands for creating this note from this source, not for its text: autosave
        sends the create again with newer text when the first reply was lost, gets the note back,
        then saves the newer text as an update (with its revision check). So the text may differ;
        the source may not: the same key for a note on something else is a 409."""
        if body.copy_of is not None:
            return self.copy(user, body)
        if body.client_request_id and (made := self._by_request(user, body.client_request_id)):
            if not self._same_source(made, body.source):
                raise request_keys.reused("note")
            return self.out(made)
        count = self.db.scalar(select(func.count()).select_from(Note).where(Note.user_id == user.id)) or 0
        if count >= MAX_NOTES:
            raise AppError(f"You can keep up to {MAX_NOTES} notes.", code="too_many_notes")
        n = Note(
            user_id=user.id,
            title=body.title.strip(),
            body=body.body,
            reflection=body.reflection,
            tags=clean_tags(body.tags),
            excerpt=body.excerpt or None,
            excerpt_kind=body.excerpt_kind if body.excerpt else None,
        )
        if body.source is not None:
            n.source_type = body.source.type
            n.source_id, n.source_track, n.source_version, n.source_title = self._resolve(user, body.source)
        n.client_request_id = body.client_request_id
        self.db.add(n)
        try:
            if commit:
                self.db.commit()
            else:
                self.db.flush()
        except IntegrityError:
            if not commit or not body.client_request_id:
                raise  # inside a caller's transaction, the caller decides what to do
            # The same create, sent twice at the same moment: the other copy made the note.
            self.db.rollback()
            made = self._by_request(user, body.client_request_id)
            if made is None:
                raise
            if not self._same_source(made, body.source):
                raise request_keys.reused("note") from None
            return self.out(made)
        return self.out(n)

    def copy(self, user: User, body: NoteIn) -> NoteOut:
        """Keep both after a conflict: the learner's version as a separate note, made once per
        decision (Volume 8, prompt 4; docs/RECOVERY.md).

        The key stands for this copy of this text: a retry (a double click, a lost reply, a reload)
        gets the copy already made. A receipt, written with the note, says which note the key made
        and what text it stood for; the same key with other text is refused. A copy made and then
        deleted is never made again by a retry (410 `copy_deleted`): only a new key, the learner's
        deliberate choice, makes another. The source note is only read: the question or problem it's
        about comes along if it's the caller's own; anyone else's id is treated as missing, and no
        link back to it is kept."""
        key = body.client_request_id
        if not key:
            raise AppError(
                "A copy needs a client_request_id, so a retry can't make it twice.",
                code="client_request_id_required",
            )
        fields = {
            "title": body.title.strip(),
            "body": body.body,
            "reflection": body.reflection,
            "tags": clean_tags(body.tags),
        }
        print_ = request_keys.fingerprint("note.copy", {"of": body.copy_of, **fields})

        def made_before() -> NoteOut | None:
            r = update_receipts.by_key(self.db, user, key)
            if r is not None:
                if r.entity != "note_copy" or not request_keys.same(r.request_fingerprint, print_):
                    raise request_keys.reused("copy")
                made = self.db.get(Note, r.entity_id)
            else:  # no receipt (it expired): the note's own unique key still finds the copy
                made = self._by_request(user, key)
            if made is None and r is None:
                return None
            if made is None or made.user_id != user.id or made.deleted_at is not None:
                raise GoneError(
                    "That copy was made, then deleted. Nothing was made again: make a new copy to keep your version.",
                    code="copy_deleted",
                )
            return self.out(made)

        if (done := made_before()) is not None:
            return done
        count = self.db.scalar(select(func.count()).select_from(Note).where(Note.user_id == user.id)) or 0
        if count >= MAX_NOTES:
            raise AppError(f"You can keep up to {MAX_NOTES} notes.", code="too_many_notes")
        src = self.db.get(Note, body.copy_of)
        own = src if src is not None and src.user_id == user.id else None
        n = Note(id=new_id(), user_id=user.id, client_request_id=key, **fields)
        if own is not None and own.source_type:
            n.source_type, n.source_id, n.source_track = own.source_type, own.source_id, own.source_track
            n.source_version, n.source_title = own.source_version, own.source_title
        self.db.add(n)
        update_receipts.record(self.db, user, key, "note_copy", n.id, 0, 1, print_)
        try:
            self.db.commit()
        except IntegrityError:  # the same copy, sent twice at once: the other one made it
            self.db.rollback()
            if (done := made_before()) is not None:
                return done
            raise
        return self.out(n)

    @staticmethod
    def _same_source(n: Note, src: SourceIn | None) -> bool:
        if src is None:
            return n.source_type is None
        sid = src.id
        if src.type not in ("question", "problem", "lesson") and src.question_index is not None:
            sid = f"{src.id}#q{src.question_index}"  # as _resolve stores it
        return (n.source_type, n.source_id) == (src.type, sid)

    def _by_request(self, user: User, key: str) -> Note | None:
        return self.db.scalar(select(Note).where(Note.user_id == user.id, Note.client_request_id == key))

    def update(self, user: User, note_id: str, patch: NotePatch) -> NoteOut:
        n = self._note(user, note_id)
        text = {
            k: v
            for k, v in patch.model_dump(
                include={"title", "body", "reflection", "tags", "key_points"}
            ).items()
            if v is not None
        }
        if text:
            if patch.base_revision is None:
                raise AppError("Send base_revision with text changes.", code="base_revision_required")
            lock_for_update(self.db, n)  # a save sent at the same moment waits, then sees the new revision
            print_ = update_receipts.fingerprint(
                "note",
                n.id,
                patch.base_revision,
                patch.model_dump(mode="json", exclude={"client_request_id", "base_revision"}),
            )
            done = update_receipts.find(
                self.db, user, patch.client_request_id, "note", n.id, patch.base_revision, print_
            )
            if done is not None:
                # This save went through already; its reply was lost. The note as it is now.
                out = self.out(n)
                out.save_replay = SaveReplay(
                    accepted_revision=done.accepted_revision, current_revision=n.revision
                )
                return out
            if patch.base_revision != n.revision:
                raise ConflictError(
                    "This note was changed somewhere else since you started editing.",
                    code="note_conflict",
                    details={"current": self.out(n).model_dump(mode="json")},
                )
        if patch.pinned and not n.pinned:
            pinned = (
                self.db.scalar(
                    select(func.count())
                    .select_from(Note)
                    .where(Note.user_id == user.id, Note.pinned.is_(True), Note.deleted_at.is_(None))
                )
                or 0
            )
            if pinned >= MAX_PINNED:
                raise ConflictError(
                    f"You can pin up to {MAX_PINNED} notes. Unpin one first.", code="pin_limit"
                )
        if "title" in text:
            n.title = text["title"].strip()
        if "body" in text:
            n.body = text["body"]
        if "reflection" in text:
            n.reflection = text["reflection"]
        if "tags" in text:
            n.tags = clean_tags(text["tags"])
        if "key_points" in text:
            n.key_points = [p.strip()[:300] for p in text["key_points"] if p.strip()] or None
        if patch.pinned is not None:
            n.pinned = patch.pinned
        if patch.archived is not None:
            if patch.archived:
                archive_note_now(n)  # what the archive preview lists (docs/LIFECYCLE.md)
            else:
                n.archived = False
        if text:
            n.revision += 1  # pin/archive never conflict with text edits in another tab
            assert patch.base_revision is not None
            update_receipts.record(
                self.db, user, patch.client_request_id, "note", n.id, patch.base_revision, n.revision, print_
            )
        n.updated_at = _now()
        self.db.commit()
        return self.out(n)

    def delete(self, user: User, note_id: str) -> DeletedOut:
        n = self._note(user, note_id)
        n.deleted_at = _now()
        n.pinned = False
        self.db.commit()
        return DeletedOut(id=n.id, restorable_until=_aware(n.deleted_at) + UNDO_WINDOW)

    def restore(self, user: User, note_id: str) -> NoteOut:
        n = self.db.get(Note, note_id)
        if (
            n is None
            or n.user_id != user.id
            or n.deleted_at is None
            or _aware(n.deleted_at) < _now() - UNDO_WINDOW
        ):
            raise NotFoundError("Nothing to restore: the undo window has passed or the note isn't deleted")
        n.deleted_at = None
        self.db.commit()
        return self.out(n)

    def key_points(self, user: User, note_id: str) -> KeyPoints:
        n = self._note(user, note_id)
        return KeyPoints(points=extract_key_points(f"{n.body}\n{n.reflection}"), method=KEY_POINTS_METHOD)


KEY_POINTS_METHOD = (
    "Built in, no AI model: these are your own sentences that state an action or a conclusion "
    "(e.g. 'next time', 'remember', 'should', 'learned'), plus your list items. Nothing is saved "
    "until you accept them."
)
_CUES = re.compile(
    r"\b(next time|remember|should|must|need to|don't|do not|always|never|learned|learnt|key|important|"
    r"todo|to do|follow up|try|practi[cs]e|avoid|because)\b",
    re.I,
)


def extract_key_points(text: str, limit: int = 6) -> list[str]:
    points: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        bullet = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)", line)
        candidates = [bullet.group(1)] if bullet else re.split(r"(?<=[.!?])\s+", line)
        for c in candidates:
            c = re.sub(r"[*_`#>]+", "", c).strip()
            if len(c) < 6 or c in points:
                continue
            if bullet or _CUES.search(c):
                points.append(c[:300])
            if len(points) >= limit:
                return points
    return points
