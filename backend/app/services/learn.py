"""Learn mode: serving units and recording what the learner actually did.

- Content comes from `app.learn` (authored in the repository); no model is called here.
- Progress events are kept per unit version. "started" and "read" are recorded when the learner
  opens and finishes reading a unit; they are never treated as mastery.
- The comprehension check is graded here against answers the browser never sees beforehand.
  `check_passed` follows the unit's rule (every answer right) on the current version.
- "practiced" is derived, not clicked: an answer to the linked question, or a submission to the
  linked problem, made after the learner started the unit. It never marks a problem solved or a
  skill validated; those still come only from scored answers and the judge.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.eligibility import feedback_eligibility
from app.careers.questions import get_question
from app.errors import ConflictError, NotFoundError
from app.learn import PASS_RULE, UNIT_INDEX, Unit, get_unit, tracks_with_units, units_for
from app.models import LearnEvent, PracticeAnswer, Problem, Submission, SubmissionMode, User
from app.schemas.learn import (
    CareerCoverage,
    CheckIn,
    CheckItemResult,
    CheckQuestionOut,
    CheckResult,
    EventOut,
    ExampleOut,
    ExerciseOut,
    LearnCatalog,
    NextAction,
    PracticeOut,
    ReferenceOut,
    ReviewOut,
    UnitLink,
    UnitOut,
    UnitProgress,
    UnitSummary,
)

ONCE_PER_VERSION = ("started", "read", "check_passed", "practiced")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def find_unit(unit_id: str) -> Unit:
    u = get_unit(unit_id)
    if u is None:
        raise NotFoundError("Learning unit not found")
    return u


def practice_href(u: Unit) -> str:
    p = u.practice
    return f"/problems/{p.ref_id}" if p.kind == "problem" else f"/careers/{u.track}/questions/{p.ref_id}"


def summary(u: Unit) -> UnitSummary:
    return UnitSummary(
        id=u.id,
        track=u.track,
        title=u.title,
        skill=u.skill,
        topics=list(u.topics),
        minutes=u.minutes,
        objective=u.objective,
        prerequisites=[UnitLink(id=p, title=find_unit(p).title) for p in u.prerequisites],
        version=u.version,
        review_status=u.review.status,
        regulated=u.scope_note is not None,
    )


def unit_out(u: Unit) -> UnitOut:
    e = u.exercise
    return UnitOut(
        **summary(u).model_dump(),
        career_title=CATALOG[u.track].title,
        changes=list(u.changes),
        scope_note=u.scope_note,
        explanation=list(u.explanation),
        example=ExampleOut(
            title=u.example.title,
            intro=u.example.intro,
            code=u.example.code,
            language=u.example.language,
            walkthrough=list(u.example.walkthrough),
        ),
        mistakes=list(u.mistakes),
        exercise=ExerciseOut(
            prompt=e.prompt,
            draft_label=e.draft_label,
            guided_steps=[e.think, e.concept, e.example, e.explanation],
            solution=e.solution,
            solution_language=e.solution_language,
        ),
        check=[CheckQuestionOut(id=c.id, prompt=c.prompt, options=list(c.options)) for c in u.check],
        pass_rule=PASS_RULE,
        practice=PracticeOut(
            kind=u.practice.kind, ref_id=u.practice.ref_id, label=u.practice.label, href=practice_href(u)
        ),
        references=[
            ReferenceOut(
                title=r.title,
                publisher=r.publisher,
                url=r.url,
                published=r.published,
                kind=r.kind,
                note=r.note,
            )
            for r in u.references
        ],
        review=ReviewOut(status=u.review.status, by=u.review.by, on=u.review.on, note=u.review.note),
        question_ids=list(u.question_ids),
    )


def catalog(track: str) -> LearnCatalog:
    if track not in CATALOG:
        raise NotFoundError(f"Career '{track}' not found")
    units = units_for(track)
    covered = [
        CareerCoverage(track=t, title=CATALOG[t].title, units=len(units_for(t))) for t in tracks_with_units()
    ]
    names = " and ".join(f"{c.title} ({c.units})" for c in covered)
    note = (
        f"Learn mode is new and deliberately small: units exist for {names}. "
        + ("" if units else f"{CATALOG[track].title} doesn't have any yet.")
    ).strip()
    return LearnCatalog(
        track=track,
        career_title=CATALOG[track].title,
        units=[summary(u) for u in units],
        coverage_note=note,
        careers_with_units=covered,
    )


class Learn:
    def __init__(self, db: Session):
        self.db = db

    def _events(self, user: User, unit_id: str) -> list[LearnEvent]:
        return list(
            self.db.scalars(
                select(LearnEvent)
                .where(LearnEvent.user_id == user.id, LearnEvent.unit_id == unit_id)
                .order_by(LearnEvent.created_at, LearnEvent.id)
            ).all()
        )

    def _record(self, user: User, u: Unit, kind: str, version: int, detail: dict | None = None) -> None:
        key = f"{u.id}:{version}:{kind}" if kind in ONCE_PER_VERSION else None
        if key and self.db.scalar(
            select(LearnEvent.id).where(LearnEvent.user_id == user.id, LearnEvent.dedupe_key == key)
        ):
            return
        self.db.add(
            LearnEvent(
                user_id=user.id, unit_id=u.id, unit_version=version, kind=kind, detail=detail, dedupe_key=key
            )
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()  # a concurrent request recorded the same once-per-version event

    def _practice_evidence(self, user: User, u: Unit, since: datetime) -> dict | None:
        p = u.practice
        if p.kind == "question":
            a = self.db.scalar(
                select(PracticeAnswer)
                .where(
                    PracticeAnswer.user_id == user.id,
                    PracticeAnswer.track == u.track,
                    PracticeAnswer.question_id == p.ref_id,
                    PracticeAnswer.created_at >= since,
                )
                .order_by(PracticeAnswer.created_at)
                .limit(1)
            )
            if a is None:
                return None
            scored = feedback_eligibility(a.feedback) != "too_short"
            return {
                "answer_id": a.id,
                "label": f"answered, scored {a.score}/100" if scored else "answered (too short to score)",
            }
        row = self.db.execute(
            select(Submission.id)
            .join(Problem, Problem.id == Submission.problem_id)
            .where(
                Submission.user_id == user.id,
                Problem.slug == p.ref_id,
                Submission.mode == SubmissionMode.SUBMIT,
                Submission.created_at >= since,
            )
            .order_by(Submission.created_at)
            .limit(1)
        ).first()
        return {"submission_id": row[0], "label": "submitted an attempt"} if row else None

    def progress(self, user: User, unit_id: str) -> UnitProgress:
        u = find_unit(unit_id)
        events = self._events(user, u.id)
        started = [e for e in events if e.kind == "started"]
        if started and not any(e.kind == "practiced" for e in events):
            found = self._practice_evidence(user, u, _aware(started[0].created_at))
            if found:
                version = max(e.unit_version for e in started)
                self._record(user, u, "practiced", version, found)
                events = self._events(user, u.id)
        return self._progress_out(u, events)

    def _progress_out(self, u: Unit, events: list[LearnEvent]) -> UnitProgress:
        cur = [e for e in events if e.unit_version == u.version]
        practiced = next((e for e in events if e.kind == "practiced"), None)
        read = any(e.kind == "read" for e in cur)
        passed = any(e.kind == "check_passed" for e in cur)
        if not read and not passed:
            nxt = NextAction(kind="read", label="Read the unit, then mark it read")
        elif not passed:
            nxt = NextAction(kind="check", label="Take the comprehension check")
        elif practiced is None:
            nxt = NextAction(kind="practice", label=u.practice.label)
        else:
            nxt = NextAction(kind="done", label="Done. Try another unit or keep practising")
        return UnitProgress(
            unit_id=u.id,
            current_version=u.version,
            versions_used=sorted({e.unit_version for e in events}),
            started=any(e.kind == "started" for e in events),
            read=read,
            check_attempts=sum(1 for e in cur if e.kind == "check_attempted"),
            check_passed=passed,
            passed_versions=sorted({e.unit_version for e in events if e.kind == "check_passed"}),
            practiced=practiced is not None,
            practiced_evidence=(practiced.detail or {}).get("label") if practiced else None,
            events=[
                EventOut(
                    kind=e.kind,
                    version=e.unit_version,
                    at=e.created_at,
                    detail=(e.detail or {}).get("label"),
                )
                for e in events
            ],
            next_action=nxt,
        )

    def _current(self, u: Unit, version: int) -> None:
        if version != u.version:
            raise ConflictError(
                f"This unit was updated to version {u.version}. Reload to see the changes.",
                code="unit_changed",
                details={"current_version": u.version},
            )

    def record(self, user: User, unit_id: str, kind: str, version: int) -> UnitProgress:
        u = find_unit(unit_id)
        self._current(u, version)
        if kind == "read":
            self._record(user, u, "started", version)  # reading implies it was opened
        self._record(user, u, kind, version)
        return self.progress(user, u.id)

    def check(self, user: User, unit_id: str, body: CheckIn) -> CheckResult:
        u = find_unit(unit_id)
        self._current(u, body.version)
        results = []
        for c in u.check:
            chosen = body.answers.get(c.id)
            ok = chosen == c.answer
            results.append(
                CheckItemResult(
                    id=c.id, chosen=chosen, correct=ok, answer=c.answer, explanation=c.explanation
                )
            )
        correct = sum(r.correct for r in results)
        passed = correct == len(u.check)
        self._record(user, u, "started", u.version)
        self._record(
            user,
            u,
            "check_attempted",
            u.version,
            {"label": f"{correct} of {len(u.check)} right", "correct": correct},
        )
        if passed:
            self._record(user, u, "check_passed", u.version, {"label": "every answer right"})
        return CheckResult(
            passed=passed,
            correct=correct,
            total=len(u.check),
            pass_rule=PASS_RULE,
            results=results,
            progress=self.progress(user, u.id),
        )

    def statuses(self, user: User, track: str) -> dict[str, UnitProgress]:
        return {u.id: self.progress(user, u.id) for u in units_for(track)}

    def passed_units(self, user: User) -> set[str]:
        """Units whose check this learner passed on any version (the plan's evidence)."""
        return set(
            self.db.scalars(
                select(LearnEvent.unit_id).where(
                    LearnEvent.user_id == user.id, LearnEvent.kind == "check_passed"
                )
            ).all()
        )


def related(
    db: Session, *, track: str | None, question_id: str | None, problem_slug: str | None
) -> list[UnitLink]:
    """Units that prepare for a question (linked explicitly or through its practice action) or a
    coding problem (its practice action or a shared topic)."""
    out: list[Unit] = []
    if track and question_id and get_question(track, question_id) is not None:
        out = [
            u
            for u in units_for(track)
            if question_id in u.question_ids
            or (u.practice.kind == "question" and u.practice.ref_id == question_id)
        ]
    elif problem_slug:
        topics = set(db.scalar(select(Problem.topics).where(Problem.slug == problem_slug)) or [])
        out = [
            u
            for u in UNIT_INDEX.values()
            if (u.practice.kind == "problem" and u.practice.ref_id == problem_slug) or topics & set(u.topics)
        ]
    return [UnitLink(id=u.id, title=u.title) for u in out]
