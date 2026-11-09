"""Recovering a revision-checked save whose reply was lost (Volume 8, prompt 3; docs/RECOVERY.md).

Stories, notes, kits, whiteboard drafts and reflections are saved against the revision the page
started from, and a newer revision is a conflict. A save whose reply was lost, sent again, used
to meet its own new revision and read as "changed elsewhere". Now a keyed save records a receipt
in the same transaction as the update: the entity, the revision it started from, the revision it
produced, and a digest of the update. A retry with that key, the same entity, the same base and
the same content finds the receipt and is answered "your save went through as revision N", with
the entity as it is now. If the entity has changed since, that's said separately (`current_revision`
after `accepted_revision`), and the page compares; it never replays an old snapshot as the latest.

Proof is the receipt, never a resemblance: an entity that happens to equal what was sent isn't
evidence that this request saved it. Without a receipt (no key, or it expired), a stale save is
a conflict, as before. A key reused for another entity, base or content is refused (409
`idempotency_key_reused`). A deleted entity is never recreated by a retry: the owner-scoped
lookup the route already does comes first and says 404.

Order inside an update: lock the entity row, look for the receipt (so the second of two copies
waits for the first, then finds its receipt), check the revision, apply, record the receipt,
commit. Receipts are kept UPDATE_RECEIPT_DAYS, then purged by housekeeping.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import UpdateReceipt, User
from app.services import request_keys

UPDATE_RECEIPT_DAYS = 7  # the browser keeps an unconfirmed save for at most a day
Entity = Literal["story", "note", "kit", "whiteboard", "reflection", "note_copy", "app_notes", "code_review"]


@dataclass(frozen=True)
class Replay:
    accepted_revision: int


def fingerprint(entity: Entity, entity_id: str, base_revision: int, update: Any) -> str:
    return request_keys.fingerprint(
        f"{entity}.update", {"id": entity_id, "base": base_revision, "update": update}
    )


def find(
    db: Session,
    user: User,
    key: str | None,
    entity: Entity,
    entity_id: str,
    base_revision: int,
    print_: str,
) -> Replay | None:
    """The accepted save this key made, if any (call after locking the entity). The same key for
    another entity, base or content is refused, without saying what it made."""
    if not key:
        return None
    since = datetime.now(UTC) - timedelta(days=UPDATE_RECEIPT_DAYS)
    r = db.scalar(
        select(UpdateReceipt).where(UpdateReceipt.user_id == user.id, UpdateReceipt.client_request_id == key)
    )
    if r is None or _aware(r.created_at) < since:
        return None  # never saved with this key, or the evidence has expired: a save like any other
    if (r.entity, r.entity_id, r.base_revision) != (
        entity,
        entity_id,
        base_revision,
    ) or not request_keys.same(r.request_fingerprint, print_):
        raise request_keys.reused("save")
    return Replay(accepted_revision=r.accepted_revision)


def by_key(db: Session, user: User, key: str) -> UpdateReceipt | None:
    """This account's unexpired receipt for a key, whatever it was for (the caller checks)."""
    since = datetime.now(UTC) - timedelta(days=UPDATE_RECEIPT_DAYS)
    r = db.scalar(
        select(UpdateReceipt).where(UpdateReceipt.user_id == user.id, UpdateReceipt.client_request_id == key)
    )
    return r if r is not None and _aware(r.created_at) >= since else None


def record(
    db: Session,
    user: User,
    key: str | None,
    entity: Entity,
    entity_id: str,
    base_revision: int,
    accepted_revision: int,
    print_: str,
) -> None:
    """Add the receipt to the update's own transaction (the caller commits both together). An
    expired receipt under the same key is replaced."""
    if not key:
        return
    db.execute(
        delete(UpdateReceipt).where(UpdateReceipt.user_id == user.id, UpdateReceipt.client_request_id == key)
    )
    db.add(
        UpdateReceipt(
            user_id=user.id,
            entity=entity,
            entity_id=entity_id,
            client_request_id=key,
            base_revision=base_revision,
            accepted_revision=accepted_revision,
            request_fingerprint=print_,
        )
    )


def purge(db: Session, now: datetime | None = None) -> int:
    """Housekeeping: receipts older than UPDATE_RECEIPT_DAYS. Returns how many went."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=UPDATE_RECEIPT_DAYS)
    result = db.execute(delete(UpdateReceipt).where(UpdateReceipt.created_at < cutoff))
    return int(getattr(result, "rowcount", 0) or 0)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
