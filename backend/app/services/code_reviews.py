"""Code-review practice (docs/CODE_REVIEW_PRACTICE.md): the learner reviews someone else's code.

Drafts are saved against a revision, like the other long-form editors, with receipts for a save
whose reply was lost. The authored review is sent only after the learner asks for it (`reveal`) or
sends a review (`attempt`); either marks the draft as revealed, and every later attempt says it was
written after seeing the reference. An attempt freezes the code, the authored review and the
comparison, so it reads the same after the exercise is corrected.

Learner text is plain text: control characters are removed and nothing is ever interpreted.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.locking import lock_for_update
from app.errors import AppError, ConflictError, NotFoundError
from app.models import CodeReviewAttempt, CodeReviewDraft, Problem, TestVisibility, User
from app.reviews import BY_SLUG, EXERCISES, Exercise
from app.reviews.feedback import evaluate, words
from app.schemas.code_reviews import (
    FindingIn,
    FindingOut,
    ReviewAttemptIn,
    ReviewAttemptOut,
    ReviewAttemptSummary,
    ReviewDraftIn,
    ReviewDraftOut,
    ReviewExerciseOut,
    ReviewExerciseSummary,
    ReviewPublicTest,
    ReviewReference,
)
from app.schemas.common import SaveReplay
from app.services import update_receipts

MAX_ATTEMPTS_PER_EXERCISE = 50
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(text: str) -> str:
    return _CONTROL.sub("", text).strip()


def excerpt(code: str, start: int, end: int) -> str:
    return "\n".join(code.splitlines()[start - 1 : end])


def _relocate(code: str, text: str) -> tuple[int, int] | None:
    """Where an excerpt is in `code` now (exactly one place, ignoring indentation), or None."""
    want = [line.strip() for line in text.splitlines()]
    have = [line.strip() for line in code.splitlines()]
    if not want or not any(want):
        return None
    hits = [i for i in range(len(have) - len(want) + 1) if have[i : i + len(want)] == want]
    return (hits[0] + 1, hits[0] + len(want)) if len(hits) == 1 else None


def reference_out(snapshot: dict[str, Any]) -> ReviewReference:
    code = snapshot["code"]
    return ReviewReference.model_validate(
        {
            "version": snapshot["version"],
            "findings": [{**r, "excerpt": excerpt(code, *r["lines"])} for r in snapshot["reference"]],
            "repaired_code": snapshot.get("repaired_code"),
            "debrief": snapshot["debrief"],
        }
    )


class CodeReviews:
    def __init__(self, db: Session, user: User | None = None):
        self.db = db
        self.user = user

    # -- the exercises (public) -------------------------------------------------------------

    def _problem(self, ex: Exercise) -> Problem:
        problem = self.db.scalar(select(Problem).where(Problem.slug == ex.problem))
        if problem is None:
            raise NotFoundError("This review exercise isn't available")
        return problem

    def _exercise(self, slug: str) -> Exercise:
        ex = BY_SLUG.get(slug)
        if ex is None:
            raise NotFoundError("Review exercise not found")
        return ex

    def exercises(self) -> list[ReviewExerciseSummary]:
        problems = {
            p.slug: p
            for p in self.db.scalars(select(Problem).where(Problem.slug.in_([e.problem for e in EXERCISES])))
        }
        return [
            ReviewExerciseSummary(
                slug=e.slug,
                title=e.title,
                difficulty=problems[e.problem].difficulty,
                problem_slug=e.problem,
                problem_title=problems[e.problem].title,
            )
            for e in EXERCISES
            if e.problem in problems
        ]

    def exercise(self, slug: str) -> ReviewExerciseOut:
        ex = self._exercise(slug)
        problem = self._problem(ex)
        public = [t for t in problem.test_cases if t.visibility == TestVisibility.PUBLIC]
        return ReviewExerciseOut(
            slug=ex.slug,
            version=ex.version,
            title=ex.title,
            context=ex.context,
            code=ex.code,
            line_count=len(ex.lines),
            problem_slug=problem.slug,
            problem_title=problem.title,
            difficulty=problem.difficulty,
            statement=problem.statement,
            constraints=list(problem.constraints or []),
            public_tests=[
                ReviewPublicTest(position=i, input=t.input, expected_output=t.expected_output)
                for i, t in enumerate(public, 1)
            ],
            review_status=ex.review_status,
        )

    def _snapshot(self, ex: Exercise) -> dict[str, Any]:
        problem = self._problem(ex)
        return ex.snapshot(problem.title, problem.statement)

    # -- the learner's review ---------------------------------------------------------------

    @property
    def _me(self) -> User:
        assert self.user is not None
        return self.user

    def _findings(self, ex: Exercise, findings: list[FindingIn]) -> list[dict[str, Any]]:
        n = len(ex.lines)
        seen: set[str] = set()
        out = []
        for i, f in enumerate(findings, 1):
            if f.end_line > n:
                raise AppError(
                    f"Finding {i} cites line {f.end_line}, but the code has {n} lines.",
                    code="line_out_of_range",
                )
            if f.id in seen:
                raise AppError(f"Finding {i} has the same id as another finding.", code="duplicate_finding")
            seen.add(f.id)
            out.append(
                {
                    "id": f.id,
                    "start_line": f.start_line,
                    "end_line": f.end_line,
                    "excerpt": excerpt(ex.code, f.start_line, f.end_line),
                    "problem": _clean(f.problem),
                    "consequence": _clean(f.consequence),
                    "repair": _clean(f.repair),
                }
            )
        return out

    def draft(self, slug: str) -> ReviewDraftOut:
        ex = self._exercise(slug)
        row = self.db.get(CodeReviewDraft, (self._me.id, slug))
        findings: list[FindingOut] = []
        for f in row.findings if row else []:
            anchor = "same"
            start, end = f["start_line"], f["end_line"]
            if row is not None and row.exercise_version != ex.version:
                # Written against an earlier version: find the cited lines again by their text.
                moved = _relocate(ex.code, f["excerpt"])
                if moved is None:
                    anchor = "missing"
                elif moved != (start, end):
                    anchor, (start, end) = "moved", moved
            findings.append(
                FindingOut.model_validate({**f, "start_line": start, "end_line": end, "anchor": anchor})
            )
        return ReviewDraftOut(
            slug=slug,
            exercise_version=row.exercise_version if row else ex.version,
            current_version=ex.version,
            findings=findings,
            summary=row.summary if row else "",
            revision=row.revision if row else 0,
            revealed=row is not None and row.revealed_version == ex.version,
            updated_at=row.updated_at if row and row.revision else None,
        )

    def save_draft(self, slug: str, body: ReviewDraftIn) -> ReviewDraftOut:
        ex = self._exercise(slug)
        findings = self._findings(ex, body.findings)
        row = lock_for_update(self.db, self.db.get(CodeReviewDraft, (self._me.id, slug)))
        current = row.revision if row else 0
        key = body.client_request_id
        print_ = update_receipts.fingerprint(
            "code_review",
            slug,
            body.expected_revision,
            body.model_dump(mode="json", exclude={"client_request_id", "expected_revision"}),
        )
        if (
            replayed := self._replayed(slug, key, body.expected_revision, print_, row is not None)
        ) is not None:
            return replayed
        if body.expected_revision != current:
            raise ConflictError(
                "This review was saved somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                details={"current_revision": current, "current": self.draft(slug).model_dump(mode="json")},
            )
        if row is None:
            row = CodeReviewDraft(
                user_id=self._me.id, exercise_slug=slug, exercise_version=ex.version, findings=[], revision=0
            )
            self.db.add(row)
        row.findings = findings
        row.summary = _clean(body.summary)
        row.exercise_version = ex.version  # the line numbers were just checked against this version
        row.revision = current + 1
        row.updated_at = datetime.now(UTC)
        update_receipts.record(
            self.db, self._me, key, "code_review", slug, body.expected_revision, row.revision, print_
        )
        try:
            self.db.commit()
        except IntegrityError:  # two first saves at once: the other one created the draft
            self.db.rollback()
            exists = self.db.get(CodeReviewDraft, (self._me.id, slug)) is not None
            if (replayed := self._replayed(slug, key, body.expected_revision, print_, exists)) is not None:
                return replayed
            saved = self.draft(slug)
            raise ConflictError(
                "This review was saved somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                details={"current_revision": saved.revision, "current": saved.model_dump(mode="json")},
            ) from None
        return self.draft(slug)

    def _replayed(
        self, slug: str, key: str | None, base: int, print_: str, exists: bool
    ) -> ReviewDraftOut | None:
        done = update_receipts.find(self.db, self._me, key, "code_review", slug, base, print_)
        if done is None:
            return None
        if not exists:
            raise NotFoundError("That review was saved, then removed. Nothing was saved again.")
        out = self.draft(slug)
        out.save_replay = SaveReplay(accepted_revision=done.accepted_revision, current_revision=out.revision)
        return out

    def _mark_revealed(self, ex: Exercise) -> bool:
        """Record that the authored review for this version has been seen. Returns whether it had
        been seen before."""
        row = self.db.get(CodeReviewDraft, (self._me.id, ex.slug))
        if row is None:
            row = CodeReviewDraft(
                user_id=self._me.id,
                exercise_slug=ex.slug,
                exercise_version=ex.version,
                findings=[],
                summary="",
                revision=0,
                updated_at=datetime.now(UTC),
            )
            self.db.add(row)
        before = row.revealed_version == ex.version
        row.revealed_version = ex.version
        return before

    def reveal(self, slug: str) -> ReviewReference:
        ex = self._exercise(slug)
        snapshot = self._snapshot(ex)
        self._mark_revealed(ex)
        try:
            self.db.commit()
        except IntegrityError:  # a first save made the draft at the same moment: mark that one
            self.db.rollback()
            self._mark_revealed(ex)
            self.db.commit()
        return reference_out(snapshot)

    def attempt(self, slug: str, body: ReviewAttemptIn) -> ReviewAttemptOut:
        ex = self._exercise(slug)
        findings = self._findings(ex, body.findings)
        summary = _clean(body.summary)
        for i, f in enumerate(findings, 1):
            if words(f["problem"]) < 2:
                raise AppError(
                    f"Finding {i} needs a description of the problem (a few words), or remove it.",
                    code="finding_incomplete",
                )
        if not findings and words(summary) < 2:
            raise AppError(
                "Add a finding, or say in the summary why you have none (for example, that the code looks correct).",
                code="review_empty",
            )
        n = (
            self.db.scalar(
                select(func.count())
                .select_from(CodeReviewAttempt)
                .where(CodeReviewAttempt.user_id == self._me.id, CodeReviewAttempt.exercise_slug == slug)
            )
            or 0
        )
        if n >= MAX_ATTEMPTS_PER_EXERCISE:
            raise AppError(
                "You've reached the limit of saved reviews for this exercise.", code="too_many_attempts"
            )
        snapshot = self._snapshot(ex)
        seen = self._mark_revealed(ex)
        a = CodeReviewAttempt(
            user_id=self._me.id,
            exercise_slug=slug,
            exercise_version=ex.version,
            snapshot=snapshot,
            findings=findings,
            summary=summary,
            feedback=evaluate(snapshot, findings),
            after_reveal=seen,
        )
        self.db.add(a)
        self.db.commit()
        return self._out(a)

    def _out(self, a: CodeReviewAttempt) -> ReviewAttemptOut:
        current = BY_SLUG.get(a.exercise_slug)
        return ReviewAttemptOut(
            id=a.id,
            slug=a.exercise_slug,
            exercise_version=a.exercise_version,
            current_version=current.version if current else None,
            title=a.snapshot["title"],
            problem_title=a.snapshot["problem_title"],
            code=a.snapshot["code"],
            findings=[FindingOut.model_validate(f) for f in a.findings],
            summary=a.summary,
            reference=reference_out(a.snapshot),
            feedback=a.feedback,
            after_reveal=a.after_reveal,
            created_at=a.created_at,
        )

    def attempts(self, slug: str) -> list[ReviewAttemptSummary]:
        self._exercise(slug)
        rows = self.db.scalars(
            select(CodeReviewAttempt)
            .where(CodeReviewAttempt.user_id == self._me.id, CodeReviewAttempt.exercise_slug == slug)
            .order_by(CodeReviewAttempt.created_at.desc())
        ).all()
        return [
            ReviewAttemptSummary(
                id=a.id,
                exercise_version=a.exercise_version,
                findings=len(a.findings),
                defects_raised=a.feedback.get("defects_raised", 0),
                defects_total=a.feedback.get("defects_total", 0),
                after_reveal=a.after_reveal,
                created_at=a.created_at,
            )
            for a in rows
        ]

    def get_attempt(self, attempt_id: str) -> ReviewAttemptOut:
        a = self.db.get(CodeReviewAttempt, attempt_id)
        if a is None or a.user_id != self._me.id:
            raise NotFoundError("Review not found")
        return self._out(a)

    def export(self) -> dict[str, Any]:
        me = self._me.id
        return {
            "drafts": [
                {
                    "exercise": d.exercise_slug,
                    "exercise_version": d.exercise_version,
                    "findings": d.findings,
                    "summary": d.summary,
                    "revision": d.revision,
                    "revealed_version": d.revealed_version,
                }
                for d in self.db.scalars(select(CodeReviewDraft).where(CodeReviewDraft.user_id == me))
            ],
            "attempts": [
                {
                    "exercise": a.exercise_slug,
                    "exercise_version": a.exercise_version,
                    "code_reviewed": a.snapshot.get("code"),
                    "findings": a.findings,
                    "summary": a.summary,
                    "feedback": a.feedback,
                    "after_reveal": a.after_reveal,
                    "created_at": a.created_at.isoformat(),
                }
                for a in self.db.scalars(select(CodeReviewAttempt).where(CodeReviewAttempt.user_id == me))
            ],
        }
