"""The facts the comparison contract looks at, gathered from what's recorded, and each attempt's
comparison with the attempt before it (app/careers/comparability.py; docs/COMPARING_ATTEMPTS.md).

Every surface that compares written answers (the question page's tries, an interview retry, the
progress chart's list) gets its classifications here, so the same pair always reads the same. Coding
submissions too (Volume 14, prompt 1): the submission page, the workspace's result and History. And
drills, whiteboard designs and work samples (Volume 15, prompt 4): each attempt's own page and list.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Literal

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
    DrillAttempt,
    InterviewRetry,
    InterviewTurn,
    PracticeAnswer,
    PracticeSession,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    User,
    WhiteboardAttempt,
    WorkSampleAttempt,
)
from app.schemas.careers import AttemptComparison, ComparedAttempt, ComparisonReason, PracticeComparison
from app.schemas.conditions import AttemptConditions
from app.schemas.submission import ComparedSubmission, SubmissionComparison
from app.services.conditions import FORMATS_RECORDED_FROM, RECORDED_FROM, Conditions, problem_versions

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


# Drills, whiteboard designs and work samples: the result is how many of the item's points the
# built-in rules found, as stored with the attempt.
Checklist = Literal["drill", "whiteboard", "work_sample"]
_FOUND: dict[str, str] = {"drill": "there", "whiteboard": "addressed", "work_sample": "covered"}


def checklist_result(kind: Checklist, feedback: dict | None) -> tuple[int, int] | None:
    """(points found, the item's points) as stored, or None when no result was stored."""
    fb = feedback or {}
    if kind == "drill":
        rows = fb.get("observations") or []
        return (sum(1 for o in rows if o.get("present")), len(rows)) if rows else None
    if kind == "whiteboard":
        rows = fb.get("rubric") or []
        return (sum(1 for r in rows if r.get("addressed")), len(rows)) if rows else None
    if fb.get("total"):
        return int(fb.get("covered") or 0), int(fb["total"])
    return None


def checklist_text(kind: Checklist, feedback: dict | None) -> str:
    got = checklist_result(kind, feedback)
    return f"{got[0]} of {got[1]} points {_FOUND[kind]}" if got else "No result stored"


_FIRST = {"drill": "drill", "whiteboard": "prompt", "work_sample": "brief"}


def not_compared(kind: Checklist, row: Any, compared: dict[str, Any]) -> str | None:
    """Why an attempt isn't compared with the one before, in the words its page and History both use
    (Volume 16, prompt 6); None when it is."""
    if row.id in compared:
        return None
    if checklist_result(kind, row.feedback) is None:
        return "Not compared: no result was stored"
    return f"Not compared: the first checked attempt at this {_FIRST[kind]}"


def _item(kind: Checklist, row: Any) -> str:
    return row.drill_id if kind == "drill" else row.prompt_id if kind == "whiteboard" else row.brief_id


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

    # --- drills, whiteboard designs and work samples (Volume 15, prompt 4) -------------------------

    def checklist_facts(self, kind: Checklist, rows: Iterable[Any]) -> dict[str, AttemptFacts]:
        """The facts of drill, whiteboard or work-sample attempts: the item and the version its points
        were checked against, the built-in rules that checked them, whether a result was stored and
        the recorded help. A drill's points are its rubric, versioned together; a whiteboard prompt's
        and a brief's points are the prompt's and the brief's, checked by a versioned set of rules."""
        rows = [r for r in rows if r.user_id == self.user.id]
        if not rows:
            return {}
        finder = Conditions(self.db, self.user)
        help = (
            finder.for_drills(rows)
            if kind == "drill"
            else finder.for_whiteboards(rows)
            if kind == "whiteboard"
            else finder.for_work_samples(rows)
        )
        self.conditions.update(help)
        out: dict[str, AttemptFacts] = {}
        for r in rows:
            fb = r.feedback or {}
            got = checklist_result(kind, fb)
            rubric: str | None
            if kind == "drill":
                track, version, rubric = r.track, r.rubric_version, "the drill's points"
            elif kind == "whiteboard":
                track, version, rubric = "whiteboard", r.prompt_version, f"v{r.rubric_version}"
            else:
                rules = fb.get("rules_version")
                track, version, rubric = "work_sample", r.brief_version, f"v{rules}" if rules else None
            labels = tuple(help[r.id].labels) if r.id in help else None
            out[r.id] = AttemptFacts(
                id=r.id,
                track=track,
                question_id=_item(kind, r),
                question_version=version,
                scale=f"0-{got[1]} points" if got else None,
                rubric=rubric,
                source="rules",
                scoring="scored" if got else "not_judged",
                format="single",
                help=None if labels is None or labels == ("Not recorded",) else labels,
                help_recorded_from=help[r.id].recorded_from if r.id in help else FORMATS_RECORDED_FROM.date(),
                kind=kind,
            )
        return out

    def checklist_pairs(self, kind: Checklist, rows: Iterable[Any]) -> dict[str, tuple[Any, Classification]]:
        """Each assessed attempt among ``rows`` beside the previous assessed attempt at the same item:
        the one it revises when it says so (a work sample's revision), else the one just before it.
        Pass every attempt of this account at the items concerned, so the earlier one is there."""
        rows = [r for r in rows if r.user_id == self.user.id]
        facts = self.checklist_facts(kind, rows)
        by_item: dict[str, list[Any]] = defaultdict(list)
        for r in rows:
            if facts[r.id].scoring == "scored":
                by_item[_item(kind, r)].append(r)
        out: dict[str, tuple[Any, Classification]] = {}
        for group in by_item.values():
            group.sort(key=lambda r: (r.created_at, r.id))
            revises = {r.id: getattr(r, "revision_of", None) for r in group}
            for i, r in enumerate(group):
                j = previous_of(group, i, revises)
                if j is not None:
                    out[r.id] = (group[j], classify(facts[group[j].id], facts[r.id]))
        return out

    def checklist_compared(self, kind: Checklist, rows: Iterable[Any]) -> dict[str, PracticeComparison]:
        """What each attempt's page and list show: both results as given, and the classification."""
        rows = list(rows)
        by_id = {r.id: r for r in rows}
        return {
            aid: PracticeComparison(
                previous=ComparedAttempt(
                    id=prev.id, created_at=prev.created_at, result=checklist_text(kind, prev.feedback)
                ),
                result=checklist_text(kind, by_id[aid].feedback),
                comparison=comparison_out(prev.id, c),
            )
            for aid, (prev, c) in self.checklist_pairs(kind, rows).items()
        }

    def all_attempts(self, kind: Checklist, items: set[str]) -> list[Any]:
        """Every attempt of this account at these items, to find each one's earlier attempt."""
        model: Any = (
            DrillAttempt
            if kind == "drill"
            else WhiteboardAttempt
            if kind == "whiteboard"
            else WorkSampleAttempt
        )
        col = (
            DrillAttempt.drill_id
            if kind == "drill"
            else WhiteboardAttempt.prompt_id
            if kind == "whiteboard"
            else WorkSampleAttempt.brief_id
        )
        if not items:
            return []
        return list(self.db.scalars(select(model).where(model.user_id == self.user.id, col.in_(items))).all())
