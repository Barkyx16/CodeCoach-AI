"""Personal kit templates (Volume 11, prompt 7; docs/TEMPLATES.md).

A template is a snapshot of checklist items and questions to ask that a learner chose from one of
their interview kits, to start another interview's kit from. It keeps only that text (and a
question's group): never whether an item was done, the meeting link, location, interviewers, notes,
chosen examples or the outcome, and nothing that says which interview it came from. It isn't a live
alias: changing or deleting the kit it came from changes nothing here, and changing or deleting a
template changes no kit already made from it (applying copies its items into the kit's form, where
they're the kit's own).

Text is plain text, stored as written (control characters removed). There is no placeholder
syntax: "{{employer}}" is kept and shown as those characters, and nothing in a template is ever
evaluated, fetched or filled in. Private to the owner (every query is by owner); under row-level
security on PostgreSQL.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.locking import lock_for_update
from app.errors import AppError, ConflictError, NotFoundError
from app.models import KitTemplate, User
from app.schemas.common import SaveReplay
from app.schemas.kit_templates import (
    KitTemplateCreate,
    KitTemplateOut,
    KitTemplateSummary,
    KitTemplateUpdate,
    TemplateChecklistItem,
    TemplateQuestion,
)
from app.services import request_keys, update_receipts

MAX_TEMPLATES = 30
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(text: str) -> str:
    return _CONTROL.sub("", text).strip()


def _items(checklist: list[TemplateChecklistItem], questions: list[TemplateQuestion]) -> tuple[list, list]:
    """Cleaned, with blank and repeated entries dropped (the same words twice is one item)."""
    seen: set[str] = set()
    ticks = []
    for c in checklist:
        text = clean(c.text)
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            ticks.append({"text": text})
    seen = set()
    asks = []
    for q in questions:
        text = clean(q.text)
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            asks.append({"text": text, "group": q.group})
    return ticks, asks


class KitTemplates:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _find(self, template_id: str, *, lock: bool = False) -> KitTemplate:
        row = self.db.scalar(
            select(KitTemplate).where(KitTemplate.id == template_id, KitTemplate.user_id == self.user.id)
        )
        if row is None:
            raise NotFoundError("Template not found")
        return lock_for_update(self.db, row) if lock else row

    def _out(self, row: KitTemplate, replay: SaveReplay | None = None) -> KitTemplateOut:
        return KitTemplateOut(
            id=row.id,
            name=row.name,
            checklist=[TemplateChecklistItem(**c) for c in row.checklist or []],
            questions=[TemplateQuestion(**q) for q in row.questions or []],
            revision=row.revision,
            save_replay=replay,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def mine(self) -> list[KitTemplateSummary]:
        rows = self.db.scalars(
            select(KitTemplate)
            .where(KitTemplate.user_id == self.user.id)
            .order_by(KitTemplate.updated_at.desc(), KitTemplate.id)
        ).all()
        return [
            KitTemplateSummary(
                id=r.id,
                name=r.name,
                checklist_count=len(r.checklist or []),
                questions_count=len(r.questions or []),
                revision=r.revision,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def get(self, template_id: str) -> KitTemplateOut:
        return self._out(self._find(template_id))

    def _by_request(self, key: str) -> KitTemplate | None:
        return self.db.scalar(
            select(KitTemplate).where(
                KitTemplate.user_id == self.user.id, KitTemplate.client_request_id == key
            )
        )

    def create(self, body: KitTemplateCreate) -> KitTemplateOut:
        """A create sent again with the same `client_request_id` (its reply was lost) returns the
        template the first made; the same key with other content is refused (409
        `idempotency_key_reused`)."""
        print_ = request_keys.fingerprint(
            "kit_template.create", body.model_dump(mode="json", exclude={"client_request_id"})
        )
        key = body.client_request_id
        if key and (made := self._by_request(key)):
            request_keys.check(made.request_fingerprint, print_, "template")
            return self._out(made)
        name = clean(body.name)
        checklist, questions = _items(body.checklist, body.questions)
        if not name:
            raise AppError("Give the template a name.", code="missing_name")
        if not checklist and not questions:
            raise AppError("A template needs at least one checklist item or question.", code="empty_template")
        n = (
            self.db.scalar(
                select(func.count()).select_from(KitTemplate).where(KitTemplate.user_id == self.user.id)
            )
            or 0
        )
        if n >= MAX_TEMPLATES:
            raise AppError(
                f"Up to {MAX_TEMPLATES} kit templates. Delete one you don't use first.",
                code="too_many_templates",
            )
        now = datetime.now(UTC)
        row = KitTemplate(
            user_id=self.user.id,
            name=name,
            checklist=checklist,
            questions=questions,
            revision=1,
            client_request_id=key,
            request_fingerprint=print_ if key else None,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        try:
            self.db.flush()
        except IntegrityError:
            # The same create, sent twice at the same moment: the other copy made the template.
            self.db.rollback()
            made = self._by_request(key) if key else None
            if made is None:
                raise
            request_keys.check(made.request_fingerprint, print_, "template")
            return self._out(made)
        self.db.commit()
        return self._out(row)

    def update(self, template_id: str, body: KitTemplateUpdate) -> KitTemplateOut:
        """Rename, or replace the items, against the revision the page loaded. A save whose reply
        was lost, sent again with its key, is answered as having gone through (docs/RECOVERY.md);
        a stale one is 409 `stale_revision` with the saved template, so both can be compared."""
        row = self._find(template_id, lock=True)
        data = body.model_dump(
            mode="json", exclude={"client_request_id", "expected_revision"}, exclude_none=True
        )
        key = body.client_request_id
        print_ = update_receipts.fingerprint("kit_template", template_id, body.expected_revision, data)
        done = update_receipts.find(
            self.db, self.user, key, "kit_template", template_id, body.expected_revision, print_
        )
        if done is not None:
            return self._out(
                row, SaveReplay(accepted_revision=done.accepted_revision, current_revision=row.revision)
            )
        if body.expected_revision != row.revision:
            raise ConflictError(
                "This template was changed somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                details={"current_revision": row.revision, "current": self._out(row).model_dump(mode="json")},
            )
        if body.name is not None:
            name = clean(body.name)
            if not name:
                raise AppError("Give the template a name.", code="missing_name")
            row.name = name
        if body.checklist is not None or body.questions is not None:
            checklist, questions = _items(
                body.checklist
                if body.checklist is not None
                else [TemplateChecklistItem(**c) for c in row.checklist],
                body.questions
                if body.questions is not None
                else [TemplateQuestion(**q) for q in row.questions],
            )
            if not checklist and not questions:
                raise AppError(
                    "A template needs at least one checklist item or question.", code="empty_template"
                )
            row.checklist, row.questions = checklist, questions
        row.revision += 1
        row.updated_at = datetime.now(UTC)
        update_receipts.record(
            self.db, self.user, key, "kit_template", template_id, body.expected_revision, row.revision, print_
        )
        self.db.commit()
        return self._out(row)

    def delete(self, template_id: str) -> None:
        """Gone for good. Kits made from it keep their items: they were copied, not linked."""
        self.db.delete(self._find(template_id))
        self.db.commit()

    def export(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "checklist": t.checklist,
                "questions": t.questions,
                "revision": t.revision,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in self.db.scalars(
                select(KitTemplate)
                .where(KitTemplate.user_id == self.user.id)
                .order_by(KitTemplate.created_at)
            )
        ]
