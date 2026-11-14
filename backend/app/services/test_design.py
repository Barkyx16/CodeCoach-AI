"""Test design (docs/TEST_DESIGN.md): learners' cases, queued for the judge like submissions.

A run is checked before anything is queued: every case must fit the exercise's one input shape
and limits, with plain messages for what doesn't. Admission follows the judge's contract: one
account at a time (PostgreSQL), the per-minute limit, one pending run per account, and a full
queue refuses rather than waits. Without a judge on this server the cases are saved as "not run":
nothing is executed, and no result is made up.

A resend with the same request key returns the run it made; the same key with other cases is
refused. Runs are never edited: a revised set of cases is a new run, and earlier ones stay as
they were, with the exercise version they ran against.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError, NotFoundError, RateLimitedError
from app.models import TestDesignRun, User
from app.schemas.test_design import (
    TestDesignExample,
    TestDesignExercise,
    TestDesignLimits,
    TestDesignParam,
    TestDesignRunIn,
    TestDesignRunOut,
    TestDesignRunSummary,
    TestDesignSummary,
    TestDesignVariant,
)
from app.services import request_keys
from app.services.judge.backends import JudgeBusyError, lock_admission
from app.testdesign import BY_SLUG, EXERCISES, Exercise, case_errors, variant_key

PENDING = ("queued", "running")
MAX_RUNS_PER_EXERCISE = 100
NOT_RUN_DETAIL = (
    "Code can't run on this server, so these cases weren't run. They're saved with this exercise version; "
    "nothing was guessed."
)
QUEUED_DETAIL = "Waiting for the judge…"


class CaseErrors(AppError):
    status_code = 422
    code = "invalid_cases"


def _now() -> datetime:
    return datetime.now(UTC)


class TestDesign:
    __test__ = False

    def __init__(self, db: Session, user: User | None = None, settings: Settings | None = None):
        self.db = db
        self.user = user
        self.settings = settings

    # -- the exercises (public) -------------------------------------------------------------

    def _exercise(self, slug: str) -> Exercise:
        ex = BY_SLUG.get(slug)
        if ex is None:
            raise NotFoundError("Test design exercise not found")
        return ex

    def exercises(self) -> list[TestDesignSummary]:
        return [
            TestDesignSummary(slug=e.slug, title=e.title, summary=e.summary, variant_count=len(e.variants))
            for e in EXERCISES
        ]

    def exercise(self, slug: str, execution_enabled: bool) -> TestDesignExercise:
        ex = self._exercise(slug)
        return TestDesignExercise(
            slug=ex.slug,
            version=ex.version,
            title=ex.title,
            summary=ex.summary,
            spec=ex.spec,
            method=ex.signature["method"],
            params=[TestDesignParam.model_validate(p) for p in ex.params],
            returns=ex.returns,
            limits=TestDesignLimits(**ex.limits.__dict__),
            examples=[TestDesignExample.model_validate(e) for e in ex.examples],
            variant_count=len(ex.variants),
            review_status=ex.review_status,
            execution_enabled=execution_enabled,
        )

    def variants(self, slug: str) -> list[TestDesignVariant]:
        """The authored faulty versions and their defects: shown only when the learner asks."""
        ex = self._exercise(slug)
        return [
            TestDesignVariant(key=variant_key(k), title=v.title, defect=v.defect)
            for k, v in enumerate(ex.variants)
        ]

    # -- runs ---------------------------------------------------------------------------------

    @property
    def _me(self) -> User:
        assert self.user is not None
        return self.user

    def _cases(self, ex: Exercise, body: TestDesignRunIn) -> list[dict[str, Any]]:
        if len(body.cases) > ex.limits.max_cases:
            raise CaseErrors(
                f"At most {ex.limits.max_cases} cases at a time. A few well-chosen cases tell you more than many alike.",
                details={"max_cases": ex.limits.max_cases},
            )
        problems = {
            str(i + 1): errs
            for i, c in enumerate(body.cases)
            if (errs := case_errors(ex, c.input, c.expected))
        }
        if problems:
            first = next(iter(problems))
            raise CaseErrors(
                f"Case {first}: {problems[first][0]}" + (" (and other cases)" if len(problems) > 1 else ""),
                details={"cases": problems},
            )
        return [
            {"input": c.input, "expected": c.expected, "label": c.label, "note": c.note.strip()}
            for c in body.cases
        ]

    def find_by_key(self, key: str | None) -> TestDesignRun | None:
        return self._by_key(key) if key and self.user else None

    def _by_key(self, key: str) -> TestDesignRun | None:
        return self.db.scalar(
            select(TestDesignRun).where(
                TestDesignRun.user_id == self._me.id, TestDesignRun.client_request_id == key
            )
        )

    def _replay(self, existing: TestDesignRun, slug: str, cases: list[dict[str, Any]]) -> TestDesignRunOut:
        if (existing.exercise_slug, existing.cases) != (slug, cases):
            raise request_keys.reused("test run")
        return self._out(existing)

    def _admit(self, execution_enabled: bool) -> None:
        assert self.settings is not None
        if execution_enabled:
            lock_admission(self.db, self._me)
        limit = self.settings.submission_rate_limit_per_minute
        recent = self.db.scalars(
            select(TestDesignRun.created_at)
            .where(
                TestDesignRun.user_id == self._me.id,
                TestDesignRun.created_at >= _now() - timedelta(minutes=1),
            )
            .order_by(TestDesignRun.created_at)
        ).all()
        if len(recent) >= limit:
            oldest = recent[-limit]
            oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=UTC)
            raise RateLimitedError.wait(
                "You're running cases very quickly. Wait a moment and try again.",
                (oldest + timedelta(minutes=1) - _now()).total_seconds(),
                limit_per_minute=limit,
            )
        if not execution_enabled:
            return
        pending = self.db.scalar(
            select(TestDesignRun)
            .where(TestDesignRun.user_id == self._me.id, TestDesignRun.status.in_(PENDING))
            .order_by(TestDesignRun.created_at)
            .limit(1)
        )
        if pending is not None:
            raise RateLimitedError(
                "Your previous set of cases is still running.",
                code="test_run_pending",
                details={"pending_run_id": pending.id, "slug": pending.exercise_slug},
            )
        depth = (
            self.db.scalar(
                select(func.count()).select_from(TestDesignRun).where(TestDesignRun.status == "queued")
            )
            or 0
        )
        if depth >= self.settings.max_queue_depth:
            raise JudgeBusyError(
                "The judge's queue is full right now, so these cases weren't run. Nothing was saved."
            )

    def start_run(
        self, slug: str, body: TestDesignRunIn, execution_enabled: bool, trace_id: str | None = None
    ) -> tuple[TestDesignRunOut, bool]:
        ex = self._exercise(slug)
        cases = self._cases(ex, body)
        key = body.client_request_id
        if key and (existing := self._by_key(key)) is not None:
            return self._replay(existing, slug, cases), False
        self._admit(execution_enabled)
        n = (
            self.db.scalar(
                select(func.count())
                .select_from(TestDesignRun)
                .where(TestDesignRun.user_id == self._me.id, TestDesignRun.exercise_slug == slug)
            )
            or 0
        )
        if n >= MAX_RUNS_PER_EXERCISE:
            raise AppError("You've reached the limit of saved runs for this exercise.", code="too_many_runs")
        run = TestDesignRun(
            user_id=self._me.id,
            exercise_slug=slug,
            exercise_version=ex.version,
            cases=cases,
            status="queued" if execution_enabled else "not_run",
            status_detail=QUEUED_DETAIL if execution_enabled else NOT_RUN_DETAIL,
            client_request_id=key,
            trace_id=trace_id,
        )
        self.db.add(run)
        try:
            self.db.commit()
        except IntegrityError:  # two copies of the same request at once: the other one saved it
            self.db.rollback()
            existing = self._by_key(key) if key else None
            if existing is None:
                raise
            return self._replay(existing, slug, cases), False
        return self._out(run), True

    def _out(self, run: TestDesignRun) -> TestDesignRunOut:
        current = BY_SLUG.get(run.exercise_slug)
        return TestDesignRunOut(
            id=run.id,
            slug=run.exercise_slug,
            exercise_version=run.exercise_version,
            current_version=current.version if current else None,
            status=run.status,
            status_detail=run.status_detail,
            cases=run.cases,
            report=run.report,
            created_at=run.created_at,
            judged_at=run.judged_at,
        )

    def runs(self, slug: str) -> list[TestDesignRunSummary]:
        self._exercise(slug)
        rows = self.db.scalars(
            select(TestDesignRun)
            .where(TestDesignRun.user_id == self._me.id, TestDesignRun.exercise_slug == slug)
            .order_by(TestDesignRun.created_at.desc())
        ).all()
        return [
            TestDesignRunSummary(
                id=r.id,
                exercise_version=r.exercise_version,
                status=r.status,
                cases=len(r.cases),
                caught=(r.report or {}).get("caught"),
                total=(r.report or {}).get("total"),
                created_at=r.created_at,
            )
            for r in rows
        ]

    def get_run(self, run_id: str) -> TestDesignRunOut:
        run = self.db.get(TestDesignRun, run_id)
        if run is None or run.user_id != self._me.id:
            raise NotFoundError("Run not found")
        return self._out(run)

    def export(self) -> list[dict[str, Any]]:
        return [
            {
                "exercise": r.exercise_slug,
                "exercise_version": r.exercise_version,
                "status": r.status,
                "cases": r.cases,
                "report": r.report,
                "created_at": r.created_at.isoformat(),
            }
            for r in self.db.scalars(select(TestDesignRun).where(TestDesignRun.user_id == self._me.id))
        ]
