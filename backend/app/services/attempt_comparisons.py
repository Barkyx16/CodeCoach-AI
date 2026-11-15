"""The facts the comparison contract looks at, gathered from what's recorded, and each attempt's
comparison with the attempt before it (app/careers/comparability.py; docs/COMPARING_ATTEMPTS.md).

Every surface that compares written answers (the question page's tries, an interview retry, the
progress chart's list) gets its classifications here, so the same pair always reads the same. Coding
submissions too (Volume 14, prompt 1): the submission page, the workspace's result and History.
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
from app.models import (
    InterviewRetry,
    InterviewTurn,
    PracticeAnswer,
    PracticeSession,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    User,
)
from app.schemas.careers import AttemptComparison, ComparisonReason
from app.schemas.conditions import AttemptConditions
from app.schemas.submission import ComparedSubmission, SubmissionComparison
from app.services.conditions import RECORDED_FROM, Conditions, problem_versions

# Written answers are graded 0-100 by the coach (app/careers/grading.py): the scale belongs to the
# kind of attempt, not a guess about one.
WRITTEN_SCALE = "0-100"
# A submission's result is tests passed of the problem's tests, judged by the code judge.
CODE_SCALE = "tests passed"
CODE_RUBRIC = "the problem's tests"
# Verdicts on the learner's code. INTERNAL_ERROR is the judge's own failure: no verdict.
VERDICTS = frozenset(
    {
        SubmissionStatus.PASSED,
        SubmissionStatus.FAILED,
        SubmissionStatus.COMPILE_ERROR,
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.TIME_LIMIT,
        SubmissionStatus.MEMORY_LIMIT,
    }
)


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


def compared_view(previous: Submission, classification: Classification) -> SubmissionComparison:
    """A submission's comparison as shown: the earlier one's verdict and counts, and the classification."""
    from app.services.judge.views import public_result_view

    r = public_result_view(previous)
    return SubmissionComparison(
        previous=ComparedSubmission(
            id=previous.id,
            status=previous.status,
            created_at=previous.created_at,
            passed_count=r.passed_count if r else None,
            total_count=r.total_count if r else None,
            hidden_passed=r.hidden_passed if r else None,
            hidden_total=r.hidden_total if r else None,
        ),
        comparison=comparison_out(previous.id, classification),
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
            rnd = help[a.id].round if a.id in help else None
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
                help_recorded_from=help[a.id].recorded_from if a.id in help else RECORDED_FROM.date(),
                timed_minutes=rnd.timed_minutes if rnd else None,
                follow_up=rnd.follow_up if rnd else None,
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

    # --- coding submissions ------------------------------------------------------------------------

    def submission_facts(self, subs: Iterable[Submission]) -> dict[str, AttemptFacts]:
        subs = [x for x in subs if x.user_id == self.user.id]
        if not subs:
            return {}
        current = problem_versions(self.db, {x.problem_id for x in subs})
        help = Conditions(self.db, self.user).for_submissions(subs)
        self.conditions.update(help)
        out: dict[str, AttemptFacts] = {}
        for x in subs:
            labels = tuple(help[x.id].labels) if x.id in help else None
            # Not recorded: known only if the problem never had another version of its tests.
            version = (
                x.content_version
                if x.content_version is not None
                else (1 if current[x.problem_id] == 1 else None)
            )
            out[x.id] = AttemptFacts(
                id=x.id,
                track="code",
                question_id=str(x.problem_id),
                question_version=version,
                scale=CODE_SCALE,
                rubric=CODE_RUBRIC,
                source="judge",
                scoring="scored" if x.status in VERDICTS else "not_judged",
                format="run" if x.mode == SubmissionMode.RUN else "submit",
                help=None if labels is None or labels == ("Not recorded",) else labels,
                help_recorded_from=help[x.id].recorded_from if x.id in help else RECORDED_FROM.date(),
                kind="code",
            )
        return out

    def submissions_with_previous(
        self, subs: Iterable[Submission]
    ) -> dict[str, tuple[Submission, Classification]]:
        """For each finished submission among ``subs``: the previous judged submission of the same
        problem in the same mode, and the classification. A run is compared only with runs, a
        submission only with submissions; one still being judged (or only saved) isn't compared yet."""
        targets = [x for x in subs if x.user_id == self.user.id and x.status.is_terminal]
        if not targets:
            return {}
        rows = list(
            self.db.scalars(
                select(Submission)
                .where(
                    Submission.user_id == self.user.id,
                    Submission.problem_id.in_({x.problem_id for x in targets}),
                )
                .order_by(Submission.created_at, Submission.id)
            ).all()
        )
        previous: dict[str, Submission] = {}
        for t in targets:
            earlier = [
                r
                for r in rows
                if r.problem_id == t.problem_id
                and r.mode == t.mode
                and r.status in VERDICTS
                and (r.created_at, r.id) < (t.created_at, t.id)
            ]
            if earlier:
                previous[t.id] = earlier[-1]
        if not previous:
            return {}
        facts = self.submission_facts({*targets, *previous.values()})
        return {
            t.id: (previous[t.id], classify(facts[previous[t.id].id], facts[t.id]))
            for t in targets
            if t.id in previous
        }
