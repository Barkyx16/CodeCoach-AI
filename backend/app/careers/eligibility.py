"""Which saved career answers have a score that counts (the score-eligibility contract).

Every answer keeps its raw stored score; nothing here rewrites or regrades. What this decides is
whether that score may stand for the learner's level in summaries ("best score", averages,
"lowest score first"):

- scored:    the grader recorded `evidence_level: "sufficient"`, or, for answers saved before that
             field existed, the recorded word count is at least MIN_WORDS;
- too_short: `evidence_level: "insufficient"`, or a legacy answer whose recorded word count is
             below MIN_WORDS. Its stored score is capped (at most 35) and isn't a measurement;
- unknown:   neither field was recorded. No answer written by this code base lacks both, but an
             answer like that is reported as unknown, never as a score or as zero.

The legacy rule is a documented contract, not a guess: since the first version of the career
grader (commit f3bb14d) every answer stored its `word_count`, MIN_WORDS has been 40 throughout,
and answers under it were capped at 35 and told they were too short, which is exactly what
`evidence_level` later recorded explicitly. A valid scored answer can have score 35 or 0; the
rule never looks at the score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.careers.grading import MIN_WORDS
from app.models import PracticeAnswer

Eligibility = Literal["scored", "too_short", "unknown"]
ScoreStatus = Literal["scored", "too_short", "unknown"]


def eligibility(evidence_level: Any, word_count: Any) -> Eligibility:
    if evidence_level == "sufficient":
        return "scored"
    if evidence_level == "insufficient":
        return "too_short"
    if isinstance(word_count, int) and not isinstance(word_count, bool):
        return "scored" if word_count >= MIN_WORDS else "too_short"
    return "unknown"


def feedback_eligibility(feedback: dict | None) -> Eligibility:
    fb = feedback or {}
    return eligibility(fb.get("evidence_level"), fb.get("word_count"))


def _fields() -> tuple[Any, Any]:
    """The two recorded fields, read with the database's JSON operator (SQLite and PostgreSQL), so
    summaries don't decode whole feedback documents."""
    return (
        PracticeAnswer.feedback["evidence_level"].as_string(),
        PracticeAnswer.feedback["word_count"].as_integer(),
    )


def eligibility_columns() -> tuple[Any, Any]:
    level, words = _fields()
    return level.label("evidence_level"), words.label("word_count")


def too_short_condition() -> ColumnElement[bool]:
    """SQL: the answer is too short to score (never NULL: missing fields fall through to False).
    Its negation is "scored or unknown"."""
    level, words = _fields()
    return or_(
        func.coalesce(level, "") == "insufficient",
        and_(level.is_(None), func.coalesce(words, MIN_WORDS) < MIN_WORDS),
    )


@dataclass
class QuestionScores:
    """One question's answers by one learner, summarised."""

    attempts: int = 0
    raw_best: int | None = None  # the highest stored score of any answer (the old `best_score`)
    best_scored: int | None = None  # the highest score among answers long enough to score
    too_short: int = 0
    unknown: int = 0

    @property
    def status(self) -> ScoreStatus:
        if self.best_scored is not None:
            return "scored"
        return "unknown" if self.unknown else "too_short"

    def add(self, score: int, kind: Eligibility) -> None:
        self.attempts += 1
        self.raw_best = score if self.raw_best is None else max(self.raw_best, score)
        if kind == "scored":
            self.best_scored = score if self.best_scored is None else max(self.best_scored, score)
        elif kind == "too_short":
            self.too_short += 1
        else:
            self.unknown += 1


def question_scores(db: Session, user_id: str, track: str) -> dict[str, QuestionScores]:
    """Every question this learner answered on `track`: raw best, best scoreable score, counts."""
    rows = db.execute(
        select(PracticeAnswer.question_id, PracticeAnswer.score, *eligibility_columns()).where(
            PracticeAnswer.user_id == user_id, PracticeAnswer.track == track
        )
    ).all()
    out: dict[str, QuestionScores] = {}
    for qid, score, level, words in rows:
        out.setdefault(qid, QuestionScores()).add(int(score), eligibility(level, words))
    return out
