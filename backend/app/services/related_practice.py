"""Practice related to an accepted improvement (Volume 13, prompt 4; docs/ACCEPTED_ACTIONS.md).

Found only through stored links, never by wording:

- retries of the question the improvement came from, in its source interview (`interview_retries`
  for that session and question index);
- follow-ups to that question: answers whose `follows_up_answer_id` is the original answer or one of
  its retries.

Only attempts made since the improvement was accepted count. Each is shown with its own score (or
"too short to score"), its conditions and the comparison rule's verdict against the attempt the
improvement came from; nothing is averaged, nothing says it worked, and none of it marks the
action done or touches its schedule. Read live each time, so a deleted answer simply drops out.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers.comparability import classify
from app.careers.eligibility import feedback_eligibility
from app.careers.questions import get_question
from app.models import (
    AcceptedAction,
    InterviewRetry,
    InterviewTurn,
    PracticeAnswer,
    PracticeSession,
    Submission,
    SubmissionMode,
    TurnRole,
    User,
)
from app.schemas.actions import RelatedAttempt, RelatedOrigin, RelatedPractice, RelatedSubmission
from app.services.attempt_comparisons import VERDICTS, AttemptComparisons, compared_view, comparison_out
from app.services.conditions import Conditions

_RETRY = re.compile(r"^/interviews/([^/]+)/retry/(\d+)$")
NOTE = (
    "Practice linked to this improvement since you accepted it, found by stored links only: retries of the "
    "question it came from, and follow-ups to it. Each keeps its own score. Whether it helped isn't judged, "
    "and marking the improvement done is yours."
)
UNLINKED = "This kind of improvement has no practice linked to it yet: mark it done when you've done it."
CODE_NOTE = (
    "Submissions of the interview's problem since you accepted this, found by a stored link (the interview "
    "names its problem). Each keeps its own verdict, compared with the submission before it. Whether it "
    "helped isn't judged, and marking the improvement done is yours."
)
FOLLOW_UP_NOTE = (
    "A different question about the same thing: not a retry, so its score isn't set beside the original's."
)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _title(track: str, qid: str) -> str:
    q = get_question(track, qid)
    return q.title if q else "A question no longer in the bank"


class RelatedPracticeFinder:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def related(
        self, row: AcceptedAction
    ) -> tuple[PracticeAnswer | None, list[tuple[str, PracticeAnswer]]] | None:
        """(the attempt it came from, [(kind, answer)] oldest first), or None when the improvement
        has no practice link (its practice isn't a retry of one question)."""
        m = _RETRY.match(row.practice_href or "")
        if m is None:
            return None
        session_id, index = m.group(1), int(m.group(2))
        origin_id = self.db.scalar(
            select(InterviewTurn.answer_id)
            .join(PracticeSession, PracticeSession.id == InterviewTurn.session_id)
            .where(
                PracticeSession.id == session_id,
                PracticeSession.user_id == self.user.id,
                InterviewTurn.role == TurnRole.CANDIDATE,
                InterviewTurn.question_index == index,
            )
        )
        retries = self.db.execute(
            select(InterviewRetry.retry_answer_id, InterviewRetry.created_at).where(
                InterviewRetry.user_id == self.user.id,
                InterviewRetry.session_id == session_id,
                InterviewRetry.question_index == index,
            )
        ).all()
        since = _aware(row.created_at)
        parents = {a for a in [origin_id, *(r for r, _ in retries)] if a}
        follow_ids = (
            set(
                self.db.scalars(
                    select(PracticeAnswer.id).where(
                        PracticeAnswer.user_id == self.user.id,
                        PracticeAnswer.follows_up_answer_id.in_(parents),
                    )
                ).all()
            )
            if parents
            else set()
        )
        retry_ids = {r for r, at in retries}
        wanted = {*retry_ids, *follow_ids, *([origin_id] if origin_id else [])}
        rows = {
            a.id: a
            for a in self.db.scalars(
                select(PracticeAnswer).where(
                    PracticeAnswer.user_id == self.user.id, PracticeAnswer.id.in_(wanted)
                )
            ).all()
        }
        origin = rows.get(origin_id) if origin_id else None
        found = [
            ("retry" if a.id in retry_ids else "follow_up", a)
            for a in rows.values()
            if a.id != origin_id and _aware(a.created_at) >= since
        ]
        found.sort(key=lambda x: (_aware(x[1].created_at), x[1].id))
        return origin, found

    def coding_problem(self, row: AcceptedAction) -> int | None:
        """The problem of the coding interview the improvement came from (a stored link), if it came
        from one."""
        if row.source_kind != "interview_improvement":
            return None
        return self.db.scalar(
            select(PracticeSession.problem_id).where(
                PracticeSession.id == row.source_id, PracticeSession.user_id == self.user.id
            )
        )

    def related_submissions(self, row: AcceptedAction) -> list[Submission] | None:
        """Judged submissions (not runs) of that problem since the improvement was accepted, oldest
        first; None when the improvement didn't come from a coding interview."""
        problem_id = self.coding_problem(row)
        if problem_id is None:
            return None
        since = _aware(row.created_at)
        rows = self.db.scalars(
            select(Submission)
            .where(
                Submission.user_id == self.user.id,
                Submission.problem_id == problem_id,
                Submission.mode == SubmissionMode.SUBMIT,
                Submission.status.in_(VERDICTS),
            )
            .order_by(Submission.created_at, Submission.id)
        ).all()
        return [s for s in rows if _aware(s.created_at) >= since]

    def _code_practice(self, row: AcceptedAction, subs: list[Submission], disputed) -> RelatedPractice:
        from app.services.judge.views import public_result_view

        pairs = AttemptComparisons(self.db, self.user).submissions_with_previous(subs)
        help = Conditions(self.db, self.user).for_submissions(subs)
        items = []
        for s in subs:
            r = public_result_view(s)
            pair = pairs.get(s.id)
            items.append(
                RelatedSubmission(
                    submission_id=s.id,
                    problem_slug=s.problem.slug,
                    problem_title=s.problem.title,
                    created_at=s.created_at,
                    status=s.status,
                    passed_count=r.passed_count if r else None,
                    total_count=r.total_count if r else None,
                    hidden_passed=r.hidden_passed if r else None,
                    hidden_total=r.hidden_total if r else None,
                    conditions=help.get(s.id),
                    compared=compared_view(*pair) if pair else None,
                    href=f"/history/submissions/{s.id}",
                )
            )
        return RelatedPractice(
            action_id=row.id,
            count=len(items),
            items=[],
            submissions=items,
            origin=None,
            linked=True,
            note=CODE_NOTE,
            disputed=disputed,
        )

    def for_action(self, row: AcceptedAction, disputed=None) -> RelatedPractice:
        rel = self.related(row)
        if rel is None and (subs := self.related_submissions(row)) is not None:
            return self._code_practice(row, subs, disputed)
        if rel is None:
            return RelatedPractice(
                action_id=row.id,
                count=0,
                items=[],
                origin=None,
                linked=False,
                note=UNLINKED,
                disputed=disputed,
            )
        origin, found = rel
        comparisons = AttemptComparisons(self.db, self.user)
        facts = comparisons.facts([*([origin] if origin else []), *(a for _, a in found)])
        items = []
        for kind, a in found:
            scoring = feedback_eligibility(a.feedback)
            items.append(
                RelatedAttempt(
                    answer_id=a.id,
                    kind=kind,
                    question_id=a.question_id,
                    question_title=_title(a.track, a.question_id),
                    created_at=a.created_at,
                    score=a.score if scoring == "scored" else None,
                    scoring=scoring,
                    conditions=comparisons.conditions.get(a.id),
                    comparison=comparison_out(origin.id, classify(facts[origin.id], facts[a.id]))
                    if origin
                    else None,
                    note=FOLLOW_UP_NOTE if kind == "follow_up" else None,
                    href=f"/careers/{a.track}/questions/{a.question_id}?answer={a.id}",
                )
            )
        origin_out = None
        if origin is not None:
            s = feedback_eligibility(origin.feedback)
            origin_out = RelatedOrigin(
                answer_id=origin.id,
                question_title=_title(origin.track, origin.question_id),
                score=origin.score if s == "scored" else None,
                scoring=s,
            )
        return RelatedPractice(
            action_id=row.id,
            count=len(items),
            items=items,
            origin=origin_out,
            linked=True,
            note=NOTE,
            disputed=disputed,
        )
