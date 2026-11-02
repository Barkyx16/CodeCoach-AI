"""The unified activity feed, career analytics and "continue where you left off".

Activity is *derived* from what is already recorded, never stored twice:

    problem_opened   progress_events (type=opened; recorded at most once per problem per day)
    code_submission  submissions (mode=submit; "run" checks aren't attempts)
    coaching         ai_interactions (hints, reviews, failure explanations)
    written_answer   practice_answers (single questions and question-round answers alike)
    interview        practice_sessions (coding interviews and question rounds)

So nothing is back-filled or invented, each source row appears exactly once (no double counting),
and the existing export/deletion already covers it. Every query is scoped to the user.

Paging: each source is filtered, ordered and limited in SQL to the rows that could appear on the
requested page; the merge takes the page from those. Counts come from SQL COUNTs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, and_, false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.careers import CATALOG
from app.careers.grading import RUBRIC_VERSION
from app.careers.questions import get_question, questions_for
from app.careers.skills import career_skills, question_skills, questions_by_skill
from app.models import (
    AIAction,
    AIInteraction,
    InterviewStatus,
    InterviewTurn,
    PracticeAnswer,
    PracticeMode,
    PracticeSession,
    Problem,
    ProgressEvent,
    ProgressEventType,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    TurnRole,
    User,
)
from app.schemas.activity import (
    CODING,
    ActivityFacets,
    ActivityItem,
    ActivityStatus,
    ActivityTarget,
    ActivityType,
    CareerAnalytics,
    DayCount,
    FacetOption,
    InterviewCounts,
    ResumeInterview,
    ResumeOut,
    ResumeProblem,
    ResumeQuestion,
    SkillStat,
    TrendPoint,
    TrendSeries,
)
from app.schemas.common import Page

TYPE_LABELS: dict[str, str] = {
    "problem_opened": "Problem opened",
    "code_submission": "Code submission",
    "coaching": "Coaching",
    "written_answer": "Written answer",
    "interview": "Mock interview",
}
STATUS_LABELS: dict[str, str] = {
    "opened": "Opened (not an attempt)",
    "saved_not_judged": "Saved, not judged",
    "awaiting_judge": "Waiting for the judge",
    "passed": "Passed all tests",
    "failed": "Didn't pass",
    "evaluation_unavailable": "Evaluation unavailable",
    "scored": "Scored by the rubric",
    "completed": "Completed",
    "in_progress": "In progress",
    "expired": "Time ran out",
    "abandoned": "Ended early",
}
FAILED = {
    SubmissionStatus.FAILED,
    SubmissionStatus.COMPILE_ERROR,
    SubmissionStatus.RUNTIME_ERROR,
    SubmissionStatus.TIME_LIMIT,
    SubmissionStatus.MEMORY_LIMIT,
}
PENDING = {SubmissionStatus.QUEUED, SubmissionStatus.RUNNING}
COACHING_ACTIONS = (AIAction.HINT, AIAction.REVIEW, AIAction.EXPLAIN_FAILURE)
COACHING_LABELS = {
    AIAction.HINT: "Hint",
    AIAction.REVIEW: "Code review",
    AIAction.EXPLAIN_FAILURE: "Failure explanation",
}
INTERVIEW_STATUS = {
    InterviewStatus.IN_PROGRESS: "in_progress",
    InterviewStatus.COMPLETED: "completed",
    InterviewStatus.EXPIRED: "expired",
    InterviewStatus.ABANDONED: "abandoned",
}
CODING_TITLE = "Coding problems"


def evaluator_key(provider: str, feedback: dict) -> str:
    """Scores are only comparable within one evaluator and rubric version."""
    return feedback.get("evaluator") or f"{provider} · rubric {RUBRIC_VERSION}"


def career_title(career: str) -> str:
    if career == CODING:
        return CODING_TITLE
    profile = CATALOG.get(career)
    return profile.title if profile else career


@dataclass(frozen=True)
class ActivityFilters:
    career: str | None = None
    type: ActivityType | None = None
    since: date | None = None
    until: date | None = None
    skill: str | None = None
    status: ActivityStatus | None = None
    q: str | None = None


def _start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


class ActivityService:
    def __init__(self, db: Session, judge_enabled: bool):
        self.db = db
        self.judge_enabled = judge_enabled
        self._problems: list[Problem] | None = None

    # --- feed -------------------------------------------------------------------------------

    def feed(self, user: User, f: ActivityFilters, page: int, page_size: int) -> Page[ActivityItem]:
        limit = page * page_size
        items: list[ActivityItem] = []
        total = 0
        for source in (self._opened, self._submissions, self._coaching, self._answers, self._interviews):
            count, rows = source(user, f, limit)
            total += count
            items.extend(rows)
        items.sort(key=lambda i: (i.occurred_at, i.id), reverse=True)
        start = (page - 1) * page_size
        return Page[ActivityItem](
            items=items[start : start + page_size], total=total, page=page, page_size=page_size
        )

    def _wants(
        self, f: ActivityFilters, type_: str, statuses: set[str], coding: bool, track_ok: bool = True
    ) -> bool:
        if f.type and f.type != type_:
            return False
        if f.status and f.status not in statuses:
            return False
        if f.career == CODING:
            return coding
        if f.career is not None:
            return not coding and track_ok
        return True

    def _date_filter(self, f: ActivityFilters, column: Any) -> list[Any]:
        conds = []
        if f.since:
            conds.append(column >= _start(f.since))
        if f.until:
            conds.append(column < _start(f.until + timedelta(days=1)))
        return conds

    def _all_problems(self) -> list[Problem]:
        if self._problems is None:
            self._problems = list(self.db.scalars(select(Problem)).all())
        return self._problems

    def _problem_ids(self, f: ActivityFilters) -> set[int] | None:
        """Problem ids matching the skill/search filters; None when neither applies."""
        if not f.skill and not f.q:
            return None
        q = (f.q or "").strip().lower()
        return {
            p.id
            for p in self._all_problems()
            if (not f.skill or f.skill in p.topics) and (not q or q in p.title.lower())
        }

    def _page(self, stmt: Select, order_col: Any, limit: int) -> tuple[int, list[Any]]:
        count = self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        rows = list(self.db.execute(stmt.order_by(order_col.desc()).limit(limit)).all()) if count else []
        return count, rows

    def _opened(self, user: User, f: ActivityFilters, limit: int) -> tuple[int, list[ActivityItem]]:
        if not self._wants(f, "problem_opened", {"opened"}, coding=True):
            return 0, []
        stmt = (
            select(ProgressEvent, Problem)
            .join(Problem, Problem.id == ProgressEvent.problem_id)
            .where(ProgressEvent.user_id == user.id, ProgressEvent.event_type == ProgressEventType.OPENED)
            .where(*self._date_filter(f, ProgressEvent.created_at))
        )
        ids = self._problem_ids(f)
        if ids is not None:
            stmt = stmt.where(ProgressEvent.problem_id.in_(ids))
        count, rows = self._page(stmt, ProgressEvent.created_at, limit)
        return count, [
            ActivityItem(
                id=f"problem_opened:{e.id}",
                type="problem_opened",
                occurred_at=e.created_at,
                career=CODING,
                career_title=CODING_TITLE,
                title=p.title,
                detail=None,
                skills=list(p.topics),
                status="opened",
                status_label=STATUS_LABELS["opened"],
                score=None,
                session_id=None,
                target=ActivityTarget(href=f"/problems/{p.slug}", problem_slug=p.slug),
            )
            for e, p in rows
        ]

    def _submission_status(self, s: SubmissionStatus) -> ActivityStatus:
        if s == SubmissionStatus.PASSED:
            return "passed"
        if s in FAILED:
            return "failed"
        if s == SubmissionStatus.INTERNAL_ERROR:
            return "evaluation_unavailable"
        return "awaiting_judge" if self.judge_enabled else "saved_not_judged"

    def _submissions(self, user: User, f: ActivityFilters, limit: int) -> tuple[int, list[ActivityItem]]:
        pending = "awaiting_judge" if self.judge_enabled else "saved_not_judged"
        statuses = {"passed", "failed", "evaluation_unavailable", pending}
        if not self._wants(f, "code_submission", statuses, coding=True):
            return 0, []
        stmt = (
            select(Submission, Problem)
            .join(Problem, Problem.id == Submission.problem_id)
            .where(Submission.user_id == user.id, Submission.mode == SubmissionMode.SUBMIT)
            .where(*self._date_filter(f, Submission.created_at))
        )
        if f.status:
            wanted = {
                "passed": {SubmissionStatus.PASSED},
                "failed": FAILED,
                "evaluation_unavailable": {SubmissionStatus.INTERNAL_ERROR},
            }.get(f.status, PENDING)
            stmt = stmt.where(Submission.status.in_(wanted))
        ids = self._problem_ids(f)
        if ids is not None:
            stmt = stmt.where(Submission.problem_id.in_(ids))
        count, rows = self._page(stmt, Submission.created_at, limit)
        out = []
        for s, p in rows:
            status = self._submission_status(s.status)
            label = STATUS_LABELS[status]
            if status == "failed":
                label = f"Didn't pass ({s.status.value.replace('_', ' ').lower()})"
            elif status == "saved_not_judged":
                label = "Saved, not judged (the code judge isn't available on this server)"
            out.append(
                ActivityItem(
                    id=f"code_submission:{s.id}",
                    type="code_submission",
                    occurred_at=s.created_at,
                    career=CODING,
                    career_title=CODING_TITLE,
                    title=p.title,
                    detail=None,
                    skills=list(p.topics),
                    status=status,
                    status_label=label,
                    score=None,
                    session_id=None,
                    target=ActivityTarget(
                        href=f"/history/submissions/{s.id}", problem_slug=p.slug, submission_id=s.id
                    ),
                )
            )
        return count, out

    def _coaching(self, user: User, f: ActivityFilters, limit: int) -> tuple[int, list[ActivityItem]]:
        if not self._wants(f, "coaching", {"completed"}, coding=True):
            return 0, []
        stmt = (
            select(AIInteraction, Problem)
            .join(Problem, Problem.id == AIInteraction.problem_id)
            .where(AIInteraction.user_id == user.id, AIInteraction.action.in_(COACHING_ACTIONS))
            .where(*self._date_filter(f, AIInteraction.created_at))
        )
        ids = self._problem_ids(f)
        if ids is not None:
            stmt = stmt.where(AIInteraction.problem_id.in_(ids))
        count, rows = self._page(stmt, AIInteraction.created_at, limit)
        return count, [
            ActivityItem(
                id=f"coaching:{a.id}",
                type="coaching",
                occurred_at=a.created_at,
                career=CODING,
                career_title=CODING_TITLE,
                title=p.title,
                detail=COACHING_LABELS[a.action] + (f", level {a.hint_level}" if a.hint_level else ""),
                skills=list(p.topics),
                status="completed",
                status_label="Delivered",
                score=None,
                session_id=None,
                target=ActivityTarget(
                    href=f"/history/coaching/{a.id}", problem_slug=p.slug, ai_interaction_id=a.id
                ),
            )
            for a, p in rows
        ]

    def _question_ids(self, user: User, f: ActivityFilters) -> dict[str, set[str]] | None:
        """Per career, question ids matching the skill/search filters; None when neither applies."""
        if not f.skill and not f.q:
            return None
        tracks = [f.career] if f.career and f.career != CODING else self._tracks(user)
        q = (f.q or "").strip().lower()
        out: dict[str, set[str]] = {}
        for track in tracks:
            if track not in CATALOG:
                continue
            ids = (
                set(questions_by_skill(track).get(f.skill, frozenset()))
                if f.skill
                else {x.id for x in questions_for(track)}
            )
            if q:
                ids = {x.id for x in questions_for(track) if x.id in ids and q in x.title.lower()}
            out[track] = ids
        return out

    def _tracks(self, user: User) -> list[str]:
        a = self.db.scalars(
            select(PracticeAnswer.track).where(PracticeAnswer.user_id == user.id).distinct()
        ).all()
        s = self.db.scalars(
            select(PracticeSession.track)
            .where(PracticeSession.user_id == user.id, PracticeSession.track.is_not(None))
            .distinct()
        ).all()
        return sorted({*a, *(t for t in s if t)})

    def _answers(self, user: User, f: ActivityFilters, limit: int) -> tuple[int, list[ActivityItem]]:
        if not self._wants(f, "written_answer", {"scored"}, coding=False):
            return 0, []
        stmt = (
            select(PracticeAnswer)
            .where(PracticeAnswer.user_id == user.id)
            .where(*self._date_filter(f, PracticeAnswer.created_at))
        )
        if f.career and f.career != CODING:
            stmt = stmt.where(PracticeAnswer.track == f.career)
        wanted = self._question_ids(user, f)
        if wanted is not None:
            conds = [
                and_(PracticeAnswer.track == t, PracticeAnswer.question_id.in_(ids))
                for t, ids in wanted.items()
                if ids
            ]
            stmt = stmt.where(or_(*conds) if conds else false())
        count, rows = self._page(
            stmt.add_columns(PracticeAnswer.created_at), PracticeAnswer.created_at, limit
        )
        answers = [r[0] for r in rows]
        sessions = (
            dict(
                self.db.execute(
                    select(InterviewTurn.answer_id, InterviewTurn.session_id).where(
                        InterviewTurn.answer_id.in_([a.id for a in answers])
                    )
                ).all()
            )
            if answers
            else {}
        )
        out = []
        for a in answers:
            q = get_question(a.track, a.question_id)
            rating = (a.feedback or {}).get("rating", "")
            out.append(
                ActivityItem(
                    id=f"written_answer:{a.id}",
                    type="written_answer",
                    occurred_at=a.created_at,
                    career=a.track,
                    career_title=career_title(a.track),
                    title=q.title if q else "A question that's no longer in the library",
                    detail="Part of a mock interview" if a.id in sessions else None,
                    skills=list(question_skills(q)) if q else [],
                    status="scored",
                    status_label=f"Scored {a.score}/100 ({rating})" if rating else f"Scored {a.score}/100",
                    score=a.score,
                    session_id=sessions.get(a.id),
                    target=ActivityTarget(
                        href=f"/careers/{a.track}/questions/{a.question_id}?answer={a.id}",
                        track=a.track,
                        question_id=a.question_id,
                        answer_id=a.id,
                    ),
                )
            )
        return count, out

    def _interviews(self, user: User, f: ActivityFilters, limit: int) -> tuple[int, list[ActivityItem]]:
        statuses = set(INTERVIEW_STATUS.values())
        if f.skill or (f.type and f.type != "interview") or (f.status and f.status not in statuses):
            return 0, []  # an interview spans several skills, so a skill filter leaves interviews out
        stmt = (
            select(PracticeSession)
            .where(
                PracticeSession.user_id == user.id,
                PracticeSession.mode.in_((PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)),
            )
            .where(*self._date_filter(f, PracticeSession.started_at))
        )
        if f.career == CODING:
            stmt = stmt.where(PracticeSession.mode == PracticeMode.INTERVIEW)
        elif f.career:
            stmt = stmt.where(
                PracticeSession.mode == PracticeMode.QUESTIONS, PracticeSession.track == f.career
            )
        if f.status:
            stmt = stmt.where(
                PracticeSession.status == next(k for k, v in INTERVIEW_STATUS.items() if v == f.status)
            )
        if f.q:
            q = f.q.strip().lower()
            pids = {p.id for p in self._all_problems() if q in p.title.lower()}
            tracks = [t for t in CATALOG if q in CATALOG[t].title.lower()]
            stmt = stmt.where(or_(PracticeSession.problem_id.in_(pids), PracticeSession.track.in_(tracks)))
        count, rows = self._page(
            stmt.add_columns(PracticeSession.started_at), PracticeSession.started_at, limit
        )
        sessions = [r[0] for r in rows]
        if sessions:
            self.db.execute(
                select(PracticeSession)
                .options(selectinload(PracticeSession.turns), selectinload(PracticeSession.problem))
                .where(PracticeSession.id.in_([s.id for s in sessions]))
            ).all()
        out = []
        for s in sessions:
            status: ActivityStatus = INTERVIEW_STATUS[s.status]  # type: ignore[assignment]
            detail: str | None
            if s.mode == PracticeMode.QUESTIONS:
                total = len((s.plan or {}).get("question_ids", []))
                replies = [t for t in s.turns if t.role == TurnRole.CANDIDATE]
                answered = sum(1 for t in replies if not (t.meta or {}).get("skipped"))
                career = s.track or ""
                title = f"{career_title(career)} question round"
                detail = f"{answered} of {total} answered" + (
                    f", {len(replies) - answered} skipped" if len(replies) > answered else ""
                )
            else:
                career = CODING
                title = f"Coding interview: {s.problem.title}" if s.problem else "Coding interview"
                overall = str((s.evaluation or {}).get("overall") or "")
                detail = overall.replace("_", " ").capitalize() if overall else None
            out.append(
                ActivityItem(
                    id=f"interview:{s.id}",
                    type="interview",
                    occurred_at=s.started_at,
                    career=career,
                    career_title=career_title(career),
                    title=title,
                    detail=detail,
                    skills=[],
                    status=status,
                    status_label=STATUS_LABELS[status],
                    score=None,
                    session_id=s.id,
                    target=ActivityTarget(
                        href=f"/interviews/{s.id}",
                        interview_id=s.id,
                        track=s.track,
                        problem_slug=s.problem.slug if s.problem else None,
                    ),
                )
            )
        return count, out

    # --- facets -----------------------------------------------------------------------------

    def facets(self, user: User, career: str | None) -> ActivityFacets:
        def n(stmt: Select) -> int:
            return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        opened = n(
            select(ProgressEvent.id).where(
                ProgressEvent.user_id == user.id, ProgressEvent.event_type == ProgressEventType.OPENED
            )
        )
        subs = dict(
            self.db.execute(
                select(Submission.status, func.count())
                .where(Submission.user_id == user.id, Submission.mode == SubmissionMode.SUBMIT)
                .group_by(Submission.status)
            ).all()
        )
        coaching = n(
            select(AIInteraction.id).where(
                AIInteraction.user_id == user.id, AIInteraction.action.in_(COACHING_ACTIONS)
            )
        )
        answers = dict(
            self.db.execute(
                select(PracticeAnswer.track, func.count())
                .where(PracticeAnswer.user_id == user.id)
                .group_by(PracticeAnswer.track)
            ).all()
        )
        sessions = self.db.execute(
            select(PracticeSession.mode, PracticeSession.track, PracticeSession.status, func.count())
            .where(
                PracticeSession.user_id == user.id,
                PracticeSession.mode.in_((PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)),
            )
            .group_by(PracticeSession.mode, PracticeSession.track, PracticeSession.status)
        ).all()

        careers: Counter[str] = Counter()
        careers[CODING] += opened + sum(subs.values()) + coaching
        for track, c in answers.items():
            careers[track] += c
        statuses: Counter[str] = Counter(
            {"opened": opened, "scored": sum(answers.values()), "completed": coaching}
        )
        for sub_status, c in subs.items():
            statuses[self._submission_status(sub_status)] += c
        interviews = 0
        for mode, session_track, iv_status, c in sessions:
            careers[CODING if mode == PracticeMode.INTERVIEW else (session_track or "")] += c
            statuses[INTERVIEW_STATUS[iv_status]] += c
            interviews += c
        types = {
            "problem_opened": opened,
            "code_submission": sum(subs.values()),
            "coaching": coaching,
            "written_answer": sum(answers.values()),
            "interview": interviews,
        }
        skills: list[FacetOption] = []
        if career == CODING:
            topics: Counter[str] = Counter()
            touched = set(
                self.db.scalars(select(Submission.problem_id).where(Submission.user_id == user.id)).all()
            ) | set(
                self.db.scalars(
                    select(ProgressEvent.problem_id).where(ProgressEvent.user_id == user.id)
                ).all()
            )
            for p in self._all_problems():
                if p.id in touched:
                    topics.update(p.topics)
            skills = [
                FacetOption(value=t, label=t.replace("-", " ").capitalize(), count=c)
                for t, c in sorted(topics.items())
            ]
        elif career in CATALOG:
            per_skill: Counter[str] = Counter()
            for qid in self.db.scalars(
                select(PracticeAnswer.question_id).where(
                    PracticeAnswer.user_id == user.id, PracticeAnswer.track == career
                )
            ).all():
                q = get_question(career, qid)
                if q:
                    per_skill.update(question_skills(q))
            skills = [
                FacetOption(value=s, label=s[:1].upper() + s[1:], count=per_skill[s])
                for s in career_skills(career)
            ]
        return ActivityFacets(
            careers=[
                FacetOption(value=c, label=career_title(c), count=k) for c, k in careers.most_common() if k
            ],
            types=[FacetOption(value=t, label=TYPE_LABELS[t], count=c) for t, c in types.items()],
            statuses=[
                FacetOption(value=s, label=STATUS_LABELS[s], count=c) for s, c in statuses.items() if c
            ],
            skills=skills,
        )

    # --- career analytics -------------------------------------------------------------------

    def career_analytics(self, user: User, track: str, since: date | None, until: date) -> CareerAnalytics:
        stmt = select(PracticeAnswer).where(PracticeAnswer.user_id == user.id, PracticeAnswer.track == track)
        stmt = stmt.where(PracticeAnswer.created_at < _start(until + timedelta(days=1)))
        if since:
            stmt = stmt.where(PracticeAnswer.created_at >= _start(since))
        answers = list(self.db.scalars(stmt.order_by(PracticeAnswer.created_at)).all())
        best: dict[str, int] = {}
        for a in answers:
            best[a.question_id] = max(best.get(a.question_id, 0), a.score)
        by_skill = questions_by_skill(track)
        answers_per_q = Counter(a.question_id for a in answers)
        skills = []
        for s in career_skills(track):
            qids = [q for q in best if q in by_skill.get(s, frozenset())]
            skills.append(
                SkillStat(
                    skill=s,
                    total_questions=len(by_skill.get(s, frozenset())),
                    questions_answered=len(qids),
                    answers=sum(answers_per_q[q] for q in qids),
                    average_best_score=round(sum(best[q] for q in qids) / len(qids)) if qids else None,
                )
            )
        kinds: Counter[str] = Counter()
        for a in answers:
            q = get_question(track, a.question_id)
            if q:
                kinds[q.kind] += 1
        sstmt = select(PracticeSession.status, PracticeSession.started_at).where(
            PracticeSession.user_id == user.id,
            PracticeSession.mode == PracticeMode.QUESTIONS,
            PracticeSession.track == track,
            PracticeSession.started_at < _start(until + timedelta(days=1)),
        )
        if since:
            sstmt = sstmt.where(PracticeSession.started_at >= _start(since))
        session_rows = self.db.execute(sstmt).all()
        istatus = Counter(INTERVIEW_STATUS[s] for s, _ in session_rows)

        series: dict[str, dict[date, list[int]]] = defaultdict(lambda: defaultdict(list))
        for a in answers:
            day = a.created_at.date()
            series[evaluator_key(a.provider, a.feedback or {})][day - timedelta(days=day.weekday())].append(
                a.score
            )
        trends = [
            TrendSeries(
                evaluator=key,
                points=[
                    TrendPoint(week_start=w, answers=len(v), average_score=round(sum(v) / len(v)))
                    for w, v in sorted(weeks.items())
                ],
            )
            for key, weeks in series.items()
        ]
        first = since or (answers[0].created_at.date() if answers else until)
        first = max(first, until - timedelta(days=364))
        days = Counter(a.created_at.date() for a in answers)
        idays = Counter(started.date() for _, started in session_rows)
        by_day = [
            DayCount(
                day=first + timedelta(days=i),
                answers=days[first + timedelta(days=i)],
                interviews=idays[first + timedelta(days=i)],
            )
            for i in range((until - first).days + 1)
        ]
        return CareerAnalytics(
            track=track,
            career_title=career_title(track),
            since=since,
            until=until,
            questions_practiced=len(best),
            answers=len(answers),
            strong_questions=sum(1 for v in best.values() if v >= 85),
            total_questions=len(questions_for(track)),
            skills=skills,
            kinds=[FacetOption(value=k, label=k.capitalize(), count=c) for k, c in kinds.most_common()],
            interviews=InterviewCounts(
                completed=istatus["completed"],
                in_progress=istatus["in_progress"],
                expired=istatus["expired"],
                abandoned=istatus["abandoned"],
            ),
            trends=trends,
            by_day=by_day,
            definitions={
                "questions_practiced": "Different questions you've answered at least once in this range.",
                "answers": "Every answer you submitted, including repeats and answers given in mock interviews.",
                "strong_questions": "Questions whose best score in this range is 85 or more.",
                "average_best_score": "For each skill: the average of your best score on each of its questions. "
                "Scores measure how well an answer covers the rubric, not whether it is correct.",
                "trend": "Weekly average score. Scores are only compared within one evaluator and rubric version; "
                f"answers graded before versions were recorded used the built-in rubric {RUBRIC_VERSION}.",
                "interviews": "Question rounds for this career started in this range, by how they ended.",
                "skills": "Each question practises the career skills or tools it names, or one general competency "
                "(working with people, judgment under pressure, leadership, motivation and fit, core knowledge).",
            },
        )

    # --- continue where you left off ------------------------------------------------------

    def resume(self, user: User) -> ResumeOut:
        now = datetime.now(UTC)
        active = self.db.scalar(
            select(PracticeSession)
            .options(selectinload(PracticeSession.problem))
            .where(
                PracticeSession.user_id == user.id,
                PracticeSession.mode.in_((PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)),
                PracticeSession.status == InterviewStatus.IN_PROGRESS,
            )
        )
        interview = None
        if active is not None and active.deadline_at and active.deadline_at > now:
            interview = ResumeInterview(
                id=active.id,
                kind="questions" if active.mode == PracticeMode.QUESTIONS else "coding",
                title=(
                    f"{career_title(active.track or '')} question round"
                    if active.mode == PracticeMode.QUESTIONS
                    else f"Coding interview: {active.problem.title}"
                    if active.problem
                    else "Coding interview"
                ),
                deadline_at=active.deadline_at,
                seconds_remaining=int((active.deadline_at - now).total_seconds()),
            )
        solved = select(Submission.problem_id).where(
            Submission.user_id == user.id, Submission.status == SubmissionStatus.PASSED
        )
        last_sub = self.db.execute(
            select(Submission, Problem)
            .join(Problem, Problem.id == Submission.problem_id)
            .where(
                Submission.user_id == user.id,
                Submission.mode == SubmissionMode.SUBMIT,
                Submission.problem_id.not_in(solved),
            )
            .order_by(Submission.created_at.desc())
            .limit(1)
        ).first()
        unfinished = None
        if last_sub:
            s, p = last_sub
            unfinished = ResumeProblem(
                slug=p.slug, title=p.title, last_status=self._submission_status(s.status), at=s.created_at
            )
        last_answer = self.db.scalar(
            select(PracticeAnswer)
            .where(PracticeAnswer.user_id == user.id)
            .order_by(PracticeAnswer.created_at.desc())
            .limit(1)
        )
        question = None
        if last_answer:
            q = get_question(last_answer.track, last_answer.question_id)
            if q:
                question = ResumeQuestion(
                    track=q.track, question_id=q.id, title=q.title, at=last_answer.created_at
                )
        return ResumeOut(interview=interview, unfinished_problem=unfinished, last_question=question)


__all__ = ["ActivityFilters", "ActivityService", "career_title", "evaluator_key"]
