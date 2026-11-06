"""Rubric transparency for written answers: the criteria up front, an optional blind self-review,
neutral "different perspectives", private flags on a criterion, and re-evaluation that only runs
when it could change something and never replaces the original result."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers import grading
from app.careers.answers import OFFLINE_COACH, answer_out, feedback_dict, feedback_points, rubric_version_of
from app.careers.grading import GOOD_MAX, GOOD_MIN, MIN_WORDS, grade
from app.careers.questions import Question, get_question, is_retired
from app.errors import AppError, ConflictError, NotFoundError
from app.models import AnswerEvaluation, AnswerFlag, AnswerSelfReview, PracticeAnswer, User
from app.schemas.answer_review import (
    AnswerPerspective,
    AnswerReviewOut,
    Check,
    CriteriaOut,
    Criterion,
    CriterionLevel,
    EvaluationOut,
    FlagIn,
    FlagOut,
    RepeatedArea,
    SelfReviewIn,
    SelfReviewOut,
)

MAX_EVALUATIONS = 3
RECENT = 10
OVERALL = "Overall"
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(text: str) -> str:
    return _CONTROL.sub("", text).strip()


def _story_kind(q: Question) -> bool:
    # The same condition the grader uses for its "I"/"we" and numbers notes.
    return q.kind in ("behavioral", "general") or any(
        "Situation" in r.label or "scene" in r.label for r in q.rubric
    )


def criteria_for(q: Question) -> CriteriaOut:
    checks = [
        Check(
            text=f"Length: about {GOOD_MIN} to {GOOD_MAX} words reads like a one-to-two-minute spoken answer. "
            f"Under {MIN_WORDS} words there isn't enough to evaluate, so no score is shown."
        ),
        Check(text="Filler phrases (“basically”, “kind of”) are pointed out when there are several."),
    ]
    if _story_kind(q):
        checks.append(
            Check(
                text="For a story from your experience: a number (time, count, %) and saying “I” for what you did are pointed out if missing."
            )
        )
    return CriteriaOut(
        question_id=q.id,
        content_version=q.version,
        rubric_version=grading.RUBRIC_VERSION,
        coach=OFFLINE_COACH,
        criteria=[
            Criterion(
                label=r.label,
                description=r.advice,
                levels=[
                    CriterionLevel(level="not_yet", text=f"Not yet: {r.advice}"),
                    CriterionLevel(
                        level="there", text=f"There: {r.label[0].lower()}{r.label[1:]}, in your own words."
                    ),
                ],
            )
            for r in q.rubric
        ],
        checks=checks,
        disclaimer=(
            "These are CodeCoach's practice criteria for this question, not an employer's rubric. The coach looks for "
            "these points in your words; it doesn't judge whether every detail is true or wise."
        ),
    )


class AnswerReview:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- lookups ------------------------------------------------------------------------------

    def _answer(self, answer_id: str) -> PracticeAnswer:
        a = self.db.get(PracticeAnswer, answer_id)
        if a is None or a.user_id != self.user.id:
            raise NotFoundError("Answer not found")
        return a

    def _labels(self, a: PracticeAnswer) -> list[str]:
        return [p["label"] for p in a.feedback.get("points", [])]

    def _evaluations(self, a: PracticeAnswer) -> list[AnswerEvaluation]:
        return list(
            self.db.scalars(
                select(AnswerEvaluation)
                .where(AnswerEvaluation.answer_id == a.id)
                .order_by(AnswerEvaluation.id)
            )
        )

    def _reevaluation(
        self, a: PracticeAnswer, evals: list[AnswerEvaluation]
    ) -> tuple[Question | None, str | None]:
        """(the question to grade against, None) when a new evaluation could differ; else (None, why not)."""
        q = get_question(a.track, a.question_id)
        if q is None or is_retired(a.track, a.question_id):
            return (
                None,
                "This question is no longer used for practice, so the answer can't be checked again. The result you got is kept.",
            )
        if len(evals) >= MAX_EVALUATIONS:
            return None, f"This answer has been checked again {MAX_EVALUATIONS} times, which is the limit."
        last = (
            (evals[-1].content_version, evals[-1].rubric_version)
            if evals
            else (a.content_version or 1, rubric_version_of(a.feedback))
        )
        if last == (q.version, grading.RUBRIC_VERSION):
            return None, (
                "The built-in coach gives the same result for the same answer under the same rubric and question version, "
                "so checking again wouldn't change anything. If a criterion looks wrong, flag it below or report the feedback."
            )
        return q, None

    # --- reading --------------------------------------------------------------------------------

    def review(self, answer_id: str) -> AnswerReviewOut:
        a = self._answer(answer_id)
        out = answer_out(a)
        sr = self.db.get(AnswerSelfReview, a.id)
        evals = self._evaluations(a)
        flags = self.db.scalars(
            select(AnswerFlag).where(AnswerFlag.answer_id == a.id).order_by(AnswerFlag.id)
        ).all()
        ratings = sr.ratings if sr and not sr.skipped else {}
        q, why_not = self._reevaluation(a, evals)
        return AnswerReviewOut(
            answer=out,
            self_review=self._self_review_out(sr) if sr else None,
            perspectives=[
                AnswerPerspective(criterion=p.label, yours=ratings.get(p.label), coach=p.covered)
                for p in out.points
            ],
            repeated=self._repeated(a),
            flags=[self._flag_out(f) for f in flags],
            evaluations=[self._evaluation_out(e, a.answer) for e in evals],
            can_reevaluate=q is not None,
            reevaluate_note=why_not
            or "The question or the rubric changed since this answer was checked. Checking again records a new evaluation beside the original.",
        )

    def _repeated(self, a: PracticeAnswer) -> list[RepeatedArea]:
        """Points this answer is missing that were also missing in other recent answers on the career.
        Something to look at, not a verdict on the learner."""
        recent = self.db.scalars(
            select(PracticeAnswer)
            .where(PracticeAnswer.user_id == self.user.id, PracticeAnswer.track == a.track)
            .order_by(PracticeAnswer.created_at.desc())
            .limit(RECENT)
        ).all()
        missing = Counter(
            p["label"] for r in recent for p in r.feedback.get("points", []) if not p.get("covered")
        )
        mine = [p["label"] for p in a.feedback.get("points", []) if not p.get("covered")]
        return [
            RepeatedArea(criterion=label, times=missing[label], of=len(recent))
            for label in mine
            if missing[label] >= 2
        ]

    @staticmethod
    def _self_review_out(sr: AnswerSelfReview) -> SelfReviewOut:
        return SelfReviewOut(
            went_well=sr.went_well,
            improve=sr.improve,
            ratings=sr.ratings,
            skipped=sr.skipped,
            before_feedback=sr.before_feedback,
            updated_at=sr.updated_at,
        )

    @staticmethod
    def _flag_out(f: AnswerFlag) -> FlagOut:
        return FlagOut(id=f.id, criterion=f.criterion, kind=f.kind, note=f.note, created_at=f.created_at)

    @staticmethod
    def _evaluation_out(e: AnswerEvaluation, answer: str) -> EvaluationOut:
        fb = e.feedback
        return EvaluationOut(
            id=e.id,
            rubric_version=e.rubric_version,
            content_version=e.content_version,
            score=e.score,
            rating=fb["rating"],
            summary=fb["summary"],
            evidence_level=fb.get("evidence_level", "sufficient"),
            # checked against the answer like the original feedback's (app/careers/evidence.py)
            points=[p.model_dump() for p in feedback_points(answer, fb["points"])],
            reason=e.reason,
            created_at=e.created_at,
        )

    # --- writing -------------------------------------------------------------------------------

    def save_self_review(self, answer_id: str, body: SelfReviewIn) -> AnswerReviewOut:
        a = self._answer(answer_id)
        labels = set(self._labels(a))
        unknown = [k for k in body.ratings if k not in labels]
        if unknown:
            raise AppError(
                "Rate only the criteria for this answer.",
                code="unknown_criterion",
                details={"unknown": unknown},
            )
        sr = self.db.get(AnswerSelfReview, a.id)
        if sr is None:
            sr = AnswerSelfReview(answer_id=a.id, user_id=self.user.id)
            self.db.add(sr)
        if body.skipped:
            sr.went_well, sr.improve, sr.ratings = "", "", {}
        else:
            sr.went_well, sr.improve, sr.ratings = (
                _clean(body.went_well),
                _clean(body.improve),
                dict(body.ratings),
            )
        sr.skipped = body.skipped
        # Once written after the feedback was read, it no longer counts as "before".
        sr.before_feedback = body.before_feedback and (sr.before_feedback if sr.updated_at else True)
        sr.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.review(a.id)

    def add_flag(self, answer_id: str, body: FlagIn) -> AnswerReviewOut:
        a = self._answer(answer_id)
        if body.criterion not in {*self._labels(a), OVERALL}:
            raise AppError(
                "Flag one of this answer's criteria, or the feedback overall.", code="unknown_criterion"
            )
        f = self.db.scalar(
            select(AnswerFlag).where(AnswerFlag.answer_id == a.id, AnswerFlag.criterion == body.criterion)
        )
        if f is None:
            f = AnswerFlag(answer_id=a.id, user_id=self.user.id, criterion=body.criterion)
            self.db.add(f)
        f.kind, f.note = body.kind, _clean(body.note)
        self.db.commit()
        return self.review(a.id)

    def remove_flag(self, answer_id: str, flag_id: int) -> AnswerReviewOut:
        a = self._answer(answer_id)
        f = self.db.get(AnswerFlag, flag_id)
        if f is None or f.answer_id != a.id:
            raise NotFoundError("Flag not found")
        self.db.delete(f)
        self.db.commit()
        return self.review(a.id)

    def reevaluate(self, answer_id: str, reason: str) -> AnswerReviewOut:
        a = self._answer(answer_id)
        q, why_not = self._reevaluation(a, self._evaluations(a))
        if q is None:
            raise ConflictError(why_not or "Can't check this answer again.", code="no_reevaluation")
        fb = grade(q, a.answer)
        self.db.add(
            AnswerEvaluation(
                answer_id=a.id,
                user_id=self.user.id,
                rubric_version=grading.RUBRIC_VERSION,
                content_version=q.version,
                score=fb.score,
                feedback=feedback_dict(fb, q),
                reason=_clean(reason)[:500],
            )
        )
        self.db.commit()  # the original answer row and its feedback are untouched
        return self.review(a.id)

    def export(self) -> dict:
        uid = self.user.id
        return {
            "self_reviews": [
                {
                    "answer_id": s.answer_id,
                    "went_well": s.went_well,
                    "improve": s.improve,
                    "ratings": s.ratings,
                    "skipped": s.skipped,
                    "before_feedback": s.before_feedback,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in self.db.scalars(select(AnswerSelfReview).where(AnswerSelfReview.user_id == uid))
            ],
            "flags": [
                {
                    "answer_id": f.answer_id,
                    "criterion": f.criterion,
                    "kind": f.kind,
                    "note": f.note,
                    "created_at": f.created_at.isoformat(),
                }
                for f in self.db.scalars(select(AnswerFlag).where(AnswerFlag.user_id == uid))
            ],
            "evaluations": [
                {
                    "answer_id": e.answer_id,
                    "rubric_version": e.rubric_version,
                    "content_version": e.content_version,
                    "score": e.score,
                    "feedback": e.feedback,
                    "reason": e.reason,
                    "created_at": e.created_at.isoformat(),
                }
                for e in self.db.scalars(select(AnswerEvaluation).where(AnswerEvaluation.user_id == uid))
            ],
        }
