"""Read-only checks over saved career answers: request keys, revision links, score eligibility.

    python -m app.cli check-answers [--limit-ids N]

Reports reason codes, counts and answer/account ids, never answer text, keys or fingerprints. It
never writes: on PostgreSQL the transaction is set read only, and it always rolls back. Rules:

- ``duplicate_key``: the same (account, key) saved twice (the unique constraint should prevent it).
  The same key string under two accounts is two different keys and is not reported.
- ``key_without_fingerprint`` / ``fingerprint_without_key``: half of a keyed save's identity.
- ``fingerprint_unknown_version``: a fingerprint this code doesn't compute; a resend gets 409
  ``idempotency_key_unverifiable``, never a guess. A notice, not a violation.
- ``parent_missing``, ``parent_self``, ``parent_other_owner``, ``parent_other_question``: a revision
  link that doesn't point at the same learner's earlier answer to the same question.
- ``parent_newer``: the linked answer was saved after its revision (a link is made only to an
  answer that already exists). No link is ever inferred from times; this only checks stored ones.
- ``eligibility_unknown``: answers stored without evidence level or word count. A notice: their
  score counts nowhere; nothing here turns them into zero or a score.
- ``eligibility_sql_mismatch``: the SQL rule (activity filters and counts) and the Python rule
  (summaries) disagree about an answer being too short.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import case, select, text
from sqlalchemy.orm import Session

from app.careers.answers import FINGERPRINT_VERSION
from app.careers.eligibility import feedback_eligibility, too_short_condition
from app.models import PracticeAnswer

VIOLATIONS = (
    "duplicate_key",
    "key_without_fingerprint",
    "fingerprint_without_key",
    "parent_missing",
    "parent_self",
    "parent_other_owner",
    "parent_other_question",
    "parent_newer",
    "eligibility_sql_mismatch",
)
NOTICES = ("fingerprint_unknown_version", "eligibility_unknown")


@dataclass(frozen=True)
class Row:
    id: str
    user_id: str
    track: str
    question_id: str
    created_at: datetime
    key: str | None
    fingerprint: str | None
    parent: str | None
    eligibility: str  # scored / too_short / unknown, from the stored feedback
    sql_too_short: bool  # the same question answered by the SQL rule


@dataclass
class Report:
    inspected: int = 0
    accounts: int = 0
    found: dict[str, list[tuple[str, str]]] = field(default_factory=lambda: defaultdict(list))

    @property
    def ok(self) -> bool:
        return not any(self.found.get(v) for v in VIOLATIONS)

    def summary(self, limit_ids: int = 20) -> dict:
        return {
            "scope": {"answers_inspected": self.inspected, "accounts": self.accounts},
            "violations": {
                v: {"count": len(self.found.get(v, [])), "ids": self.found.get(v, [])[:limit_ids]}
                for v in VIOLATIONS
            },
            "notices": {
                n: {"count": len(self.found.get(n, [])), "ids": self.found.get(n, [])[:limit_ids]}
                for n in NOTICES
            },
            "ok": self.ok,
        }


def check_rows(rows: list[Row]) -> Report:
    """The rules over rows already read; pure, so every rule can be tested on its own."""
    rep = Report(inspected=len(rows), accounts=len({r.user_id for r in rows}))
    by_id = {r.id: r for r in rows}
    keys = Counter((r.user_id, r.key) for r in rows if r.key)
    for r in rows:
        ref = (r.id, r.user_id)
        if r.key and keys[(r.user_id, r.key)] > 1:
            rep.found["duplicate_key"].append(ref)
        if r.key and not r.fingerprint:
            rep.found["key_without_fingerprint"].append(ref)
        if r.fingerprint and not r.key:
            rep.found["fingerprint_without_key"].append(ref)
        if r.fingerprint and r.fingerprint.split(":", 1)[0] != FINGERPRINT_VERSION:
            rep.found["fingerprint_unknown_version"].append(ref)
        if r.parent:
            p = by_id.get(r.parent)
            if r.parent == r.id:
                rep.found["parent_self"].append(ref)
            elif p is None:
                rep.found["parent_missing"].append(ref)
            elif p.user_id != r.user_id:
                rep.found["parent_other_owner"].append(ref)
            elif (p.track, p.question_id) != (r.track, r.question_id):
                rep.found["parent_other_question"].append(ref)
            elif p.created_at > r.created_at:
                rep.found["parent_newer"].append(ref)
        if r.eligibility == "unknown":
            rep.found["eligibility_unknown"].append(ref)
        if r.sql_too_short != (r.eligibility == "too_short"):
            rep.found["eligibility_sql_mismatch"].append(ref)
    return rep


def read_rows(db: Session) -> list[Row]:
    stmt = select(
        PracticeAnswer.id,
        PracticeAnswer.user_id,
        PracticeAnswer.track,
        PracticeAnswer.question_id,
        PracticeAnswer.created_at,
        PracticeAnswer.client_request_id,
        PracticeAnswer.request_fingerprint,
        PracticeAnswer.revises_answer_id,
        PracticeAnswer.feedback,
        case((too_short_condition(), True), else_=False),
    )
    return [
        Row(i, u, t, q, at, k, f, p, feedback_eligibility(fb), bool(short))
        for i, u, t, q, at, k, f, p, fb, short in db.execute(stmt)
    ]


def check(db: Session) -> Report:
    """Read, check and roll back: never a write, whatever the rules find."""
    try:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
        return check_rows(read_rows(db))
    finally:
        db.rollback()
