"""Names a learner listed, kept out of everything that leaves the app (Volume 15, prompt 7;
docs/PRIVACY.md, "Names you listed").

One function, ``replace_names``, replaces each listed name with ``[name]`` and counts them: whole
words only (a name inside a longer word stays, a hyphenated one included), any letter case, a possessive kept readable
("Priya's" becomes "[name]'s"), and spaces inside a name matched however they're typed. The practice
packet, a shared answer and every coach-context preview call it on what they send, never on what's
stored: the learner's own copy doesn't change. It finds only the names listed; it can't tell any
other word is a name, and it never claims to.

Names are private to the account: read only for the signed-in learner, in the export, deleted with
the account, and never written to a log or a trace (a canary test checks).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, ConflictError, NotFoundError
from app.models import ListedName, User

PLACEHOLDER = "[name]"
MAX_NAMES = 100
MAX_LENGTH = 80
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def fold(name: str) -> str:
    return " ".join(name.split()).casefold()


def clean(name: str) -> str:
    """A name as it's kept: spaces collapsed, control characters removed. Refused if it has no letter
    or digit (a name made only of punctuation would match nothing sensible)."""
    text = " ".join(_CONTROL.sub(" ", name).split())
    if not text or not any(ch.isalnum() for ch in text):
        raise AppError("Type a name: at least one letter.", code="invalid_name")
    if len(text) > MAX_LENGTH:
        raise AppError(f"A name can be up to {MAX_LENGTH} characters.", code="invalid_name")
    return text


@lru_cache(maxsize=256)
def _pattern(names: tuple[str, ...]) -> re.Pattern[str] | None:
    parts = [r"\s+".join(re.escape(w) for w in n.split()) for n in names if n.strip()]
    if not parts:
        return None
    # The longest first, so "Ann Lee" is one replacement, not "Ann" and then "Lee".
    parts.sort(key=len, reverse=True)
    # A hyphen joins a longer name ("Ann-Marie" isn't "Ann"), as a letter or digit does.
    return re.compile(r"(?<![\w-])(?:" + "|".join(parts) + r")(?P<s>['’]s)?(?![\w-])", re.IGNORECASE)


def replace_names(text: str, names: Sequence[str]) -> tuple[str, int]:
    """The text with every listed name replaced by "[name]", and how many were. An empty list, or
    text with none of them, comes back unchanged."""
    if not text or not names:
        return text, 0
    pattern = _pattern(tuple(sorted({fold(n) for n in names})))
    if pattern is None:
        return text, 0
    return pattern.subn(lambda m: PLACEHOLDER + (m.group("s") or ""), text)


def replace_in(value: object, names: Sequence[str]) -> tuple[object, int]:
    """The same for a value that may hold text anywhere inside (a program's output: a string, or a
    list or mapping of them): every string in it, at any depth. Other values come back as they were."""
    if isinstance(value, str):
        return replace_names(value, names)
    if isinstance(value, list | tuple):
        total, out = 0, []
        for v in value:
            got, n = replace_in(v, names)
            out.append(got)
            total += n
        return (type(value)(out) if isinstance(value, tuple) else out), total
    if isinstance(value, dict):
        total, mapped = 0, {}
        for k, v in value.items():
            got, n = replace_in(v, names)
            mapped[k] = got
            total += n
        return mapped, total
    return value, 0


def names_note(n: int) -> str | None:
    """What a preview says when it replaced listed names."""
    if not n:
        return None
    return f"{n} name{'' if n == 1 else 's'} you listed {'was' if n == 1 else 'were'} replaced with {PLACEHOLDER}."


def names_for(db: Session, user_id: str) -> tuple[str, ...]:
    """This account's listed names (only its own: the query names the account)."""
    return tuple(db.scalars(select(ListedName.name).where(ListedName.user_id == user_id)).all())


class ListedNames:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _rows(self) -> list[ListedName]:
        return list(
            self.db.scalars(
                select(ListedName).where(ListedName.user_id == self.user.id).order_by(ListedName.folded)
            ).all()
        )

    def all(self) -> list[ListedName]:
        return self._rows()

    def _own(self, name_id: str) -> ListedName:
        row = self.db.get(ListedName, name_id)
        if row is None or row.user_id != self.user.id:
            raise NotFoundError("That name isn't in your list")
        return row

    def add(self, name: str) -> ListedName:
        text = clean(name)
        existing = self.db.scalar(
            select(ListedName).where(ListedName.user_id == self.user.id, ListedName.folded == fold(text))
        )
        if existing is not None:
            return existing  # the same name again (any letter case) is the one already listed
        count = (
            self.db.scalar(
                select(func.count()).select_from(ListedName).where(ListedName.user_id == self.user.id)
            )
            or 0
        )
        if count >= MAX_NAMES:
            raise AppError(f"The list holds up to {MAX_NAMES} names.", code="too_many_names")
        now = datetime.now(UTC)
        row = ListedName(user_id=self.user.id, name=text, folded=fold(text), created_at=now, updated_at=now)
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:  # the same name from another tab at the same moment
            self.db.rollback()
            again = self.db.scalar(
                select(ListedName).where(ListedName.user_id == self.user.id, ListedName.folded == fold(text))
            )
            if again is None:
                raise
            return again
        return row

    def update(self, name_id: str, name: str) -> ListedName:
        row = self._own(name_id)
        text = clean(name)
        clash = self.db.scalar(
            select(ListedName).where(
                ListedName.user_id == self.user.id, ListedName.folded == fold(text), ListedName.id != row.id
            )
        )
        if clash is not None:
            raise ConflictError("That name is already in your list.", code="name_listed")
        row.name, row.folded, row.updated_at = text, fold(text), datetime.now(UTC)
        self.db.commit()
        return row

    def remove(self, name_id: str) -> None:
        self.db.delete(self._own(name_id))
        self.db.commit()

    def export(self) -> list[dict]:
        return [
            {"name": r.name, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat()}
            for r in self._rows()
        ]
