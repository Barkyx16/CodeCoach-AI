"""Comparing authored sample answers (docs/COMPARE_ANSWERS.md). The lesson is public; the
explanation is a deliberate reveal; a learner's reading is theirs, frozen with the samples and the
explanation it was compared with. Reasons are plain text (control characters removed). Nothing
here changes a plan, a score or progress."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.comparisons import BY_ID, LESSONS, Lesson
from app.comparisons.feedback import evaluate
from app.errors import AppError, NotFoundError
from app.models import ComparisonAttempt, User
from app.schemas.comparisons import (
    ComparisonAttemptIn,
    ComparisonAttemptOut,
    ComparisonAttemptSummary,
    ComparisonLesson,
    ComparisonSummary,
)

MAX_ATTEMPTS_PER_LESSON = 50
MIN_REASON_WORDS = 3
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _lesson(lesson_id: str) -> Lesson:
    lesson = BY_ID.get(lesson_id)
    if lesson is None:
        raise NotFoundError("Comparison lesson not found")
    return lesson


class Comparisons:
    def __init__(self, db: Session | None = None, user: User | None = None):
        self.db = db
        self.user = user

    @staticmethod
    def lessons() -> list[ComparisonSummary]:
        return [ComparisonSummary(id=ls.id, title=ls.title, teaching_goal=ls.teaching_goal) for ls in LESSONS]

    @staticmethod
    def lesson(lesson_id: str) -> ComparisonLesson:
        ls = _lesson(lesson_id)
        return ComparisonLesson.model_validate(
            {
                "id": ls.id,
                "version": ls.version,
                "title": ls.title,
                "teaching_goal": ls.teaching_goal,
                "question": ls.question,
                "rubric": list(ls.rubric),
                "kind": ls.kind,
                "samples": list(ls.samples),
                "next_step": ls.next_step,
                "review_status": ls.review_status,
            }
        )

    @staticmethod
    def explanation(lesson_id: str) -> dict[str, Any]:
        return dict(_lesson(lesson_id).explanation)

    @property
    def _db(self) -> Session:
        assert self.db is not None
        return self.db

    @property
    def _me(self) -> User:
        assert self.user is not None
        return self.user

    def attempt(self, lesson_id: str, body: ComparisonAttemptIn) -> ComparisonAttemptOut:
        ls = _lesson(lesson_id)
        seen: set[tuple[str, str, str]] = set()
        selections = []
        for i, s in enumerate(body.selections, 1):
            text = ls.sentence(s.sample, s.sentence)
            if text is None:
                raise AppError(
                    f"Excerpt {i} isn't in this version of the samples. Reload the lesson.",
                    code="unknown_excerpt",
                )
            key = (s.sample, s.sentence, s.kind)
            if key in seen:
                raise AppError(f"Excerpt {i} is marked twice the same way.", code="duplicate_excerpt")
            seen.add(key)
            reason = _CONTROL.sub("", s.reason).strip()
            if len(re.findall(r"[\w']+", reason)) < MIN_REASON_WORDS:
                raise AppError(
                    f"Excerpt {i}: say why in a few words. The reason is the point of the exercise.",
                    code="reason_required",
                )
            selections.append(
                {"sample": s.sample, "sentence": s.sentence, "quote": text, "kind": s.kind, "reason": reason}
            )
        sample_ids = {s["id"] for s in ls.samples}
        if body.choice is not None and (ls.kind == "tradeoff" or body.choice not in sample_ids):
            raise AppError(
                "This lesson has no single best answer, so there's nothing to choose."
                if ls.kind == "tradeoff"
                else "Choose one of the answers shown.",
                code="invalid_choice",
            )
        n = (
            self._db.scalar(
                select(func.count())
                .select_from(ComparisonAttempt)
                .where(ComparisonAttempt.user_id == self._me.id, ComparisonAttempt.lesson_id == lesson_id)
            )
            or 0
        )
        if n >= MAX_ATTEMPTS_PER_LESSON:
            raise AppError(
                "You've reached the limit of saved attempts for this lesson.", code="too_many_attempts"
            )
        snapshot = ls.snapshot()
        a = ComparisonAttempt(
            user_id=self._me.id,
            lesson_id=ls.id,
            lesson_version=ls.version,
            snapshot=snapshot,
            selections=selections,
            choice=body.choice,
            feedback=evaluate(snapshot, selections, body.choice),
            revealed_early=body.revealed_early,
        )
        self._db.add(a)
        self._db.commit()
        return self._out(a)

    def _out(self, a: ComparisonAttempt) -> ComparisonAttemptOut:
        current = BY_ID.get(a.lesson_id)
        snap = a.snapshot
        return ComparisonAttemptOut.model_validate(
            {
                "id": a.id,
                "lesson_id": a.lesson_id,
                "lesson_version": a.lesson_version,
                "current_version": current.version if current else None,
                "title": snap["title"],
                "question": snap["question"],
                "samples": snap["samples"],
                "rubric": snap["rubric"],
                "selections": a.selections,
                "choice": a.choice,
                "feedback": a.feedback,
                "explanation": snap["explanation"],
                "revealed_early": a.revealed_early,
                "created_at": a.created_at,
            }
        )

    def attempts(self, lesson_id: str) -> list[ComparisonAttemptSummary]:
        _lesson(lesson_id)
        rows = self._db.scalars(
            select(ComparisonAttempt)
            .where(ComparisonAttempt.user_id == self._me.id, ComparisonAttempt.lesson_id == lesson_id)
            .order_by(ComparisonAttempt.created_at.desc())
        ).all()
        return [
            ComparisonAttemptSummary(
                id=a.id,
                lesson_version=a.lesson_version,
                selections=len(a.selections),
                matches=a.feedback.get("counts", {}).get("matches", 0),
                revealed_early=a.revealed_early,
                created_at=a.created_at,
            )
            for a in rows
        ]

    def get_attempt(self, attempt_id: str) -> ComparisonAttemptOut:
        a = self._db.get(ComparisonAttempt, attempt_id)
        if a is None or a.user_id != self._me.id:
            raise NotFoundError("Attempt not found")
        return self._out(a)

    def export(self) -> list[dict[str, Any]]:
        return [
            {
                "lesson": a.lesson_id,
                "lesson_version": a.lesson_version,
                "selections": a.selections,
                "choice": a.choice,
                "revealed_early": a.revealed_early,
                "feedback": a.feedback,
                "created_at": a.created_at.isoformat(),
            }
            for a in self._db.scalars(
                select(ComparisonAttempt).where(ComparisonAttempt.user_id == self._me.id)
            )
        ]
