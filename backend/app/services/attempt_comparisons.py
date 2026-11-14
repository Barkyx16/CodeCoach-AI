"""The facts the comparison contract looks at, gathered from what's recorded, and each attempt's
comparison with the attempt before it (app/careers/comparability.py; docs/COMPARING_ATTEMPTS.md).

Every surface that compares written answers (the question page's tries, an interview retry, the
progress chart's list) gets its classifications here, so the same pair always reads the same.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers.comparability import (
    SOURCES,
    AttemptFacts,
    Classification,
    Format,
    classify,
    previous_of,
)
from app.careers.eligibility import feedback_eligibility
from app.models import InterviewRetry, InterviewTurn, PracticeAnswer, PracticeSession, User
from app.schemas.careers import AttemptComparison, ComparisonReason
from app.schemas.conditions import AttemptConditions
from app.services.conditions import RECORDED_FROM, Conditions

# Written answers are graded 0-100 by the coach (app/careers/grading.py): the scale belongs to the
# kind of attempt, not a guess about one.
WRITTEN_SCALE = "0-100"


def recorded_rubric(feedback: dict) -> str | None:
    """The rubric version as recorded: its own field, or inside the recorded evaluator name. Never a
    default: an answer that recorded neither says so."""
    if feedback.get("rubric_version"):
        return str(feedback["rubric_version"])
    evaluator = str(feedback.get("evaluator") or "")
    if "rubric " in evaluator:
        return evaluator.rpartition("rubric ")[2].strip() or None
    return None


def comparison_out(against: str, c: Classification) -> AttemptComparison:
    return AttemptComparison(
        against=against,
        outcome=c.outcome,
        scores_comparable=c.scores_comparable,
        points_comparable=c.points_comparable,
        reasons=[ComparisonReason(rule=r.rule, kind=r.kind, text=r.text) for r in c.reasons],
        explanation=c.explanation,
        contract_version=c.contract_version,
    )


class AttemptComparisons:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.conditions: dict[str, AttemptConditions] = {}  # filled by facts(), for reuse

    def _formats(self, ids: set[str]) -> dict[str, Format]:
        """Single question unless an interview turn or a retry records it (neither is deleted apart
        from the answer)."""
        out: dict[str, Format] = {}
        if not ids:
            return out
        for (aid,) in self.db.execute(
            select(InterviewTurn.answer_id)
            .join(PracticeSession, PracticeSession.id == InterviewTurn.session_id)
            .where(PracticeSession.user_id == self.user.id, InterviewTurn.answer_id.in_(ids))
        ):
            if aid is not None:
                out[aid] = "interview"
        for (aid,) in self.db.execute(
            select(InterviewRetry.retry_answer_id).where(
                InterviewRetry.user_id == self.user.id, InterviewRetry.retry_answer_id.in_(ids)
            )
        ):
            out[aid] = "retry"
        return out

    def facts(self, answers: Iterable[PracticeAnswer]) -> dict[str, AttemptFacts]:
        answers = [a for a in answers if a.user_id == self.user.id]
        formats = self._formats({a.id for a in answers})
        help = Conditions(self.db, self.user).for_answers(answers)
        self.conditions.update(help)
        out: dict[str, AttemptFacts] = {}
        for a in answers:
            fb = a.feedback or {}
            labels = tuple(help[a.id].labels) if a.id in help else None
            out[a.id] = AttemptFacts(
                id=a.id,
                track=a.track,
                question_id=a.question_id,
                question_version=a.content_version or 1,
                scale=WRITTEN_SCALE,
                rubric=recorded_rubric(fb),
                source=SOURCES.get(a.provider or ""),
                scoring=feedback_eligibility(fb),
                format=formats.get(a.id, "single"),
                help=None if labels is None or labels == ("Not recorded",) else labels,
                help_recorded_from=RECORDED_FROM.date(),
            )
        return out

    def with_previous(self, answers: Iterable[PracticeAnswer]) -> dict[str, tuple[str, Classification]]:
        """For each answer with an earlier one to the same question among ``answers``: (that
        answer's id, the classification). Pass every answer to the questions concerned, so the
        earlier one is always there to compare with."""
        answers = list(answers)
        facts = self.facts(answers)
        by_question: dict[tuple[str, str], list[PracticeAnswer]] = defaultdict(list)
        for a in answers:
            by_question[(a.track, a.question_id)].append(a)
        out: dict[str, tuple[str, Classification]] = {}
        for rows in by_question.values():
            rows.sort(key=lambda r: (r.created_at, r.id))
            revises = {r.id: r.revises_answer_id for r in rows}
            for i, r in enumerate(rows):
                j = previous_of(rows, i, revises)
                if j is not None:
                    out[r.id] = (rows[j].id, classify(facts[rows[j].id], facts[r.id]))
        return out

    def for_questions(self, keys: set[tuple[str, str]]) -> list[PracticeAnswer]:
        """Every answer of this account to these questions (to find each one's earlier attempt)."""
        if not keys:
            return []
        tracks = {t for t, _ in keys}
        rows = self.db.scalars(
            select(PracticeAnswer).where(
                PracticeAnswer.user_id == self.user.id,
                PracticeAnswer.track.in_(tracks),
                PracticeAnswer.question_id.in_({q for _, q in keys}),
            )
        ).all()
        return [r for r in rows if (r.track, r.question_id) in keys]
