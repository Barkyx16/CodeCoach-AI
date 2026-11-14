"""Work-sample practice (docs/WORK_SAMPLES.md): drafts saved against a revision, artifacts sent for
feedback frozen with the brief they were written against. A revision is a new attempt; the
original stays as it was. Text is plain text: control characters are removed, nothing is
interpreted. Nothing is sent anywhere: no email, no publishing, no sharing.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.locking import lock_for_update
from app.errors import AppError, ConflictError, NotFoundError
from app.models import User, WorkSampleAttempt, WorkSampleDraft
from app.schemas.common import SaveReplay
from app.schemas.work_samples import (
    MAX_SECTION,
    WorkSampleAttemptIn,
    WorkSampleAttemptOut,
    WorkSampleAttemptSummary,
    WorkSampleBrief,
    WorkSampleDraftIn,
    WorkSampleDraftOut,
    WorkSampleSectionOut,
    WorkSampleSummary,
)
from app.services import update_receipts
from app.worksamples import BRIEFS, BY_ID, Brief
from app.worksamples.feedback import evaluate, words

MAX_ATTEMPTS_PER_BRIEF = 50
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _brief(brief_id: str) -> Brief:
    b = BY_ID.get(brief_id)
    if b is None:
        raise NotFoundError("Work sample not found")
    return b


def _clean_sections(b: Brief, sections: dict[str, str]) -> dict[str, str]:
    unknown = sorted(set(sections) - set(b.section_ids))
    if unknown:
        raise AppError(f"This brief has no section {unknown[0]!r}.", code="unknown_section")
    out = {}
    for sid in b.section_ids:
        text = _CONTROL.sub("", sections.get(sid, "")).strip()
        if len(text) > MAX_SECTION:
            raise AppError(f"Each section can be up to {MAX_SECTION} characters.", code="section_too_long")
        out[sid] = text
    return out


class WorkSamples:
    def __init__(self, db: Session, user: User | None = None):
        self.db = db
        self.user = user

    @staticmethod
    def briefs() -> list[WorkSampleSummary]:
        return [
            WorkSampleSummary(id=b.id, title=b.title, format_label=b.format_label, careers=list(b.careers))
            for b in BRIEFS
        ]

    @staticmethod
    def brief(brief_id: str) -> WorkSampleBrief:
        b = _brief(brief_id)
        return WorkSampleBrief(
            id=b.id,
            version=b.version,
            title=b.title,
            format=b.format,
            format_label=b.format_label,
            careers=list(b.careers),
            scenario=b.scenario,
            audience=b.audience,
            purpose=b.purpose,
            facts=[f["text"] for f in b.facts],
            required=[r["label"] for r in b.required],
            sections=[WorkSampleSectionOut(id=s.id, label=s.label, hint=s.hint) for s in b.sections],
            min_words=b.min_words,
            max_words=b.max_words,
            review_status=b.review_status,
            scope_note=b.scope_note,
        )

    @property
    def _me(self) -> User:
        assert self.user is not None
        return self.user

    def draft(self, brief_id: str) -> WorkSampleDraftOut:
        b = _brief(brief_id)
        row = self.db.get(WorkSampleDraft, (self._me.id, brief_id))
        return WorkSampleDraftOut(
            brief_id=b.id,
            sections=row.sections if row else dict.fromkeys(b.section_ids, ""),
            revision=row.revision if row else 0,
            updated_at=row.updated_at if row else None,
        )

    def save_draft(self, brief_id: str, body: WorkSampleDraftIn) -> WorkSampleDraftOut:
        b = _brief(brief_id)
        sections = _clean_sections(b, body.sections)
        row = lock_for_update(self.db, self.db.get(WorkSampleDraft, (self._me.id, brief_id)))
        current = row.revision if row else 0
        key = body.client_request_id
        print_ = update_receipts.fingerprint(
            "work_sample", brief_id, body.expected_revision, {"sections": sections}
        )
        if (
            replayed := self._replayed(brief_id, key, body.expected_revision, print_, row is not None)
        ) is not None:
            return replayed
        if body.expected_revision != current:
            raise ConflictError(
                "This work sample was saved somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                details={
                    "current_revision": current,
                    "current": self.draft(brief_id).model_dump(mode="json"),
                },
            )
        if row is None:
            row = WorkSampleDraft(user_id=self._me.id, brief_id=brief_id, sections={}, revision=0)
            self.db.add(row)
        row.sections = sections
        row.revision = current + 1
        row.updated_at = datetime.now(UTC)
        update_receipts.record(
            self.db, self._me, key, "work_sample", brief_id, body.expected_revision, row.revision, print_
        )
        try:
            self.db.commit()
        except IntegrityError:  # two first saves at once
            self.db.rollback()
            exists = self.db.get(WorkSampleDraft, (self._me.id, brief_id)) is not None
            if (
                replayed := self._replayed(brief_id, key, body.expected_revision, print_, exists)
            ) is not None:
                return replayed
            saved = self.draft(brief_id)
            raise ConflictError(
                "This work sample was saved somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                details={"current_revision": saved.revision, "current": saved.model_dump(mode="json")},
            ) from None
        return self.draft(brief_id)

    def _replayed(
        self, brief_id: str, key: str | None, base: int, print_: str, exists: bool
    ) -> WorkSampleDraftOut | None:
        done = update_receipts.find(self.db, self._me, key, "work_sample", brief_id, base, print_)
        if done is None:
            return None
        if not exists:
            raise NotFoundError("That work sample was saved, then removed. Nothing was saved again.")
        out = self.draft(brief_id)
        out.save_replay = SaveReplay(accepted_revision=done.accepted_revision, current_revision=out.revision)
        return out

    def attempt(self, brief_id: str, body: WorkSampleAttemptIn) -> WorkSampleAttemptOut:
        b = _brief(brief_id)
        sections = _clean_sections(b, body.sections)
        if words(" ".join(sections.values())) < 10:
            raise AppError(
                "Write the work sample first (a few sentences at least), then ask for feedback.",
                code="too_short",
            )
        if body.revision_of is not None:
            earlier = self.db.get(WorkSampleAttempt, body.revision_of)
            if earlier is None or earlier.user_id != self._me.id or earlier.brief_id != brief_id:
                raise NotFoundError("The attempt this revises wasn't found")
        n = (
            self.db.scalar(
                select(func.count())
                .select_from(WorkSampleAttempt)
                .where(WorkSampleAttempt.user_id == self._me.id, WorkSampleAttempt.brief_id == brief_id)
            )
            or 0
        )
        if n >= MAX_ATTEMPTS_PER_BRIEF:
            raise AppError(
                "You've reached the limit of saved attempts for this brief.", code="too_many_attempts"
            )
        a = WorkSampleAttempt(
            user_id=self._me.id,
            brief_id=b.id,
            brief_version=b.version,
            snapshot=b.snapshot(),
            sections=sections,
            feedback=evaluate(b, sections),
            revision_of=body.revision_of,
        )
        self.db.add(a)
        self.db.commit()
        return self._out(a)

    def _out(self, a: WorkSampleAttempt) -> WorkSampleAttemptOut:
        current = BY_ID.get(a.brief_id)
        snap: dict[str, Any] = a.snapshot
        labels = {s["id"]: s["label"] for s in snap.get("sections", [])} or {"message": "Message"}
        return WorkSampleAttemptOut(
            id=a.id,
            brief_id=a.brief_id,
            brief_version=a.brief_version,
            current_version=current.version if current else None,
            title=snap["title"],
            format_label=snap["format_label"],
            sections=a.sections,
            section_labels=labels,
            feedback=a.feedback,
            reference=snap["reference"],
            revision_of=a.revision_of,
            created_at=a.created_at,
        )

    def attempts(self, brief_id: str) -> list[WorkSampleAttemptSummary]:
        _brief(brief_id)
        rows = self.db.scalars(
            select(WorkSampleAttempt)
            .where(WorkSampleAttempt.user_id == self._me.id, WorkSampleAttempt.brief_id == brief_id)
            .order_by(WorkSampleAttempt.created_at.desc())
        ).all()
        return [
            WorkSampleAttemptSummary(
                id=a.id,
                brief_version=a.brief_version,
                covered=a.feedback.get("covered", 0),
                total=a.feedback.get("total", 0),
                revision_of=a.revision_of,
                created_at=a.created_at,
            )
            for a in rows
        ]

    def get_attempt(self, attempt_id: str) -> WorkSampleAttemptOut:
        a = self.db.get(WorkSampleAttempt, attempt_id)
        if a is None or a.user_id != self._me.id:
            raise NotFoundError("Attempt not found")
        return self._out(a)

    def export(self) -> dict[str, Any]:
        me = self._me.id
        return {
            "drafts": [
                {"brief": d.brief_id, "sections": d.sections, "revision": d.revision}
                for d in self.db.scalars(select(WorkSampleDraft).where(WorkSampleDraft.user_id == me))
            ],
            "attempts": [
                {
                    "brief": a.brief_id,
                    "brief_version": a.brief_version,
                    "sections": a.sections,
                    "feedback": a.feedback,
                    "revision_of": a.revision_of,
                    "created_at": a.created_at.isoformat(),
                }
                for a in self.db.scalars(select(WorkSampleAttempt).where(WorkSampleAttempt.user_id == me))
            ],
        }
