"""Offering a reviewed follow-up problem (Volume 14, prompt 10; docs/FOLLOW_UPS.md, "Coding problems").

Only this account's submissions decide what it's offered: a follow-up is offered after a judged
submission of the problem passed (a run never counts), only for a reviewed pair
(app/content/problem_followups.py), never for a retired problem, and only while the learner hasn't
attempted the second problem at all ("Not previously attempted in this app"). Dismissing it is kept
with the account, so it stays dismissed on every device. A submission made from the offer records
the passed one it followed, once; its verdict is its own and is never set beside the first.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.content.problem_followups import follow_up_between, follow_ups_from
from app.errors import AppError, NotFoundError
from app.models import OnboardingState, Problem, Submission, SubmissionMode, SubmissionStatus, User
from app.schemas.problem_followups import (
    FollowUpOf,
    ProblemFollowUpDone,
    ProblemFollowUpOffer,
    ProblemFollowUpsOut,
)
from app.services.content import is_problem_retired
from app.services.followups import NOT_ATTEMPTED

NOT_COMBINED = "Its own verdict, not combined with this problem's or compared with it."


def dismissal_key(from_slug: str, to_slug: str) -> str:
    return f"problem-follow-up:{from_slug}>{to_slug}"


class ProblemFollowUps:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _problem(self, slug: str) -> Problem:
        p = self.db.scalar(select(Problem).where(Problem.slug == slug))
        if p is None:
            raise NotFoundError(f"Problem '{slug}' not found")
        return p

    def _passed(self, problem: Problem) -> Submission | None:
        """This account's latest judged submission of the problem that passed (a run doesn't count)."""
        return self.db.scalar(
            select(Submission)
            .where(
                Submission.user_id == self.user.id,
                Submission.problem_id == problem.id,
                Submission.mode == SubmissionMode.SUBMIT,
                Submission.status == SubmissionStatus.PASSED,
            )
            .order_by(Submission.created_at.desc())
            .limit(1)
        )

    def _attempted(self, problem_id: int) -> bool:
        return (
            self.db.scalar(
                select(Submission.id)
                .where(Submission.user_id == self.user.id, Submission.problem_id == problem_id)
                .limit(1)
            )
            is not None
        )

    def _dismissed(self) -> set[str]:
        row = self.db.get(OnboardingState, self.user.id)
        return set(row.dismissed or []) if row else set()

    def offer(self, slug: str) -> ProblemFollowUpsOut:
        problem = self._problem(slug)
        pairs = follow_ups_from(slug)
        answered = self._answered(problem)
        if not pairs:
            return ProblemFollowUpsOut(
                status="none",
                message="No reviewed related problem is linked to this one yet.",
                offers=[],
                answered=answered,
            )
        passed = self._passed(problem)
        if passed is None:
            return ProblemFollowUpsOut(
                status="not_yet",
                message="After a judged submission of this problem passes, a different, related problem may be "
                "offered here.",
                offers=[],
                answered=answered,
            )
        dismissed = self._dismissed()
        offers: list[ProblemFollowUpOffer] = []
        for pair in pairs:
            to = self.db.scalar(select(Problem).where(Problem.slug == pair.to_slug))
            if to is None or is_problem_retired(to.slug):
                continue
            if dismissal_key(slug, to.slug) in dismissed or self._attempted(to.id):
                continue  # dismissed, or not fresh: never offered again
            offers.append(
                ProblemFollowUpOffer(
                    slug=to.slug,
                    title=to.title,
                    difficulty=to.difficulty.value if hasattr(to.difficulty, "value") else str(to.difficulty),
                    shares=pair.shares,
                    difference=pair.difference,
                    exposure=NOT_ATTEMPTED,
                    from_submission_id=passed.id,
                )
            )
        if not offers:
            return ProblemFollowUpsOut(
                status="done",
                message="The related problems for this one were attempted or dismissed.",
                offers=[],
                answered=answered,
            )
        return ProblemFollowUpsOut(
            status="offered",
            message="An optional, different problem that shares one idea with this one. Its verdict will be its own: "
            "it isn't combined with this one's, and passing it doesn't by itself show that anything was learned.",
            offers=offers,
            answered=answered,
        )

    def _answered(self, problem: Problem) -> list[ProblemFollowUpDone]:
        mine = select(Submission.id).where(
            Submission.user_id == self.user.id, Submission.problem_id == problem.id
        )
        rows = self.db.scalars(
            select(Submission)
            .options(selectinload(Submission.problem), selectinload(Submission.result))
            .where(Submission.user_id == self.user.id, Submission.follows_up_submission_id.in_(mine))
            .order_by(Submission.created_at)
        ).all()
        out = []
        for s in rows:
            r = s.result
            out.append(
                ProblemFollowUpDone(
                    submission_id=s.id,
                    slug=s.problem.slug,
                    title=s.problem.title,
                    status=s.status,
                    passed_count=getattr(r, "passed_count", None) if r else None,
                    total_count=getattr(r, "total_count", None) if r else None,
                    created_at=s.created_at,
                    follows_up_submission_id=s.follows_up_submission_id or "",
                )
            )
        return out

    def dismiss(self, slug: str, to_slug: str) -> ProblemFollowUpsOut:
        if follow_up_between(slug, to_slug) is None:
            raise NotFoundError("No reviewed follow-up links these problems")
        row = self.db.get(OnboardingState, self.user.id)
        if row is None:
            row = OnboardingState(user_id=self.user.id, dismissed=[])
            self.db.add(row)
        key = dismissal_key(slug, to_slug)
        if key not in (row.dismissed or []):
            row.dismissed = [*(row.dismissed or []), key]
            row.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.offer(slug)

    def check_link(self, problem: Problem, follows_up_id: str | None) -> str | None:
        """The passed submission a follow-up names: this account's own, of a problem with a reviewed
        pair to this one. Another account's is 404, like one that doesn't exist."""
        if follows_up_id is None:
            return None
        parent = self.db.get(Submission, follows_up_id)
        if parent is None or parent.user_id != self.user.id:
            raise NotFoundError("That earlier submission wasn't found.")
        if parent.mode != SubmissionMode.SUBMIT or parent.status != SubmissionStatus.PASSED:
            raise AppError("A follow-up comes after a judged submission that passed.", code="not_a_follow_up")
        first = self.db.get(Problem, parent.problem_id)
        if first is None or follow_up_between(first.slug, problem.slug) is None:
            raise AppError("That submission isn't of a problem this one follows up.", code="not_a_follow_up")
        return parent.id


def follow_up_of(db: Session, sub: Submission) -> FollowUpOf | None:
    if not sub.follows_up_submission_id:
        return None
    parent = db.get(Submission, sub.follows_up_submission_id)
    if parent is None or parent.user_id != sub.user_id:
        return None
    first = db.get(Problem, parent.problem_id)
    if first is None:
        return None
    return FollowUpOf(
        submission_id=parent.id,
        problem_slug=first.slug,
        problem_title=first.title,
        status=parent.status,
        text=f"A follow-up to {first.title}, a different problem. {NOT_COMBINED.replace('this problem', 'that problem')}",
    )
