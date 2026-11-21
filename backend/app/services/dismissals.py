"""Suggestions the learner said "not now" to, kept with the account (Volume 15, prompt 2;
docs/FOLLOW_UPS.md, "Not now").

One record per account and suggestion, so a dismissal made on one device holds on every other,
and Settings can list what was dismissed and offer any of it again. A key names the suggestion,
not the item it was offered on:

- "question-follow-up:<track>/<from>><to>": a reviewed follow-up question;
- "problem-follow-up:<from>><to>": a reviewed follow-up coding problem;
- "plan-change:<track>@<version>": "Your plan changed" for that version of the plan.

Offered again, a suggestion follows its own rules: a follow-up problem tried since still isn't
offered, and the list says so. Only this account's records are ever read or changed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.followups import follow_ups_from
from app.careers.questions import get_question
from app.content.problem_followups import follow_up_between
from app.errors import AppError, NotFoundError
from app.models import DismissedSuggestion, Problem, Submission, User

QUESTION, PROBLEM, PLAN = "question_follow_up", "problem_follow_up", "plan_change"
_PATTERNS = {
    QUESTION: re.compile(
        r"^question-follow-up:(?P<track>[a-z0-9-]{1,64})/(?P<src>[A-Za-z0-9_.-]{1,64})>(?P<to>[A-Za-z0-9_.-]{1,64})$"
    ),
    PROBLEM: re.compile(r"^problem-follow-up:(?P<src>[a-z0-9-]{1,80})>(?P<to>[a-z0-9-]{1,80})$"),
    PLAN: re.compile(r"^plan-change:(?P<track>[a-z0-9-]{1,64})@(?P<version>[1-9][0-9]{0,5})$"),
}
INVALID = "invalid_dismissal"


def question_key(track: str, from_id: str, to_id: str) -> str:
    return f"question-follow-up:{track}/{from_id}>{to_id}"


def problem_key(from_slug: str, to_slug: str) -> str:
    return f"problem-follow-up:{from_slug}>{to_slug}"


def plan_key(track: str, version: int) -> str:
    return f"plan-change:{track}@{version}"


@dataclass(frozen=True)
class Parsed:
    kind: str
    parts: dict[str, str]


def parse(key: str) -> Parsed:
    """What a key names, checked against the suggestions that exist; anything else is refused."""
    for kind, pattern in _PATTERNS.items():
        m = pattern.match(key)
        if not m:
            continue
        parts = m.groupdict()
        if kind == QUESTION and not any(
            f.to_id == parts["to"] for f in follow_ups_from(parts["track"], parts["src"])
        ):
            break
        if kind == PROBLEM and follow_up_between(parts["src"], parts["to"]) is None:
            break
        if kind == PLAN and parts["track"] not in CATALOG:
            break
        return Parsed(kind, parts)
    raise AppError("That isn't a suggestion this app offers.", code=INVALID)


class Dismissals:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _rows(self) -> list[DismissedSuggestion]:
        return list(
            self.db.scalars(
                select(DismissedSuggestion)
                .where(DismissedSuggestion.user_id == self.user.id)
                .order_by(DismissedSuggestion.dismissed_at.desc(), DismissedSuggestion.key)
            )
        )

    def keys(self) -> set[str]:
        return set(
            self.db.scalars(
                select(DismissedSuggestion.key).where(DismissedSuggestion.user_id == self.user.id)
            )
        )

    def add(self, key: str, offered_on: str | None = None, *, commit: bool = True) -> DismissedSuggestion:
        """Idempotent: the same key twice is one record (its first time is kept)."""
        parsed = parse(key)
        existing = self.db.scalar(
            select(DismissedSuggestion).where(
                DismissedSuggestion.user_id == self.user.id, DismissedSuggestion.key == key
            )
        )
        if existing is not None:
            return existing
        row = DismissedSuggestion(
            user_id=self.user.id,
            key=key,
            kind=parsed.kind,
            offered_on=(offered_on or "")[:200] or None,
            dismissed_at=datetime.now(UTC),
        )
        self.db.add(row)
        if commit:
            try:
                self.db.commit()
            except IntegrityError:  # the same key from two devices at once: one record
                self.db.rollback()
                found = self.db.scalar(
                    select(DismissedSuggestion).where(
                        DismissedSuggestion.user_id == self.user.id, DismissedSuggestion.key == key
                    )
                )
                assert found is not None
                return found
        return row

    def remove(self, key: str) -> None:
        row = self.db.scalar(
            select(DismissedSuggestion).where(
                DismissedSuggestion.user_id == self.user.id, DismissedSuggestion.key == key
            )
        )
        if row is None:
            raise NotFoundError("That suggestion isn't dismissed.")
        self.db.delete(row)
        self.db.commit()

    # --- how the list describes each ------------------------------------------------------------------

    def describe(self, row: DismissedSuggestion) -> tuple[str, str | None]:
        """Its label in plain words, and what offering it again will do when that isn't simply "offered"."""
        try:
            parsed = parse(row.key)
        except AppError:
            return (
                "A suggestion that's no longer offered",
                "It isn't offered any more, so it won't come back.",
            )
        p = parsed.parts
        if parsed.kind == QUESTION:
            to = get_question(p["track"], p["to"])
            src = get_question(p["track"], p["src"])
            label = f"A related question: {to.title if to else p['to']}"
            if src:
                label += f" (after “{src.title}”)"
            return label, None
        if parsed.kind == PROBLEM:
            to_problem = self.db.scalar(select(Problem).where(Problem.slug == p["to"]))
            src_problem = self.db.scalar(select(Problem).where(Problem.slug == p["src"]))
            label = f"A related problem: {to_problem.title if to_problem else p['to']}"
            if src_problem:
                label += f" (after {src_problem.title})"
            tried = (
                to_problem is not None
                and self.db.scalar(
                    select(Submission.id)
                    .where(Submission.user_id == self.user.id, Submission.problem_id == to_problem.id)
                    .limit(1)
                )
                is not None
            )
            note = "You've tried this problem since, so it won't be offered again." if tried else None
            return label, note
        career = CATALOG[p["track"]].title
        return (
            f"“Your plan changed” for {career} (plan version {p['version']})",
            "It shows again while that version of the plan is the current one.",
        )

    def listed(self) -> list[dict]:
        out = []
        for row in self._rows():
            label, note = self.describe(row)
            out.append(
                {
                    "key": row.key,
                    "kind": row.kind,
                    "label": label,
                    "note": note,
                    "offered_on": row.offered_on,
                    "dismissed_at": row.dismissed_at,
                }
            )
        return out

    def export(self) -> list[dict]:
        return [
            {
                "key": r.key,
                "kind": r.kind,
                "offered_on": r.offered_on,
                "dismissed_at": r.dismissed_at.isoformat(),
            }
            for r in self._rows()
        ]
