"""Communication drills: quick, recoverable attempts with grounded feedback and comparisons."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.drills import BY_ID, DRILLS, RUBRIC_VERSION, Drill, prompt_for
from app.drills.feedback import compare, evaluate, words
from app.errors import AppError, NotFoundError, RateLimitedError
from app.models import DrillAttempt, User
from app.schemas.drills import DrillAttemptIn, DrillAttemptOut, DrillOut
from app.services import request_keys

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MIN_WORDS = 3
MAX_PER_DRILL = 200


class Drills:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _drill(self, drill_id: str) -> Drill:
        d = BY_ID.get(drill_id)
        if d is None:
            raise NotFoundError("Drill not found")
        return d

    def _count(self, drill_id: str) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(DrillAttempt)
                .where(DrillAttempt.user_id == self.user.id, DrillAttempt.drill_id == drill_id)
            )
            or 0
        )

    def _out(self, d: Drill) -> DrillOut:
        return DrillOut(
            id=d.id,
            title=d.title,
            objective=d.objective,
            looks_for=list(d.looks_for),
            target_seconds=d.target_seconds,
            prompt=prompt_for(d, self.user.career_track),
            attempts=self._count(d.id),
        )

    def all(self) -> list[DrillOut]:
        return [self._out(d) for d in DRILLS]

    def get(self, drill_id: str) -> DrillOut:
        return self._out(self._drill(drill_id))

    def _attempt_out(self, a: DrillAttempt, previous: DrillAttempt | None) -> DrillAttemptOut:
        return DrillAttemptOut(
            id=a.id,
            drill_id=a.drill_id,
            prompt=a.prompt,
            text=a.text,
            source=a.source,
            spoken_seconds=a.spoken_seconds,
            rubric_version=a.rubric_version,
            feedback=a.feedback,
            compared_with_previous=compare(previous.feedback, a.feedback) if previous else None,
            created_at=a.created_at,
        )

    def attempts(self, drill_id: str) -> list[DrillAttemptOut]:
        self._drill(drill_id)
        rows = self.db.scalars(
            select(DrillAttempt)
            .where(DrillAttempt.user_id == self.user.id, DrillAttempt.drill_id == drill_id)
            .order_by(DrillAttempt.created_at)
        ).all()
        out = [self._attempt_out(a, rows[i - 1] if i else None) for i, a in enumerate(rows)]
        return list(reversed(out))

    def submit(self, drill_id: str, body: DrillAttemptIn, limiter) -> tuple[DrillAttemptOut, bool]:
        d = self._drill(drill_id)
        text = _CONTROL.sub("", body.text).strip()
        if body.client_request_id and (existing := self._by_request(body.client_request_id)) is not None:
            self._same_attempt(existing, d.id, text, body)
            return self._with_previous(existing), False
        # Silence, an aborted recording or a failed transcription never counts as an attempt.
        if len(words(text)) < MIN_WORDS:
            raise AppError(
                "There's nothing to give feedback on yet. Say or type a few words, then send.",
                code="too_little",
            )
        if body.source == "typed" and body.spoken_seconds is not None:
            raise AppError("Spoken time is only for recorded answers.", code="invalid_measure")
        allowed, retry = limiter.hit(f"drill:{self.user.id}")
        if not allowed:
            raise RateLimitedError.wait(
                "That's a lot of drills this hour. Take a short break.",
                retry,
            )
        if self._count(d.id) >= MAX_PER_DRILL:
            raise AppError(
                "You've reached the limit of saved attempts for this drill.", code="too_many_attempts"
            )
        prompt = prompt_for(d, self.user.career_track)
        a = DrillAttempt(
            user_id=self.user.id,
            drill_id=d.id,
            track=self.user.career_track,
            prompt=prompt,
            text=text,
            source=body.source,
            spoken_seconds=body.spoken_seconds,
            rubric_version=RUBRIC_VERSION,
            feedback=evaluate(d, prompt, text, body.source, body.spoken_seconds),
            client_request_id=body.client_request_id,
        )
        self.db.add(a)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._by_request(body.client_request_id) if body.client_request_id else None
            if existing is None:
                raise
            self._same_attempt(existing, d.id, text, body)
            return self._with_previous(existing), False
        return self._with_previous(a), True

    def _by_request(self, key: str) -> DrillAttempt | None:
        return self.db.scalar(
            select(DrillAttempt).where(
                DrillAttempt.user_id == self.user.id, DrillAttempt.client_request_id == key
            )
        )

    @staticmethod
    def _same_attempt(existing: DrillAttempt, drill_id: str, text: str, body: DrillAttemptIn) -> None:
        """An attempt is never edited, so a resend is compared with what it saved: the same key
        for another drill or other words is refused, not answered with the first feedback."""
        if (existing.drill_id, existing.text, existing.source, existing.spoken_seconds) != (
            drill_id,
            text,
            body.source,
            body.spoken_seconds,
        ):
            raise request_keys.reused("drill attempt")

    def _with_previous(self, a: DrillAttempt) -> DrillAttemptOut:
        prev = self.db.scalar(
            select(DrillAttempt)
            .where(
                DrillAttempt.user_id == self.user.id,
                DrillAttempt.drill_id == a.drill_id,
                DrillAttempt.created_at < a.created_at,
            )
            .order_by(DrillAttempt.created_at.desc())
            .limit(1)
        )
        return self._attempt_out(a, prev)

    def export(self) -> list[dict]:
        return [
            {
                "drill": a.drill_id,
                "prompt": a.prompt,
                "text": a.text,
                "source": a.source,
                "spoken_seconds": a.spoken_seconds,
                "rubric_version": a.rubric_version,
                "feedback": a.feedback,
                "created_at": a.created_at.isoformat(),
            }
            for a in self.db.scalars(select(DrillAttempt).where(DrillAttempt.user_id == self.user.id))
        ]
