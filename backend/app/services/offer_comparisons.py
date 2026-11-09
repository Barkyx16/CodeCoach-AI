"""Private offer comparisons (docs/OFFER_COMPARISON.md).

Saved like the other long-form editors: against the revision the page started from (a newer one
is a conflict that returns the saved version, so nothing is overwritten), with update receipts so a
save whose reply was lost isn't mistaken for someone else's. Every text is plain text with control
characters removed. A linked application must be the learner's own and is only read for its name:
nothing here changes its stage or history. Figures come from app/offercompare/calc.py on every read.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.locking import lock_for_update
from app.errors import AppError, ConflictError, NotFoundError
from app.models import Application, OfferComparison, User
from app.offercompare import example
from app.offercompare.calc import derive
from app.schemas.common import SaveReplay
from app.schemas.offer_comparisons import (
    ComparisonDoc,
    DerivedOut,
    OfferComparisonCreate,
    OfferComparisonOut,
    OfferComparisonSave,
    OfferComparisonSummary,
)
from app.services import update_receipts

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TEXT_FIELDS = ("label", "source_note", "guaranteed_note", "bonus_note", "equity_note", "benefits_note")


def _clean(text: str) -> str:
    return _CONTROL.sub("", text).strip()


def checked(doc: ComparisonDoc) -> dict[str, Any]:
    """The document as stored: unique ids, ratings only for offers in it, a rating's value only when
    rated, distinct currencies in a rate, and every text plain."""
    data = doc.model_dump(mode="json")
    data["title"] = _clean(data["title"]) or "My offers"
    offer_ids = [o["id"] for o in data["offers"]]
    if len(set(offer_ids)) != len(offer_ids):
        raise AppError("Two offers have the same id.", code="duplicate_offer")
    factor_ids = [f["id"] for f in data["factors"]]
    if len(set(factor_ids)) != len(factor_ids):
        raise AppError("Two factors have the same id.", code="duplicate_factor")
    for o in data["offers"]:
        for name in _TEXT_FIELDS:
            o[name] = _clean(o[name])
        if not o["label"]:
            raise AppError("Every offer needs a name.", code="offer_label_required")
    for f in data["factors"]:
        f["label"] = _clean(f["label"])
        if not f["label"]:
            raise AppError("Every factor needs a name.", code="factor_label_required")
        stray = sorted(set(f["ratings"]) - set(offer_ids))
        if stray:
            raise AppError(
                f"“{f['label']}” rates an offer that isn't in this comparison.", code="unknown_offer"
            )
        for r in f["ratings"].values():
            r["note"] = _clean(r["note"])
            if r["state"] == "rated" and r["value"] is None:
                raise AppError(
                    f"“{f['label']}”: a rating needs a value from 1 to 5, or choose unknown.",
                    code="rating_value_required",
                )
            if r["state"] != "rated":
                r["value"] = None  # unknown and not comparable carry no number
    for c in data["conversions"]:
        c["note"] = _clean(c["note"])
        if c["from_currency"] == c["to_currency"]:
            raise AppError("A rate converts between two different currencies.", code="same_currency")
    return data


class OfferComparisons:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _find(self, comparison_id: str, *, lock: bool = False) -> OfferComparison:
        row = self.db.get(OfferComparison, comparison_id)
        if row is None or row.user_id != self.user.id:
            raise NotFoundError("Comparison not found")
        return lock_for_update(self.db, row) if lock else row

    def _applications(self, data: dict[str, Any]) -> dict[str, str]:
        ids = {o["application_id"] for o in data["offers"] if o.get("application_id")}
        if not ids:
            return {}
        rows = self.db.scalars(
            select(Application).where(Application.id.in_(ids), Application.user_id == self.user.id)
        ).all()
        found = {a.id: f"{a.role_title} at {a.employer}" for a in rows}
        if set(found) != ids:
            raise NotFoundError("Application not found")  # never someone else's, never a guess
        return found

    def _out(self, row: OfferComparison, replay: SaveReplay | None = None) -> OfferComparisonOut:
        return OfferComparisonOut(
            save_replay=replay,
            id=row.id,
            revision=row.revision,
            doc=ComparisonDoc.model_validate(row.doc),
            derived=derive(row.doc),
            applications=self._applications(row.doc),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def create(self, body: OfferComparisonCreate) -> OfferComparisonOut:
        raw = (
            example()
            if body.example
            else {"title": body.title, "offers": [], "factors": [], "conversions": []}
        )
        data = checked(ComparisonDoc.model_validate(raw))
        now = datetime.now(UTC)
        row = OfferComparison(
            user_id=self.user.id, title=data["title"], doc=data, revision=1, created_at=now, updated_at=now
        )
        self.db.add(row)
        self.db.commit()
        return self._out(row)

    def get(self, comparison_id: str) -> OfferComparisonOut:
        return self._out(self._find(comparison_id))

    def save(self, comparison_id: str, body: OfferComparisonSave) -> OfferComparisonOut:
        row = self._find(comparison_id, lock=True)
        data = checked(body.doc)
        self._applications(data)
        key = body.client_request_id
        print_ = update_receipts.fingerprint("offer_comparison", comparison_id, body.expected_revision, data)
        done = update_receipts.find(
            self.db, self.user, key, "offer_comparison", comparison_id, body.expected_revision, print_
        )
        if done is not None:
            return self._out(
                row, SaveReplay(accepted_revision=done.accepted_revision, current_revision=row.revision)
            )
        if body.expected_revision != row.revision:
            raise ConflictError(
                "This comparison was saved somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                details={"current_revision": row.revision, "current": self._out(row).model_dump(mode="json")},
            )
        row.doc = data
        row.title = data["title"]
        row.revision += 1
        row.updated_at = datetime.now(UTC)
        update_receipts.record(
            self.db,
            self.user,
            key,
            "offer_comparison",
            comparison_id,
            body.expected_revision,
            row.revision,
            print_,
        )
        self.db.commit()
        return self._out(row)

    def delete(self, comparison_id: str) -> None:
        self.db.delete(self._find(comparison_id))
        self.db.commit()

    def preview(self, doc: ComparisonDoc) -> DerivedOut:
        """The figures for an unsaved draft, so the page can show formulas as you type. Nothing is stored."""
        return DerivedOut(derived=derive(checked(doc)))

    def mine(self) -> list[OfferComparisonSummary]:
        rows = self.db.scalars(
            select(OfferComparison)
            .where(OfferComparison.user_id == self.user.id)
            .order_by(OfferComparison.updated_at.desc())
        ).all()
        return [
            OfferComparisonSummary(
                id=r.id, title=r.title, offers=len(r.doc.get("offers", [])), updated_at=r.updated_at
            )
            for r in rows
        ]

    def export(self) -> list[dict[str, Any]]:
        return [
            {
                "title": r.title,
                "revision": r.revision,
                "doc": r.doc,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in self.db.scalars(select(OfferComparison).where(OfferComparison.user_id == self.user.id))
        ]
