"""Progress analytics and personalized recommendations.

Everything is computed from facts already stored (submissions, progress events, AI usage),
so there is no separate counter table that could drift out of sync.

Recommendation strategy (explainable on purpose, so every suggestion carries a reason):
1. Unfinished business: problems attempted but not solved, most recent first.
2. Weak topics: topics with the lowest solve ratio, weighted by how many hints were needed.
3. Difficulty ladder: don't suggest a medium problem in a topic until an easy one in that
   topic is solved, unless the learner has nothing easier left.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AIAction,
    AIInteraction,
    Difficulty,
    Problem,
    ProgressEvent,
    Submission,
    SubmissionStatus,
    User,
)
from app.schemas.progress import (
    ActivityDay,
    DifficultyProgress,
    ProblemStatus,
    ProgressOut,
    Recommendation,
    TopicProgress,
)

_DIFFICULTY_RANK = {Difficulty.EASY: 0, Difficulty.MEDIUM: 1, Difficulty.HARD: 2}


@dataclass
class _ProblemFacts:
    problem: Problem
    submissions: int = 0
    solved: bool = False
    last_status: SubmissionStatus | None = None
    last_activity: datetime | None = None
    hints: int = 0
    reviews: int = 0
    opened: bool = False

    @property
    def attempted(self) -> bool:
        return self.submissions > 0

    @property
    def status(self) -> str:
        if self.solved:
            return "solved"
        if self.attempted:
            return "attempted"
        return "in_progress" if (self.opened or self.hints or self.reviews) else "not_started"


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def _topic_label(topic: str) -> str:
    return topic.replace("-", " ")


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; Postgres returns aware ones. Normalize to UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _streaks(days: set[date], today: date) -> tuple[int, int]:
    if not days:
        return 0, 0
    ordered = sorted(days)
    longest = run = 1
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)
    # The current streak survives until the end of the day after the last active day.
    current = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


class ProgressService:
    def __init__(self, db: Session):
        self.db = db

    def _facts(self, user: User) -> dict[int, _ProblemFacts]:
        problems = self.db.scalars(select(Problem).order_by(Problem.order_index)).all()
        facts = {p.id: _ProblemFacts(problem=p) for p in problems}

        for sub in self.db.scalars(
            select(Submission).where(Submission.user_id == user.id).order_by(Submission.created_at)
        ):
            f = facts.get(sub.problem_id)
            if f is None:
                continue
            f.submissions += 1
            f.last_status = sub.status
            f.last_activity = _aware(sub.created_at)
            if sub.status == SubmissionStatus.PASSED:
                f.solved = True

        for ai in self.db.scalars(select(AIInteraction).where(AIInteraction.user_id == user.id)):
            f = facts.get(ai.problem_id)
            if f is None:
                continue
            if ai.action == AIAction.HINT:
                f.hints += 1
            elif ai.action == AIAction.REVIEW:
                f.reviews += 1
            ts = _aware(ai.created_at)
            f.last_activity = max(f.last_activity or ts, ts)

        for ev in self.db.scalars(select(ProgressEvent).where(ProgressEvent.user_id == user.id)):
            f = facts.get(ev.problem_id)
            if f is not None:
                f.opened = True
        return facts

    def progress(self, user: User, *, now: datetime | None = None) -> ProgressOut:
        now = now or datetime.now(UTC)
        facts = self._facts(user)
        values = list(facts.values())

        topic_rows: dict[str, TopicProgress] = {}
        for f in values:
            for topic in f.problem.topics:
                row = topic_rows.setdefault(
                    topic, TopicProgress(topic=topic, total_problems=0, attempted=0, solved=0)
                )
                row.total_problems += 1
                row.attempted += int(f.attempted)
                row.solved += int(f.solved)

        diff_rows = []
        for d in Difficulty:
            subset = [f for f in values if f.problem.difficulty == d]
            if subset:
                diff_rows.append(
                    DifficultyProgress(
                        difficulty=d.value, total_problems=len(subset), solved=sum(f.solved for f in subset)
                    )
                )

        events = self.db.scalars(
            select(ProgressEvent.created_at).where(ProgressEvent.user_id == user.id)
        ).all()
        stamps = [_aware(t) for t in events]
        per_day = Counter(t.date() for t in stamps)
        current_streak, longest_streak = _streaks(set(per_day), now.date())
        window_start = now.date() - timedelta(days=27)
        activity = [
            ActivityDay(
                day=window_start + timedelta(days=i), events=per_day.get(window_start + timedelta(days=i), 0)
            )
            for i in range(28)
        ]

        submissions = sum(f.submissions for f in values)
        status_counts = dict(
            self.db.execute(
                select(Submission.status, func.count())
                .where(Submission.user_id == user.id)
                .group_by(Submission.status)
            ).all()
        )
        accepted_count = status_counts.get(SubmissionStatus.PASSED, 0)
        judged = sum(n for st, n in status_counts.items() if SubmissionStatus(st).is_terminal)

        weakest = self.weakest_topics(facts)
        return ProgressOut(
            total_problems=len(values),
            attempted=sum(f.attempted for f in values),
            solved=sum(f.solved for f in values),
            submissions=submissions,
            accepted_submissions=accepted_count,
            acceptance_rate=round(accepted_count / judged, 3) if judged else None,
            hints_used=sum(f.hints for f in values),
            reviews_requested=sum(f.reviews for f in values),
            current_streak_days=current_streak,
            longest_streak_days=longest_streak,
            last_active_at=max(stamps) if stamps else None,
            by_topic=sorted(topic_rows.values(), key=lambda r: r.topic),
            by_difficulty=diff_rows,
            problems=[
                ProblemStatus(
                    slug=f.problem.slug,
                    status=f.status,
                    last_submission_status=f.last_status,
                    submissions=f.submissions,
                    hints_used=f.hints,
                )
                for f in values
            ],
            activity=activity,
            weakest_topics=weakest,
            recommended_next=[r.slug for r in self.recommend(user, limit=3, facts=facts)],
        )

    @staticmethod
    def weakest_topics(facts: dict[int, _ProblemFacts], limit: int = 3) -> list[str]:
        """Topics the learner has touched, ranked by (solve ratio asc, hints per problem desc)."""
        touched: dict[str, list[_ProblemFacts]] = defaultdict(list)
        for f in facts.values():
            if f.attempted or f.hints or f.reviews:
                for t in f.problem.topics:
                    touched[t].append(f)

        def score(item: tuple[str, list[_ProblemFacts]]) -> tuple[float, float, str]:
            topic, rows = item
            solve_ratio = sum(r.solved for r in rows) / len(rows)
            hints_per = sum(r.hints for r in rows) / len(rows)
            return (solve_ratio, -hints_per, topic)

        return [
            t
            for t, rows in sorted(touched.items(), key=score)
            if not all(r.solved for r in rows) or sum(r.hints for r in rows) > 0
        ][:limit]

    def recommend(
        self, user: User, *, limit: int = 5, facts: dict[int, _ProblemFacts] | None = None
    ) -> list[Recommendation]:
        facts = facts if facts is not None else self._facts(user)
        values = list(facts.values())
        picks: list[Recommendation] = []
        chosen: set[str] = set()

        def add(f: _ProblemFacts, reason: str, kind: str) -> None:
            if f.problem.slug not in chosen and len(picks) < limit:
                chosen.add(f.problem.slug)
                picks.append(
                    Recommendation(
                        slug=f.problem.slug,
                        title=f.problem.title,
                        difficulty=f.problem.difficulty,
                        topics=f.problem.topics,
                        reason=reason,
                        kind=kind,
                    )
                )

        # 1. Unfinished business, most recent first.
        unfinished = [f for f in values if f.attempted and not f.solved]
        for f in sorted(
            unfinished, key=lambda f: f.last_activity or datetime.min.replace(tzinfo=UTC), reverse=True
        ):
            add(
                f,
                f"You've submitted this {_times(f.submissions)} without a pass. Finish it while it's fresh.",
                "retry",
            )

        # 2. Weak topics: easiest unsolved problem in each.
        solved_easy_topics = {
            t
            for f in values
            if f.solved and f.problem.difficulty == Difficulty.EASY
            for t in f.problem.topics
        }
        for topic in self.weakest_topics(facts, limit=5):
            candidates = sorted(
                (f for f in values if topic in f.problem.topics and not f.solved and not f.attempted),
                key=lambda f: (_DIFFICULTY_RANK[f.problem.difficulty], f.problem.order_index),
            )
            for f in candidates[:1]:
                add(f, f"Builds your weakest area so far: {_topic_label(topic)}.", "weak_topic")

        # 3. Difficulty ladder over everything not yet touched.
        fresh = [f for f in values if not f.solved and not f.attempted]

        def ladder_key(f: _ProblemFacts) -> tuple[int, int, int]:
            locked = int(
                f.problem.difficulty != Difficulty.EASY and not (set(f.problem.topics) & solved_easy_topics)
            )
            return (locked, _DIFFICULTY_RANK[f.problem.difficulty], f.problem.order_index)

        for f in sorted(fresh, key=ladder_key):
            if f.problem.difficulty == Difficulty.EASY:
                reason = f"A solid {' and '.join(_topic_label(t) for t in f.problem.topics[:2])} fundamental."
            elif set(f.problem.topics) & solved_easy_topics:
                reason = "You've solved an easy problem in this area. Ready for a step up."
            else:
                reason = "A stretch problem. Try an easy one in the same topic first if it feels hard."
            add(f, reason, "next_step")
        return picks
