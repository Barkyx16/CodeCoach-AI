"""Running offer rehearsals on the server (docs/OFFER_REHEARSAL.md).

The rehearsal row holds the phase and every turn; the client sends a turn's text, how it was
entered and the last turn it saw, never where the conversation goes. A resent turn (same request
key, same text) returns the rehearsal unchanged; the same key with other text is refused; a turn
written against an older state is refused so two tabs can't talk over each other. The
counterpart's replies come from app/offers/talk.py, on the snapshot the rehearsal started with,
and nothing here calls an AI provider, sends anything, or touches an application.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, ConflictError, NotFoundError
from app.models import OfferRehearsal, User
from app.offers import BY_ID, CASES, PHASE_TITLES, PHASES, OfferCase, Phase, from_snapshot
from app.offers.talk import MODE, debrief, opener, reply
from app.schemas.offers import (
    OfferCard,
    OfferCaseSummary,
    OfferPhaseIn,
    OfferPhaseOut,
    OfferRehearsalIn,
    OfferRehearsalOut,
    OfferRehearsalSummary,
    OfferTermOut,
    OfferTurnIn,
    OfferTurnOut,
)
from app.services import request_keys

MAX_PER_PHASE = 3
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _now() -> datetime:
    return datetime.now(UTC)


def _case(case_id: str) -> OfferCase:
    c = BY_ID.get(case_id)
    if c is None:
        raise NotFoundError("Offer case not found")
    return c


def _clean(text: str) -> str:
    return _CONTROL.sub("", text).strip()


def card(c: OfferCase) -> OfferCard:
    return OfferCard(
        id=c.id,
        version=c.version,
        title=c.title,
        role=c.role,
        employer=c.employer,
        counterpart=c.counterpart,
        currency=c.currency,
        terms=[OfferTermOut(id=t.id, label=t.label, value=t.value) for t in c.terms],
        phases=[OfferPhaseOut(id=p, title=PHASE_TITLES[p]) for p in PHASES],
        review_status=c.review_status,
    )


class Offers:
    def __init__(self, db: Session | None = None, user: User | None = None):
        self.db = db
        self.user = user

    # --- the fictional cards ---------------------------------------------------------------------
    @staticmethod
    def cases() -> list[OfferCaseSummary]:
        return [OfferCaseSummary(id=c.id, title=c.title, role=c.role, employer=c.employer) for c in CASES]

    @staticmethod
    def case(case_id: str) -> OfferCard:
        return card(_case(case_id))

    @property
    def _db(self) -> Session:
        assert self.db is not None
        return self.db

    @property
    def _me(self) -> User:
        assert self.user is not None
        return self.user

    def _find(self, rehearsal_id: str, *, lock: bool = False) -> OfferRehearsal:
        q = select(OfferRehearsal).where(OfferRehearsal.id == rehearsal_id)
        if lock:
            q = q.with_for_update()
        r = self._db.scalar(q)
        if r is None or r.user_id != self._me.id:
            raise NotFoundError("Rehearsal not found")
        return r

    # --- a rehearsal -----------------------------------------------------------------------------
    def start(self, body: OfferRehearsalIn) -> OfferRehearsalOut:
        c = _case(body.case_id)
        goals = [g for g in (_clean(x)[:200] for x in body.goals) if g]
        if body.parent_id is None:
            open_one = self._db.scalar(
                select(OfferRehearsal).where(
                    OfferRehearsal.user_id == self._me.id,
                    OfferRehearsal.case_id == c.id,
                    OfferRehearsal.status == "in_progress",
                )
            )
            if open_one is not None:
                return self._out(open_one)  # resume it rather than start a second
        else:
            parent = self._find(body.parent_id)
            if parent.case_id != c.id or parent.status != "completed":
                raise ConflictError(
                    "Try a different approach after finishing a rehearsal of this case.",
                    code="parent_not_finished",
                )
        now = _now()
        r = OfferRehearsal(
            user_id=self._me.id,
            case_id=c.id,
            case_version=c.version,
            snapshot=c.snapshot(),
            goals=goals,
            status="in_progress",
            phase="clarify",
            turns=[
                {
                    "seq": 1,
                    "speaker": "counterpart",
                    "phase": "clarify",
                    "text": opener(c, "clarify"),
                    "at": now.isoformat(),
                }
            ],
            parent_id=body.parent_id,
            created_at=now,
            updated_at=now,
        )
        self._db.add(r)
        self._db.commit()
        return self._out(r)

    def turn(self, rehearsal_id: str, body: OfferTurnIn) -> OfferRehearsalOut:
        r = self._find(rehearsal_id, lock=True)
        turns = list(r.turns or [])
        text = _clean(body.text)
        if body.client_request_id:
            sent = next((t for t in turns if t.get("client_request_id") == body.client_request_id), None)
            if sent is not None:
                if sent["text"] != text:
                    raise request_keys.reused("message")
                return self._out(r)  # the same turn again (a retry after a lost reply): nothing changes
        if r.status != "in_progress":
            raise ConflictError(
                "This rehearsal is finished. Start a different approach to try again.",
                code="rehearsal_finished",
            )
        if body.after_seq != turns[-1]["seq"]:
            raise ConflictError(
                "The conversation moved on in another tab or window. Reload to see where it is.",
                code="rehearsal_advanced",
            )
        if not text:
            raise AppError("Write or say something first.", code="turn_empty")
        phase: Phase = r.phase  # type: ignore[assignment]
        if sum(1 for t in turns if t["speaker"] == "learner" and t["phase"] == phase) >= MAX_PER_PHASE:
            raise ConflictError(
                f"That's {MAX_PER_PHASE} turns in this part. Move on to the next part, or finish.",
                code="phase_full",
            )
        oc = from_snapshot(r.snapshot)
        now = _now().isoformat()
        seq = turns[-1]["seq"]
        turns.append(
            {
                "seq": seq + 1,
                "speaker": "learner",
                "phase": phase,
                "text": text,
                "source": body.source,
                "at": now,
                "client_request_id": body.client_request_id,
            }
        )
        answer = reply(oc, phase, text)
        turns.append(
            {"seq": seq + 2, "speaker": "counterpart", "phase": phase, "text": answer.text, "at": now}
        )
        r.turns = turns
        r.updated_at = _now()
        if answer.concluded:
            self._complete(r)
        self._db.commit()
        return self._out(r)

    def advance(self, rehearsal_id: str, body: OfferPhaseIn) -> OfferRehearsalOut:
        r = self._find(rehearsal_id, lock=True)
        here = PHASES.index(r.phase)
        asked = PHASES.index(body.from_phase)
        if here > asked or r.status != "in_progress":
            return self._out(r)  # already moved on (another tab, a retried click)
        if here < asked:
            raise ConflictError(
                "That part hasn't started yet. Reload to see where you are.", code="rehearsal_advanced"
            )
        if here == len(PHASES) - 1:
            raise ConflictError("This is the last part. Finish to see the debrief.", code="last_phase")
        nxt = PHASES[here + 1]
        oc = from_snapshot(r.snapshot)
        turns = list(r.turns or [])
        turns.append(
            {
                "seq": turns[-1]["seq"] + 1,
                "speaker": "counterpart",
                "phase": nxt,
                "text": opener(oc, nxt),
                "at": _now().isoformat(),
            }
        )
        r.turns = turns
        r.phase = nxt
        r.updated_at = _now()
        self._db.commit()
        return self._out(r)

    def finish(self, rehearsal_id: str) -> OfferRehearsalOut:
        r = self._find(rehearsal_id, lock=True)
        if r.status != "completed":
            self._complete(r)
            self._db.commit()
        return self._out(r)

    def _complete(self, r: OfferRehearsal) -> None:
        r.status = "completed"
        r.completed_at = _now()
        r.updated_at = r.completed_at
        r.debrief = debrief(r.snapshot, list(r.turns or []), list(r.goals or []))

    def get(self, rehearsal_id: str) -> OfferRehearsalOut:
        return self._out(self._find(rehearsal_id))

    def mine(self) -> list[OfferRehearsalSummary]:
        rows = self._db.scalars(
            select(OfferRehearsal)
            .where(OfferRehearsal.user_id == self._me.id)
            .order_by(OfferRehearsal.created_at.desc())
        ).all()
        return [
            OfferRehearsalSummary(
                id=r.id,
                case_id=r.case_id,
                title=r.snapshot["title"],
                status=r.status,
                outcome=(r.debrief or {}).get("outcome"),
                parent_id=r.parent_id,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
            for r in rows
        ]

    def _out(self, r: OfferRehearsal) -> OfferRehearsalOut:
        current = BY_ID.get(r.case_id)
        oc = from_snapshot(r.snapshot)
        turns = list(r.turns or [])
        used = sum(1 for t in turns if t["speaker"] == "learner" and t["phase"] == r.phase)
        return OfferRehearsalOut(
            id=r.id,
            case_id=r.case_id,
            case_version=r.case_version,
            current_version=current.version if current else None,
            card=card(oc),
            goals=list(r.goals or []),
            status=r.status,
            phase=r.phase,
            turns=[
                OfferTurnOut(
                    seq=t["seq"],
                    speaker=t["speaker"],
                    phase=t["phase"],
                    text=t["text"],
                    source=t.get("source"),
                    at=datetime.fromisoformat(t["at"]),
                )
                for t in turns
            ],
            turns_left_in_phase=0 if r.status != "in_progress" else max(0, MAX_PER_PHASE - used),
            parent_id=r.parent_id,
            mode=MODE,
            debrief=r.debrief,
            created_at=r.created_at,
            updated_at=r.updated_at,
            completed_at=r.completed_at,
        )

    def export(self) -> list[dict[str, Any]]:
        return [
            {
                "case": r.case_id,
                "case_version": r.case_version,
                "goals": r.goals,
                "status": r.status,
                "turns": [{k: v for k, v in t.items() if k != "client_request_id"} for t in r.turns or []],
                "debrief": r.debrief,
                "parent_id": r.parent_id,
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in self._db.scalars(select(OfferRehearsal).where(OfferRehearsal.user_id == self._me.id))
        ]
