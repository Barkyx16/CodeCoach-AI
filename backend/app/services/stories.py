"""The story bank: a learner's own STAR stories, shared with job targets, with every save kept.

Stories are private to their owner (every query filters by user). Text is stored as written
(control characters removed) and only ever shown back as plain text. Practising a story creates
an ordinary graded answer that points at the story; the story itself never changes because of it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.eligibility import feedback_eligibility
from app.careers.questions import get_question, is_retired
from app.errors import AppError, ConflictError, NotFoundError
from app.models import ExperienceEntry, PracticeAnswer, RoleTarget, StoryRevision, User
from app.schemas.stories import (
    SECTIONS,
    StoryAssistIn,
    StoryAssistOut,
    StoryCreate,
    StoryFields,
    StoryOut,
    StoryPractice,
    StoryQuestionLink,
    StoryRevisionOut,
    StorySummary,
    StoryTargetLink,
    StoryUpdate,
)
from app.services import story_assist

MAX_STORIES = 200
MAX_REVISIONS = 100
# What a revision snapshots: everything the learner wrote.
SNAPSHOT_FIELDS = (
    "title",
    "track",
    "context",
    *SECTIONS,
    "notes",
    "evidence",
    "competencies",
    "tags",
    "short_version",
    "long_version",
    "target_id",
    "question_refs",
)
TEXT_FIELDS = ("title", *SECTIONS, "notes", "evidence", "short_version", "long_version")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_REF = re.compile(r"^[a-z0-9-]{1,64}/[A-Za-z0-9_-]{1,64}$")

# Details that may identify a person; only ever pointed out, never blocked or changed.
_PRIVACY = [
    (
        re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+"),
        "“{m}” may identify someone. “The patient”, “a client” or “a colleague” works just as well.",
    ),
    (re.compile(r"\b\d{6,}\b"), "“{m}” looks like an ID or record number. Leave identifiers out."),
    (
        re.compile(r"\b\d{1,2}/\d{1,2}/(?:19|20)\d{2}\b"),
        "“{m}” looks like a date of birth or a record date. Leave it out unless it's needed.",
    ),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "“{m}” is an email address. Leave contact details out."),
    (re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)"), "“{m}” looks like a phone number. Leave contact details out."),
]


def clean(text: str | None) -> str:
    return _CONTROL.sub("", text or "").strip()


def snapshot(e: ExperienceEntry) -> dict:
    return {f: getattr(e, f) for f in SNAPSHOT_FIELDS}


def record_revision(db: Session, e: ExperienceEntry, reason: str, *, bump: bool) -> None:
    """Keep this version. `bump` moves the story to its next revision number first."""
    if bump:
        e.revision = (e.revision or 1) + 1
    db.add(StoryRevision(story_id=e.id, revision=e.revision, reason=reason, fields=snapshot(e)))
    # Keep the newest MAX_REVISIONS; the very first one is kept too, so the original survives.
    count = (
        db.scalar(select(func.count()).select_from(StoryRevision).where(StoryRevision.story_id == e.id)) or 0
    )
    if count > MAX_REVISIONS:
        old = db.scalars(
            select(StoryRevision)
            .where(StoryRevision.story_id == e.id, StoryRevision.revision > 1)
            .order_by(StoryRevision.revision)
            .limit(count - MAX_REVISIONS)
        ).all()
        for r in old:
            db.delete(r)


def missing_sections(e: ExperienceEntry) -> list[str]:
    return story_assist.is_complete({s: getattr(e, s) or "" for s in SECTIONS})


def privacy_hints(e: ExperienceEntry) -> list[str]:
    text = "\n".join(getattr(e, f) or "" for f in TEXT_FIELDS)
    hints: list[str] = []
    for pattern, message in _PRIVACY:
        for m in pattern.findall(text)[:3]:
            hint = message.format(m=m.strip())
            if hint not in hints:
                hints.append(hint)
    return hints[:8]


class Stories:
    def __init__(self, db: Session):
        self.db = db

    # --- reads --------------------------------------------------------------------------------

    def _get(self, user: User, story_id: str) -> ExperienceEntry:
        e = self.db.get(ExperienceEntry, story_id)
        if e is None or e.user_id != user.id:
            raise NotFoundError("Story not found")
        return e

    def _target(self, e: ExperienceEntry) -> StoryTargetLink | None:
        if not e.target_id:
            return None
        t = self.db.get(RoleTarget, e.target_id)
        return StoryTargetLink(id=t.id, title=t.title) if t else None

    def _practice_counts(self, user: User) -> dict[str, int]:
        rows = self.db.execute(
            select(PracticeAnswer.story_id, func.count())
            .where(PracticeAnswer.user_id == user.id, PracticeAnswer.story_id.is_not(None))
            .group_by(PracticeAnswer.story_id)
        ).all()
        return {str(sid): int(n) for sid, n in rows if sid}

    def _summary(self, e: ExperienceEntry, practice_count: int) -> StorySummary:
        preview = (e.situation or e.action or e.result or "").strip().replace("\n", " ")
        return StorySummary(
            id=e.id,
            title=e.title,
            track=e.track,
            context=e.context,
            competencies=e.competencies or [],
            tags=e.tags or [],
            missing=missing_sections(e),
            target=self._target(e),
            revision=e.revision,
            archived=e.archived,
            practice_count=practice_count,
            preview=preview[:160],
            updated_at=e.updated_at,
        )

    def all(
        self, user: User, archived: bool = False, q: str = "", competency: str | None = None
    ) -> list[StorySummary]:
        rows = self.db.scalars(
            select(ExperienceEntry)
            .where(ExperienceEntry.user_id == user.id, ExperienceEntry.archived.is_(archived))
            .order_by(ExperienceEntry.updated_at.desc())
        ).all()
        words = q.lower().split()
        if competency:
            rows = [e for e in rows if competency in (e.competencies or [])]
        if words:
            # Your own stories only, so a simple search over everything you wrote is enough.
            def text(e: ExperienceEntry) -> str:
                return " ".join([*(getattr(e, f) or "" for f in TEXT_FIELDS), *(e.tags or [])]).lower()

            rows = [e for e in rows if all(w in text(e) for w in words)]
        counts = self._practice_counts(user)
        return [self._summary(e, counts.get(e.id, 0)) for e in rows]

    def get(self, user: User, story_id: str) -> StoryOut:
        e = self._get(user, story_id)
        answers = self.db.scalars(
            select(PracticeAnswer)
            .where(PracticeAnswer.user_id == user.id, PracticeAnswer.story_id == e.id)
            .order_by(PracticeAnswer.created_at.desc())
        ).all()
        practice = []
        for a in answers:
            q = get_question(a.track, a.question_id)
            practice.append(
                StoryPractice(
                    answer_id=a.id,
                    question_title=q.title if q else a.question_id,
                    href=f"/careers/{a.track}/questions/{a.question_id}?answer={a.id}",
                    score=a.score,
                    too_short=feedback_eligibility(a.feedback) == "too_short",
                    created_at=a.created_at,
                )
            )
        questions = []
        for ref in e.question_refs or []:
            track, _, qid = ref.partition("/")
            q = get_question(track, qid)
            questions.append(
                StoryQuestionLink(
                    ref=ref,
                    title=q.title if q else qid,
                    href=f"/careers/{track}/questions/{qid}",
                    available=q is not None and not is_retired(track, qid),
                )
            )
        summary = self._summary(e, len(answers))
        return StoryOut(
            **summary.model_dump(),
            situation=e.situation,
            task=e.task,
            action=e.action,
            result=e.result,
            reflection=e.reflection,
            notes=e.notes,
            evidence=e.evidence,
            short_version=e.short_version,
            long_version=e.long_version,
            questions=questions,
            practice=practice,
            privacy_hints=privacy_hints(e),
            created_at=e.created_at,
        )

    def revisions(self, user: User, story_id: str) -> list[StoryRevisionOut]:
        e = self._get(user, story_id)
        rows = self.db.scalars(
            select(StoryRevision)
            .where(StoryRevision.story_id == e.id)
            .order_by(StoryRevision.revision.desc())
        ).all()
        return [
            StoryRevisionOut(revision=r.revision, reason=r.reason, created_at=r.created_at, fields=r.fields)
            for r in rows
        ]

    # --- writes -------------------------------------------------------------------------------

    def _apply(self, user: User, e: ExperienceEntry, body: StoryFields, clear_target: bool = False) -> None:
        data = body.model_dump(exclude_unset=True)
        for f in TEXT_FIELDS:
            if f in data and data[f] is not None:
                setattr(e, f, clean(data[f]))
        if not e.title:
            raise AppError("Give the story a title.", code="title_required")
        if "track" in data:
            if data["track"] is not None and data["track"] not in CATALOG:
                raise AppError("Unknown career.", code="unknown_career")
            e.track = data["track"]
        if "context" in data:
            e.context = data["context"]
        if data.get("competencies") is not None:
            e.competencies = list(dict.fromkeys(data["competencies"]))
        if data.get("tags") is not None:
            tags = [clean(t)[:40] for t in data["tags"]]
            e.tags = list(dict.fromkeys(t for t in tags if t))
        if data.get("question_refs") is not None:
            refs = list(dict.fromkeys(data["question_refs"]))
            for ref in refs:
                track, _, qid = ref.partition("/")
                if not _REF.match(ref) or get_question(track, qid) is None:
                    raise AppError(f"Unknown question: {ref}", code="unknown_question")
            e.question_refs = refs
        if clear_target:
            e.target_id = None
            e.requirement_ids = []
        elif data.get("target_id"):
            t = self.db.get(RoleTarget, data["target_id"])
            if t is None or t.user_id != user.id:
                raise NotFoundError("Target not found")
            if e.target_id != t.id:
                e.target_id = t.id
                e.requirement_ids = []  # requirements belong to the target they came from

    def create(self, user: User, body: StoryCreate) -> StoryOut:
        n = (
            self.db.scalar(
                select(func.count()).select_from(ExperienceEntry).where(ExperienceEntry.user_id == user.id)
            )
            or 0
        )
        if n >= MAX_STORIES:
            raise AppError(
                f"Up to {MAX_STORIES} stories per account. Archive or delete some first.",
                code="too_many_stories",
            )
        e = ExperienceEntry(user_id=user.id, title="", track=user.career_track, revision=1)
        self._apply(user, e, body)
        self.db.add(e)
        self.db.flush()
        record_revision(self.db, e, "created", bump=False)
        self.db.commit()
        return self.get(user, e.id)

    def update(self, user: User, story_id: str, body: StoryUpdate) -> StoryOut:
        e = self._get(user, story_id)
        if body.expected_revision != e.revision:
            raise ConflictError(
                "This story changed since you opened it (maybe in another tab). Your edits weren't saved.",
                code="stale_revision",
                details={"current_revision": e.revision},
            )
        before = snapshot(e)
        self._apply(user, e, body, clear_target=body.clear_target)
        if snapshot(e) == before:
            return self.get(user, e.id)  # nothing changed: no new revision
        e.updated_at = datetime.now(UTC)
        record_revision(self.db, e, body.reason, bump=True)
        self.db.commit()
        return self.get(user, e.id)

    def set_archived(self, user: User, story_id: str, archived: bool) -> StoryOut:
        e = self._get(user, story_id)
        e.archived = archived
        e.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(user, e.id)

    def restore(self, user: User, story_id: str, revision: int, expected_revision: int) -> StoryOut:
        e = self._get(user, story_id)
        if expected_revision != e.revision:
            raise ConflictError(
                "This story changed since you opened it. Reload it, then restore.",
                code="stale_revision",
                details={"current_revision": e.revision},
            )
        old = self.db.scalar(
            select(StoryRevision).where(StoryRevision.story_id == e.id, StoryRevision.revision == revision)
        )
        if old is None:
            raise NotFoundError("Revision not found")
        fields = dict(old.fields)
        # A target that's gone since (or was never this learner's: the same check as an edit)
        # stays unlinked; everything written comes back.
        if fields.get("target_id"):
            t = self.db.get(RoleTarget, fields["target_id"])
            if t is None or t.user_id != user.id:
                fields["target_id"] = None
        if fields.get("target_id") != e.target_id:
            e.requirement_ids = []  # requirements belong to the target they came from
        for f in SNAPSHOT_FIELDS:
            if f in fields:
                setattr(e, f, fields[f])
        e.updated_at = datetime.now(UTC)
        record_revision(self.db, e, "restored", bump=True)
        self.db.commit()
        return self.get(user, e.id)

    def delete(self, user: User, story_id: str) -> None:
        e = self._get(user, story_id)
        self.db.delete(e)  # revisions go with it; answers that rehearsed it keep their text and score
        self.db.commit()

    def assist(self, user: User, story_id: str, body: StoryAssistIn) -> StoryAssistOut:
        e = self._get(user, story_id)
        given = {
            "situation": body.situation,
            "task": body.task,
            "action": body.action_text,
            "result": body.result,
            "reflection": body.reflection,
        }
        sections = {f: clean(v) if v is not None else getattr(e, f) for f, v in given.items()}
        if body.action == "check":
            return StoryAssistOut(
                action="check",
                method=story_assist.METHOD,
                proposals=[],
                questions=story_assist.check(sections),
            )
        if body.action == "shorten":
            proposals = story_assist.shorten(sections)
            questions = (
                [] if proposals else ["Nothing to trim: no filler words or repeated sentences were found."]
            )
            return StoryAssistOut(
                action="shorten", method=story_assist.METHOD, proposals=proposals, questions=questions
            )
        proposals, questions = story_assist.clarity(sections)
        if not proposals and not questions:
            questions = ["No hedges, very long sentences or vague phrases were found."]
        return StoryAssistOut(
            action="clarity", method=story_assist.METHOD, proposals=proposals, questions=questions
        )


def check_story_owner(db: Session, user: User, story_id: str | None) -> str | None:
    """For answers that rehearse a story: it must be the learner's own."""
    if story_id is None:
        return None
    e = db.get(ExperienceEntry, story_id)
    if e is None or e.user_id != user.id:
        raise NotFoundError("Story not found")
    return e.id
