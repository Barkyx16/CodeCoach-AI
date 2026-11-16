"""The adaptive practice plan: transparent, deterministic rules over recorded evidence.

Inputs, per career (one career's evidence never counts toward another's):
  goals       optional: focus areas, formats, experience, weekly time, target date, confidence
  answers     practice_answers for the career (best score per question, rubric points missed)
  sessions    question rounds for the career (completed rounds, spoken answers)
  coding      for careers with coding problems: submissions and the judge's verdicts, on problems
              and (as evidence for their topics only) debugging exercises; never runs, and never a
              submission the judge failed to run

Rules, in order (see `_generate`):
  1. Fewer than 3 answers and no finished baseline round -> a 3-question baseline first.
  2. Weak answers (best < 70) -> review the feedback, then retry (weakest first, at most 2).
  3. Focus questions: the skills you asked for, then skills you haven't practised, then your
     lowest-scoring skills; at your level (raised a level once a skill's average best is 85+).
  4. Voice, if you chose it and haven't answered out loud in 7 days.
  5. Coding problems from the existing recommender, if the career has coding and you want it.
  (2b) A Learn unit for a weak or chosen skill that has one, if you haven't passed its check:
     placed before the retry it prepares for. Done only when the unit's comprehension check is
     passed after it was planned; reading the unit is not enough.
  6. A full 5-question mock interview once there's a baseline and none finished in 14 days.

Completion is read from evidence created after the activity was planned (an answer to that
question, a spoken answer, a finished round, a submitted attempt), never assumed. The one
exception, "review feedback", is marked by the learner and labelled as self-reported. Skipping
or replacing never marks anything done. When work is completed (or goals change) a new plan
version is made, and its `changes` list explains what moved and why. Practice the version doesn't
use (an answer elsewhere, a finished round) never makes one by itself: the plan names it (`news`)
when it would change what's chosen, and the learner's "Update my plan" makes the next version
(docs/PLAN_UPDATES.md). AI is not used.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.careers import CATALOG
from app.careers.eligibility import eligibility, eligibility_columns, feedback_eligibility
from app.careers.questions import Question, get_question, questions_for
from app.careers.skills import career_skills, question_skills, questions_by_skill
from app.errors import AppError, ConflictError, NotFoundError
from app.learn import units_for
from app.models import (
    InterviewStatus,
    InterviewTurn,
    LearnEvent,
    PlanItem,
    PracticeAnswer,
    PracticeGoal,
    PracticeMode,
    PracticePlan,
    PracticeSession,
    Problem,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    TurnRole,
    User,
)
from app.schemas.roadmap import (
    AssessmentOut,
    CodingEvidence,
    EvaluatedSkill,
    GoalsIn,
    GoalsOut,
    NewEvidence,
    PlanItemOut,
    PlanNews,
    PlanOut,
    PlanProgress,
    ReadLesson,
    ReadSubmission,
    RoundStart,
    SelfRating,
    SkillNews,
    TodayOut,
    Withheld,
)
from app.services.disputes import OVERALL, Dispute, Disputes, covering, first_disputed
from app.services.disputes import note as dispute_note
from app.services.learn import Learn
from app.services.progress import ProgressService, build_facts

DEFAULT_TRACK = "software-engineer"
DEFAULT_WEEKLY_MINUTES = 60


@dataclass
class _Used:
    """Evidence that already completed an item: answer ids, round (session) ids and judged
    submission ids."""

    answers: set[str]
    sessions: set[str]
    submissions: set[str] = field(default_factory=set)
    lessons: set[str] = field(default_factory=set)  # Learn units whose check completed an item


# Rounds are matched before single answers, so a round claims the answers inside it.
_ROUND_ORDER = {"assessment": 0, "mock": 1, "voice": 2}

WEAK = 70
STRONG = 85
MAX_ITEMS = 8
LEVELS = ("easy", "medium", "hard")
START_LEVEL = {"new": "easy", "early": "easy", "mid": "medium", "senior": "hard"}
JUDGED = {
    SubmissionStatus.PASSED,
    SubmissionStatus.FAILED,
    SubmissionStatus.COMPILE_ERROR,
    SubmissionStatus.RUNTIME_ERROR,
    SubmissionStatus.TIME_LIMIT,
    SubmissionStatus.MEMORY_LIMIT,
}
CODING_MINUTES = {"easy": 15, "medium": 25, "hard": 35}
# A verdict in the judge's own terms (Volume 16, prompt 7): never turned into a score.
VERDICT = {
    SubmissionStatus.PASSED: "passed",
    SubmissionStatus.FAILED: "tests failed",
    SubmissionStatus.COMPILE_ERROR: "compile error",
    SubmissionStatus.RUNTIME_ERROR: "runtime error",
    SubmissionStatus.TIME_LIMIT: "time limit exceeded",
    SubmissionStatus.MEMORY_LIMIT: "memory limit exceeded",
}
CODE_RULE = (
    "How code counts: a pass counts as solved; failed tests, errors and time or memory limits count as "
    "tried, not solved. A verdict is never turned into a score."
)
EVIDENCE_READ = (
    "This plan reads your scored answers to {career} questions, your finished question rounds and the "
    "lesson checks you've passed{code}. A lesson only read, or a check not passed, isn't evidence. "
    "Improvements you accept are kept beside the plan and don't change what it suggests; the practice "
    "they lead to does."
)
EVIDENCE_READ_CODE = (
    ", and the judge's verdicts on code you submit: to problems, and to debugging exercises for the skills "
    "they name (not runs, which check the public tests only)"
)


def _now() -> datetime:
    return datetime.now(UTC)


def _withheld(what: str, d: Dispute, why: str) -> dict[str, str]:
    """One line for a suggestion the plan didn't make because of a dispute (docs/DISPUTES.md)."""
    return {
        "text": f"Not suggested: {what}: {why}.",
        "href": d.href,
        "answer_id": d.answer_id,
        "criterion": d.criterion,
    }


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _code_skill(problem: Problem) -> str:
    """The skill a submission is labelled with: a problem's first topic (as the plan's coding
    activities are labelled), a debugging exercise's first topic after "debugging" itself."""
    return _code_skills(problem)[0]


def _code_skills(problem: Problem) -> list[str]:
    """Every skill a submission is evidence for (Volume 17, prompt 9): each of its problem's topics,
    as the planner reads them; a debugging exercise's after "debugging" itself."""
    topics = [t for t in problem.topics or [] if not (problem.kind == "debug" and t == "debugging")]
    return list(dict.fromkeys(topics)) or ["debugging" if problem.kind == "debug" else "problem solving"]


def _and(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


@dataclass
class _Piece:
    """One piece of new evidence, for the preview's sentence about its skill."""

    kind: str  # answer | round | submission | lesson
    title: str
    ref: str = ""  # the evidence's id: one submission is a piece of each of its topics' skills
    score: int | None = None
    passed: bool | None = None
    verdict: str | None = None
    exercise: bool = False


def _moves(came_in: list[Spec], left: list[Spec], also: bool = False) -> str | None:
    """'the next version would suggest “A” and not “B”', or None when nothing moves."""
    ins = _and([f"“{s.title}”" for s in came_in]) if came_in else ""
    outs = _and([f"“{s.title}”" for s in left]) if left else ""
    would = "would also" if also else "would"
    if ins and outs:
        return f"the next version {would} suggest {ins} and not {outs}"
    if ins:
        return f"the next version {would} suggest {ins}"
    if outs:
        return f"the next version {'also ' if also else ''}wouldn't suggest {outs}"
    return None


def _skill_sentence(
    skill: str, pieces: list[_Piece], came_in: list[Spec], left: list[Spec], alone: str = "on its own"
) -> str:
    """One sentence: what's new for the skill, what it counts as, and what it moves (or that it
    moves nothing on its own). Verdicts are said as verdicts; scores only for answers."""
    phrases: list[str] = []
    code = [p for p in pieces if p.kind == "submission"]
    if code:
        if len(code) > 3:
            passed = sum(bool(p.passed) for p in code)
            phrases.append(f"{len(code)} submissions, {passed} of them passed")
        else:
            # Each problem once, its attempts in order: "“Two Sum” didn't pass (tests failed), then passed".
            by_title: dict[tuple[str, bool], list[str]] = {}
            for p in code:
                by_title.setdefault((p.title, p.exercise), []).append(
                    "passed" if p.passed else f"didn't pass ({p.verdict})"
                )
            phrases.append(
                _and(
                    [
                        ("the debugging exercise " if exercise else "")
                        + f"“{title}” "
                        + ", then ".join(results)
                        for (title, exercise), results in by_title.items()
                    ]
                )
            )
    answers = [p for p in pieces if p.kind == "answer"]
    if answers:
        if len(answers) > 2:
            below = sum((p.score or 0) < WEAK for p in answers)
            phrases.append(f"{len(answers)} answers, {below} below {WEAK}")
        else:
            phrases.append(_and([f"“{p.title}” scored {p.score}/100" for p in answers]))
    rounds = [p for p in pieces if p.kind == "round"]
    if rounds:
        phrases.append(_and([f"a finished {p.title[0].lower() + p.title[1:]}" for p in rounds]))
    lessons = [p for p in pieces if p.kind == "lesson"]
    if lessons:  # a check graded by its rubric (Volume 17, prompt 3); reading alone never counts
        phrases.append("the check passed on " + _and([f"the lesson “{p.title}”" for p in lessons]))
    what = "; ".join(phrases)
    meaning = ""
    if code:
        if all(p.passed for p in code):
            meaning = ", which counts as solved"
        elif not any(p.passed for p in code):
            meaning = ", which counts as tried, not solved"
        else:
            meaning = ": a pass counts as solved, the rest as tried"
    moved = _moves(came_in, left)
    head = skill[:1].upper() + skill[1:]
    if moved is None:
        return f"{head}: {what}{meaning}; {alone} that changes nothing the plan chooses."
    return f"{head}: {what}{meaning}, so {moved}."


# Each skill with new evidence is asked about on its own up to this many (Volume 17, prompt 9): the
# plan's own limit on items. Past it, the rest are asked about together, in one more plan.
SKILLS_ASKED_ALONE = MAX_ITEMS


def _together(names: list[str]) -> str:
    return f"the other {len(names)} skills together ({_and(names)})"


def _submissions_text(submissions: int, not_passed: int) -> str:
    """ "1 submission (not passed)", "3 submissions (2 not passed)", "2 submissions (both passed)"."""
    text = _plural(submissions, "submission", "submissions")
    if submissions == 1:
        return text + (" (not passed)" if not_passed else " (passed)")
    if not_passed == 0:
        return text + (" (both passed)" if submissions == 2 else " (all passed)")
    if not_passed == submissions:
        return text + (" (neither passed)" if submissions == 2 else " (none passed)")
    return text + f" ({not_passed} not passed)"


def news_text(
    answers: int,
    retries: int,
    below: int,
    rounds: int,
    since: str,
    submissions: int = 0,
    not_passed: int = 0,
    lessons: int = 0,
) -> str:
    """One line for what's new: "2 answers since this plan, one below 70." Counts only: it says
    what was done and how it scored (a submission: passed or not, as judged), never that anything
    improved."""
    parts: list[str] = []
    if answers:
        if retries == answers:
            parts.append(_plural(answers, "retry", "retries"))
        elif retries:
            parts.append(
                f"{_plural(answers, 'answer', 'answers')} ({retries} of them {'a retry' if retries == 1 else 'retries'})"
            )
        else:
            parts.append(_plural(answers, "answer", "answers"))
    if rounds:
        parts.append(_plural(rounds, "finished round", "finished rounds"))
    if submissions:
        parts.append(_submissions_text(submissions, not_passed))
    if lessons:
        parts.append(_plural(lessons, "lesson check passed", "lesson checks passed"))
    text = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] + f" since {since}"
    if below and submissions:
        text += (
            ", the answer below 70" if answers == 1 else f", {_plural(below, 'answer', 'answers')} below 70"
        )
    elif below:
        if answers == 1:
            text += ", below 70"
        elif below == answers:
            text += ", both below 70" if answers == 2 else ", all below 70"
        else:
            text += f", {'one' if below == 1 else below} below 70"
    return text + "."


@dataclass
class Spec:
    kind: str
    skill: str
    title: str
    reason: str
    completion: str
    minutes: int
    target: dict[str, Any] = field(default_factory=dict)
    # What it was derived from (docs/DISPUTES.md): [{answer_id, criterion}], criterion a feedback
    # point's label or "Overall" (that answer's score and feedback as a whole).
    derived: list[dict[str, str]] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        t = self.target
        return self.kind, str(
            t.get("question_id")
            or t.get("problem_slug")
            or t.get("unit_id")
            or t.get("purpose")
            or self.skill
        )


@dataclass
class Evidence:
    best: dict[str, int]  # question id -> best score among answers long enough to score
    latest: dict[str, str]  # question id -> id of the most recent answer
    answers: int
    baseline_done: bool
    last_mock: datetime | None
    last_voice: datetime | None
    learn_passed: set[str] = field(default_factory=set)  # unit ids whose check was passed
    # Every question with at least one answer (including answers too short to score, which have
    # no entry in `best`: app/careers/eligibility.py).
    answered: set[str] = field(default_factory=set)
    # Disputes (docs/DISPUTES.md): an answer whose feedback as a whole is disputed doesn't count
    # above; these keep what it would have been, to say what wasn't suggested and why.
    disputes: dict[tuple[str, str], Dispute] = field(default_factory=dict)
    best_answer: dict[str, str] = field(default_factory=dict)  # question -> the answer with `best`
    best_all: dict[str, int] = field(default_factory=dict)  # with disputed answers counted
    answered_all: set[str] = field(default_factory=set)
    disputed_question: dict[str, Dispute] = field(default_factory=dict)
    withheld: list[dict[str, str]] = field(default_factory=list)  # filled while generating
    # Submissions to read as if they didn't exist (the plan without what's new: Roadmap._news).
    left_out_submissions: set[str] = field(default_factory=set)
    # The problem facts to plan coding from, built in memory from rows read once (Volume 17,
    # prompt 9); None: read them (the planner's own reading, as before).
    code_facts: dict[int, Any] | None = None
    # Planned only to compare what it chooses (the preview's plans): a weak answer's feedback words
    # an item and is never what chooses one, so it isn't read (Volume 17, prompt 9).
    choosing_only: bool = False


def _read_lessons(track: str, plan: PracticePlan) -> list[ReadLesson] | None:
    """The lesson checks the update that made this version read, as it recorded them (no statement:
    titles come from the catalog). One no longer offered is still listed, by its unit."""
    if plan.read_lessons is None:
        return None
    units = {u.id: u for u in units_for(track)}
    out = []
    for rec in plan.read_lessons:
        unit = units.get(rec.get("unit_id", ""))
        out.append(
            ReadLesson(
                unit_id=rec.get("unit_id", ""),
                version=int(rec.get("version") or 0),
                title=unit.title if unit else None,
                href=f"/learn/{unit.id}" if unit else None,
            )
        )
    return out


@dataclass
class _EvidenceRows:
    """The rows a plan's evidence is built from (`Roadmap._evidence_rows`)."""

    answers: list[tuple[Any, ...]]  # (id, question_id, score, level, words), oldest first
    sessions: list[PracticeSession]
    voice_turns: list[tuple[Any, ...]]  # (created_at, meta, session_id, answer_id)
    learn_passed: set[str]


def _evidence_from(
    rows: _EvidenceRows,
    disputes: dict[tuple[str, str], Dispute] | None = None,
    leave_out: _Used | None = None,
) -> Evidence:
    """The plan's evidence from rows already read, leaving out what's named (in memory)."""
    answers = rows.answers
    if leave_out is not None:
        answers = [r for r in answers if r[0] not in leave_out.answers]
    disputes = disputes or {}
    best: dict[str, int] = {}
    best_answer: dict[str, str] = {}
    best_all: dict[str, int] = {}
    latest: dict[str, str] = {}
    answered: set[str] = set()
    answered_all: set[str] = set()
    disputed_question: dict[str, Dispute] = {}
    for answer_id, question_id, score, level, words in answers:
        answered_all.add(question_id)
        scored = eligibility(level, words) == "scored"
        if scored:
            best_all[question_id] = max(best_all.get(question_id, 0), score)
        overall = disputes.get((answer_id, OVERALL))
        if overall is not None:
            # Its feedback as a whole is disputed: it doesn't shape the plan (its score stays).
            disputed_question.setdefault(question_id, overall)
            continue
        answered.add(question_id)
        if scored and score > best.get(question_id, -1):
            best[question_id], best_answer[question_id] = score, answer_id
        latest[question_id] = answer_id
    sessions = rows.sessions
    if leave_out is not None:
        sessions = [s for s in sessions if s.id not in leave_out.sessions]
    completed = [s for s in sessions if s.status == InterviewStatus.COMPLETED]
    mocks = [
        _aware(s.started_at)
        for s in completed
        if (s.plan or {}).get("purpose", "practice") == "practice"
        and len((s.plan or {}).get("question_ids", [])) >= 5
    ]
    spoken = [
        _aware(at)
        for at, meta, sid, aid in rows.voice_turns
        if (meta or {}).get("source") in ("voice", "mixed")
        and (leave_out is None or (sid not in leave_out.sessions and aid not in leave_out.answers))
    ]
    return Evidence(
        best=best,
        latest=latest,
        answers=len(answers),
        baseline_done=any((s.plan or {}).get("purpose") == "baseline" for s in completed),
        last_mock=max(mocks) if mocks else None,
        last_voice=max(spoken) if spoken else None,
        # A check passed since the plan, left out to ask what it alone would move (prompt 3).
        learn_passed=rows.learn_passed - (leave_out.lessons if leave_out else set()),
        answered=answered,
        disputes=disputes,
        best_answer=best_answer,
        best_all=best_all,
        answered_all=answered_all,
        disputed_question=disputed_question,
        left_out_submissions=set(leave_out.submissions) if leave_out is not None else set(),
    )


class Roadmap:
    def __init__(self, db: Session, judge_enabled: bool):
        self.db = db
        self.judge_enabled = judge_enabled

    # --- goals ------------------------------------------------------------------------------

    def _track(self, user: User, track: str | None) -> str:
        t = track or user.career_track or DEFAULT_TRACK
        if t not in CATALOG:
            raise NotFoundError(f"Career '{t}' not found")
        return t

    def _goal(self, user: User, track: str) -> PracticeGoal | None:
        return self.db.scalar(
            select(PracticeGoal).where(PracticeGoal.user_id == user.id, PracticeGoal.track == track)
        )

    def goals(self, user: User, track: str | None) -> GoalsOut:
        t = self._track(user, track)
        g = self._goal(user, t)
        return self._goals_out(t, g)

    def save_goals(self, user: User, body: GoalsIn) -> GoalsOut:
        t = self._track(user, body.track)
        profile = CATALOG[t]
        skills = set(career_skills(t))
        bad = [s for s in [*body.focus_areas, *body.confidence] if s not in skills]
        if bad:
            raise AppError(
                f"Not a skill of {profile.title}: {', '.join(sorted(set(bad))[:3])}",
                code="unknown_skill",
                details={"unknown": sorted(set(bad))},
            )
        if any(not 1 <= v <= 5 for v in body.confidence.values()):
            raise AppError("Confidence ratings go from 1 to 5.", code="invalid_confidence")
        if "coding" in body.formats and not profile.has_coding:
            raise AppError(f"{profile.title} doesn't have coding problems.", code="no_coding")
        g = self._goal(user, t) or PracticeGoal(user_id=user.id, track=t)
        g.specialty = body.specialty.strip() if body.specialty else None
        g.experience = body.experience
        g.target_date = body.target_date
        g.weekly_minutes = body.weekly_minutes
        g.focus_areas = list(dict.fromkeys(body.focus_areas))
        g.formats = list(dict.fromkeys(body.formats))
        g.confidence = dict(body.confidence)
        g.setup_skipped = body.setup_skipped
        g.updated_at = _now()
        self.db.add(g)
        self.db.commit()
        return self._goals_out(t, g)

    def _goals_out(self, track: str, g: PracticeGoal | None) -> GoalsOut:
        profile = CATALOG[track]
        return GoalsOut(
            track=track,
            career_title=profile.title,
            has_coding=profile.has_coding,
            skills=list(career_skills(track)),
            saved=g is not None,
            specialty=g.specialty if g else None,
            experience=g.experience if g else None,
            target_date=g.target_date if g else None,
            weekly_minutes=g.weekly_minutes if g else None,
            focus_areas=list(g.focus_areas) if g else [],
            formats=list(g.formats) if g else [],
            confidence=dict(g.confidence) if g else {},
            setup_skipped=g.setup_skipped if g else False,
        )

    # --- evidence ---------------------------------------------------------------------------

    def _evidence(
        self,
        user: User,
        track: str,
        disputes: dict[tuple[str, str], Dispute] | None = None,
        leave_out: _Used | None = None,
    ) -> Evidence:
        """`leave_out`: answers and rounds to read as if they didn't exist (the plan's evidence
        without what's new since a version, to see whether that changes anything: `_news`)."""
        return _evidence_from(self._evidence_rows(user, track), disputes, leave_out)

    def _evidence_rows(self, user: User, track: str) -> _EvidenceRows:
        """Everything the plan's evidence is read from, read once (Volume 17, prompt 9): the preview
        builds each skill's leave-out from these in memory."""
        # Ids and scores only: the plan needs one answer's feedback (at most two, for weak
        # questions), loaded by id below. Loading every whole row decoded all their feedback JSON
        # (docs/PERFORMANCE.md, "Real journeys").
        answers = self.db.execute(
            select(
                PracticeAnswer.id, PracticeAnswer.question_id, PracticeAnswer.score, *eligibility_columns()
            )
            .where(PracticeAnswer.user_id == user.id, PracticeAnswer.track == track)
            .order_by(PracticeAnswer.created_at)
        ).all()
        sessions = self.db.scalars(
            select(PracticeSession).where(
                PracticeSession.user_id == user.id,
                PracticeSession.mode == PracticeMode.QUESTIONS,
                PracticeSession.track == track,
            )
        ).all()
        voice_turns = self.db.execute(
            select(
                InterviewTurn.created_at,
                InterviewTurn.meta,
                InterviewTurn.session_id,
                InterviewTurn.answer_id,
            )
            .join(PracticeSession, PracticeSession.id == InterviewTurn.session_id)
            .where(
                PracticeSession.user_id == user.id,
                PracticeSession.track == track,
                InterviewTurn.role == TurnRole.CANDIDATE,
            )
        ).all()
        return _EvidenceRows(
            answers=[tuple(r) for r in answers],
            sessions=list(sessions),
            voice_turns=[tuple(r) for r in voice_turns],
            learn_passed=set(Learn(self.db).passed_units(user)),
        )

    # --- generation -------------------------------------------------------------------------

    def _level(self, goal: PracticeGoal | None) -> str:
        return START_LEVEL.get((goal.experience if goal else None) or "", "easy")

    def _pick_question(
        self, track: str, skill: str, level: str, ev: Evidence, avoid: set[str]
    ) -> Question | None:
        ids = questions_by_skill(track).get(skill, frozenset())
        pool = sorted(
            (q for q in questions_for(track) if q.id in ids and q.id not in avoid), key=lambda q: q.id
        )
        scores = [ev.best[q] for q in ids if q in ev.best]
        if scores and sum(scores) / len(scores) >= STRONG and level != "hard":
            level = LEVELS[LEVELS.index(level) + 1]  # doing well here: go a level up
        for lv in (level, *LEVELS):
            for q in pool:
                if q.difficulty == lv and q.id not in ev.answered:
                    return q
        return None

    def _generate(
        self, user: User, track: str, goal: PracticeGoal | None, ev: Evidence, avoid: set[str]
    ) -> list[Spec]:
        profile = CATALOG[track]
        formats = (
            list(goal.formats)
            if goal and goal.formats
            else ["written", *(["coding"] if profile.has_coding else [])]
        )
        level = self._level(goal)
        specs: list[Spec] = []
        used: set[str] = set(avoid)

        if ev.answers < 3 and not ev.baseline_done:
            specs.append(
                Spec(
                    "assessment",
                    "Baseline",
                    "Baseline check: 3 short questions",
                    f"There isn't enough evidence to tailor your plan yet ({ev.answers} "
                    f"{'answer' if ev.answers == 1 else 'answers'} so far). Three questions of different kinds show where to start.",
                    "Finish the baseline round by answering or skipping all three questions.",
                    12,
                    {"purpose": "baseline"},
                )
            )

        # Low scores first; then questions answered only with answers too short to score (no score:
        # they need a real try, but aren't ranked as the lowest).
        weak: list[tuple[int | None, str]] = [
            *sorted(((s, q) for q, s in ev.best.items() if s < WEAK and q not in used), key=lambda x: x[0]),
            *((None, q) for q in sorted(ev.answered - set(ev.best) - used)),
        ][:2]
        # Weak only because of answers whose feedback is disputed: not suggested, and said so.
        weak_ids = {q for _, q in weak}
        for qid in sorted(ev.disputed_question):
            would_be = ev.best_all.get(qid, WEAK) < WEAK or qid not in ev.best_all
            if qid in weak_ids or qid in used or not would_be:
                continue
            q, d = get_question(track, qid), ev.disputed_question[qid]
            if q is not None:
                ev.withheld.append(_withheld(f"retrying “{q.title}”", d, f"you disputed {d.what} {d.when}"))
        reviews: list[Spec] = []
        retries: list[Spec] = []
        for score, qid in weak:
            q = get_question(track, qid)
            last_id = ev.latest.get(qid)
            last = self.db.get(PracticeAnswer, last_id) if last_id and not ev.choosing_only else None
            if q is None or last_id is None or (last is None and not ev.choosing_only):
                continue
            feedback = (last.feedback or {}) if last is not None else {}
            labels = [p["label"] for p in feedback.get("points", []) if not p.get("covered")]
            # A point the learner disputes isn't cited (nor used to choose anything); the next ones are.
            for label in labels[:2]:
                hit = covering(ev.disputes, last_id, label)
                if hit is not None:
                    ev.withheld.append(
                        _withheld(
                            f"adding “{label}” to “{q.title}”", hit, f"you disputed this point {hit.when}"
                        )
                    )
            cited = [lb for lb in labels if covering(ev.disputes, last_id, lb) is None][:2]
            missed = [lb.lower() for lb in cited]
            basis = [{"answer_id": ev.best_answer.get(qid) or last_id, "criterion": OVERALL}]
            skill = question_skills(q)[0]
            if not reviews:
                reviews.append(
                    Spec(
                        "review",
                        skill,
                        f"Review feedback: {q.title}",
                        (
                            f"Your best score here is {score}/100."
                            if score is not None
                            else "Your answers here were too short to score."
                        )
                        + " Read what a strong answer includes before trying again.",
                        "Open your feedback and mark it reviewed. This one is self-reported.",
                        4,
                        {"question_id": qid, "answer_id": last_id},
                        [{"answer_id": last_id, "criterion": OVERALL}],
                    )
                )
            retries.append(
                Spec(
                    "retry",
                    skill,
                    f"Retry: {q.title}",
                    (
                        f"Your best score is {score}/100"
                        if score is not None
                        else "Your answers were too short to score"
                    )
                    + (f"; it missed {', '.join(missed[:2])}." if missed else "."),
                    "Submit a new answer to this question. Your earlier answers stay saved.",
                    6,
                    {"question_id": qid},
                    [*basis, *({"answer_id": last_id, "criterion": lb} for lb in cited)],
                )
            )
            used.add(qid)

        # Focus skills: chosen ones, then unpractised ones, then the lowest-scoring practised ones.
        skills = career_skills(track)
        by_skill = questions_by_skill(track)
        stats: dict[str, list[int]] = defaultdict(list)
        stat_answers: dict[str, list[str]] = defaultdict(list)
        for qid, s in ev.best.items():
            q = get_question(track, qid)
            for sk in question_skills(q) if q else ():
                stats[sk].append(s)
                if qid in ev.best_answer:
                    stat_answers[sk].append(ev.best_answer[qid])
        chosen = [s for s in (goal.focus_areas if goal else []) if s in skills]
        unpractised = [s for s in skills if not stats[s] and by_skill.get(s) and s not in chosen]
        lowest = sorted(
            (s for s in skills if stats[s] and s not in chosen), key=lambda s: sum(stats[s]) / len(stats[s])
        )
        focus: list[Spec] = []
        for s in [*chosen, *unpractised, *lowest]:
            if len(focus) >= 3:
                break
            q = self._pick_question(track, s, level, ev, used)
            if q is None:
                continue
            if s in chosen:
                why = f"You asked for help with {s}."
            elif not stats[s]:
                why = f"You haven't practised {s} yet."
            else:
                why = f"Your average best score in {s} is {round(sum(stats[s]) / len(stats[s]))}/100, your lowest."
            focus.append(
                Spec(
                    "question",
                    s,
                    q.title,
                    why,
                    "Submit an answer to this question. Any score counts; the score shows what to do next.",
                    6,
                    {"question_id": q.id},
                    []
                    if s in chosen or not stats[s]
                    else [{"answer_id": a, "criterion": OVERALL} for a in stat_answers[s]],
                )
            )
            used.add(q.id)

        # A short lesson before retrying a weak skill (or for a chosen focus skill), when one exists.
        lessons: list[Spec] = []
        for skill, why, derived in [
            *(
                (
                    r.skill,
                    "your answers in it are below 70",
                    [d for d in r.derived if d["criterion"] == OVERALL],
                )
                for r in retries
            ),
            *((s, "you asked for help with it", []) for s in chosen),
        ]:
            unit = next(
                (u for u in units_for(track) if u.skill == skill and u.id not in ev.learn_passed), None
            )
            if unit is not None and not lessons:
                lessons.append(
                    Spec(
                        "learn",
                        skill,
                        f"Learn: {unit.title}",
                        f"A {unit.minutes}-minute lesson on {skill}, because {why}.",
                        "Pass the lesson's comprehension check. Reading it alone doesn't count.",
                        unit.minutes,
                        {"unit_id": unit.id},
                        derived,
                    )
                )

        voice: list[Spec] = []
        if "voice" in formats and (ev.last_voice is None or ev.last_voice < _now() - timedelta(days=7)):
            q = next(
                (get_question(track, f.target["question_id"]) for f in focus), None
            ) or self._pick_question(track, skills[0], level, ev, used)
            if q is not None:
                voice.append(
                    Spec(
                        "voice",
                        question_skills(q)[0],
                        f"Answer out loud: {q.title}",
                        "You chose voice practice and haven't answered out loud in the last 7 days.",
                        "Answer this question by speaking in a one-question mock interview. You can fix the transcript before sending.",
                        6,
                        {"question_id": q.id},
                    )
                )

        coding: list[Spec] = []
        if profile.has_coding and "coding" in formats:
            done = (
                "Submit an attempt. The judge's verdict is recorded; passing isn't required."
                if self.judge_enabled
                else "Submit an attempt. This server can't run code, so it's saved without a verdict."
            )
            for rec in ProgressService(self.db).recommend(
                user, limit=2, facts=ev.code_facts, leave_out=ev.left_out_submissions, plan=True
            ):
                if rec.slug in used:
                    continue
                coding.append(
                    Spec(
                        "coding",
                        rec.topics[0] if rec.topics else "problem solving",
                        f"Solve: {rec.title}",
                        rec.reason,
                        done,
                        CODING_MINUTES.get(rec.difficulty, 20),
                        {"problem_slug": rec.slug},
                    )
                )
                used.add(rec.slug)

        mock: list[Spec] = []
        if (ev.answers >= 3 or ev.baseline_done) and (
            ev.last_mock is None or ev.last_mock < _now() - timedelta(days=14)
        ):
            mock.append(
                Spec(
                    "mock",
                    "Interview practice",
                    f"{profile.title} mock interview (5 questions)",
                    "A full round practises switching between question types against the clock"
                    + (
                        " and you haven't finished one yet."
                        if ev.last_mock is None
                        else "; your last one was over two weeks ago."
                    ),
                    "Finish all five questions. Ending early doesn't count, though your answers are still saved.",
                    20,
                    {"difficulty": level},
                )
            )

        coding_first = profile.has_coding and formats == ["coding"]
        order: list[Spec] = list(specs)
        if coding_first:
            order += coding[:1]
            coding = coding[1:]
        order += reviews
        # A lesson goes right before the retry it prepares for (or here, for a chosen skill).
        lesson_later = (
            bool(lessons) and len(retries) > 1 and retries[1].skill == lessons[0].skill != retries[0].skill
        )
        if not lesson_later:
            order += lessons
        order += retries[:1]
        order += focus[:1]
        order += coding[:1]
        if lesson_later:
            order += lessons
        order += retries[1:]
        order += focus[1:2]
        order += voice
        order += coding[1:]
        order += focus[2:]
        order += mock
        return order[:MAX_ITEMS]

    # --- plan lifecycle ---------------------------------------------------------------------

    def _latest(self, user: User, track: str) -> PracticePlan | None:
        return self.db.scalar(
            select(PracticePlan)
            .options(selectinload(PracticePlan.items))
            .where(PracticePlan.user_id == user.id, PracticePlan.track == track)
            .order_by(PracticePlan.version.desc())
            .limit(1)
        )

    def _avoid(self, user: User, track: str) -> set[str]:
        """Targets skipped or replaced in the last 7 days don't come straight back."""
        since = _now() - timedelta(days=7)
        rows = self.db.scalars(
            select(PlanItem)
            .join(PracticePlan, PracticePlan.id == PlanItem.plan_id)
            .where(
                PracticePlan.user_id == user.id,
                PracticePlan.track == track,
                PlanItem.status.in_(("skipped", "replaced")),
                PlanItem.resolved_at >= since,
            )
        ).all()
        return {str(i.target.get("question_id") or i.target.get("problem_slug")) for i in rows if i.target}

    def _new_version(
        self, user: User, track: str, prev: PracticePlan | None, changes: list[str]
    ) -> PracticePlan:
        goal = self._goal(user, track)
        # Worked out from the disputes as they stand, and checked again just before it's published:
        # a dispute made meanwhile (another tab, another device) is respected (docs/DISPUTES.md).
        for _ in range(3):
            disputes = Disputes(self.db, user.id).active(track)
            ev = self._evidence(user, track, disputes)
            specs = self._generate(user, track, goal, ev, self._avoid(user, track))
            if set(Disputes(self.db, user.id).active(track)) == set(disputes):
                break
        plan = PracticePlan(
            user_id=user.id,
            track=track,
            version=(prev.version + 1) if prev else 1,
            created_at=_now(),
        )
        for i, s in enumerate(specs):
            plan.items.append(
                PlanItem(
                    position=i,
                    kind=s.kind,
                    skill=s.skill,
                    title=s.title,
                    reason=s.reason,
                    completion=s.completion,
                    minutes=s.minutes,
                    target=s.target,
                    derived_from=s.derived,
                    status="pending",
                    created_at=_now(),
                )
            )
        plan.withheld = ev.withheld
        if prev is not None:
            old = {
                (
                    i.kind,
                    str(
                        i.target.get("question_id")
                        or i.target.get("problem_slug")
                        or i.target.get("unit_id")
                        or i.target.get("purpose")
                        or i.skill
                    ),
                ): i
                for i in prev.items
                if i.status == "pending"
            }
            new_keys = {s.key for s in specs}
            # Rounds the learner has open: dropping the activity one belongs to is said, not silent.
            open_rounds = [
                _aware(at)
                for at in self.db.scalars(
                    select(PracticeSession.started_at).where(
                        PracticeSession.user_id == user.id,
                        PracticeSession.mode == PracticeMode.QUESTIONS,
                        PracticeSession.track == track,
                        PracticeSession.status == InterviewStatus.IN_PROGRESS,
                    )
                ).all()
            ]
            for key, item in old.items():
                if key not in new_keys:
                    started = item.kind in _ROUND_ORDER and any(
                        at >= _aware(item.created_at) for at in open_rounds
                    )
                    qid = item.target.get("question_id")
                    if item.kind == "retry" and qid in ev.best and ev.best[qid] >= WEAK:
                        changes.append(f"Dropped “{item.title}”: your best score is now {ev.best[qid]}/100.")
                    elif item.kind == "assessment" and (ev.answers >= 3 or ev.baseline_done):
                        changes.append(
                            "Dropped the baseline check: there's now enough evidence to plan from."
                        )
                    else:
                        changes.append(f"Moved “{item.title}” out to make room for newer priorities.")
                    if started:
                        changes[-1] += (
                            " You'd started it: that round stays open, and what you answer in it is saved."
                        )
            for s in specs:
                if s.key not in old:
                    changes.append(f"Added “{s.title}”: {s.reason}")
        plan.changes = changes or ["No changes to your priorities."]
        self.db.add(plan)
        self.db.flush()
        return plan

    def _sync(self, user: User, plan: PracticePlan) -> list[str]:
        """Mark pending items done from evidence recorded after they were planned.

        One piece of evidence (a saved answer, or a finished round) completes at most one item, so
        one spoken answer can't finish both "answer out loud" and "answer this question", and its
        minutes aren't counted twice. Rounds are matched first and claim the answers inside them;
        single-answer items then need an answer no other item used.
        """
        done: list[str] = []
        used = self._used_evidence(plan)
        pending = [i for i in plan.items if i.status == "pending"]
        pending.sort(key=lambda i: (_ROUND_ORDER.get(i.kind, len(_ROUND_ORDER)), i.position))
        for item in pending:
            found = self._find_evidence(user, plan.track, item, used)
            if found:
                item.status = "done"
                item.evidence = found
                item.resolved_at = _now()
                used.answers.update(found.get("answer_ids", []))
                if found.get("answer_id"):
                    used.answers.add(found["answer_id"])
                if found.get("session_id"):
                    used.sessions.add(found["session_id"])
                done.append(f"Done: “{item.title}” ({found['label']}).")
        return done

    def _used_evidence(self, plan: PracticePlan) -> _Used:
        """The answers and rounds that already completed an item of this plan version."""
        used = _Used(set(), set())
        legacy: list[str] = []  # rounds recorded before items listed their answers
        for item in plan.items:
            ev = item.evidence or {}
            if item.status != "done":
                continue
            if ev.get("answer_id"):
                used.answers.add(ev["answer_id"])
            used.answers.update(ev.get("answer_ids", []))
            if ev.get("session_id"):
                used.sessions.add(ev["session_id"])
                if "answer_ids" not in ev:
                    legacy.append(ev["session_id"])
            if ev.get("submission_id"):
                used.submissions.add(ev["submission_id"])
            if ev.get("unit_id"):
                used.lessons.add(ev["unit_id"])
        if legacy:
            used.answers.update(self._round_answers(legacy))
        return used

    def _round_answers(self, session_ids: list[str]) -> list[str]:
        return [
            a
            for a in self.db.scalars(
                select(InterviewTurn.answer_id).where(
                    InterviewTurn.session_id.in_(session_ids), InterviewTurn.answer_id.is_not(None)
                )
            ).all()
            if a
        ]

    def _find_evidence(
        self, user: User, track: str, item: PlanItem, used: _Used | None = None
    ) -> dict[str, Any] | None:
        since = _aware(item.created_at)
        t = item.target or {}
        used = used or _Used(set(), set())
        if item.kind in ("question", "retry"):
            query = select(PracticeAnswer).where(
                PracticeAnswer.user_id == user.id,
                PracticeAnswer.track == track,
                PracticeAnswer.question_id == t.get("question_id"),
                PracticeAnswer.created_at >= since,
            )
            if used.answers:
                query = query.where(PracticeAnswer.id.not_in(used.answers))
            a = self.db.scalar(query.order_by(PracticeAnswer.created_at.desc()).limit(1))
            if a is None:
                return None
            # A too-short answer did the activity, but it isn't a scored result: don't quote its score.
            kind = feedback_eligibility(a.feedback)
            label = (
                f"answered, scored {a.score}/100"
                if kind == "scored"
                else "answered (too short to score)"
                if kind == "too_short"
                else "answered"
            )
            return {"answer_id": a.id, "label": label}
        if item.kind == "voice":
            rows = self.db.execute(
                select(InterviewTurn.session_id, InterviewTurn.answer_id, InterviewTurn.meta)
                .join(PracticeSession, PracticeSession.id == InterviewTurn.session_id)
                .where(
                    PracticeSession.user_id == user.id,
                    PracticeSession.track == track,
                    InterviewTurn.role == TurnRole.CANDIDATE,
                    InterviewTurn.created_at >= since,
                )
                .order_by(InterviewTurn.created_at)
            ).all()
            hit = next(
                (
                    (sid, aid)
                    for sid, aid, meta in rows
                    if (meta or {}).get("source") in ("voice", "mixed")
                    and sid not in used.sessions
                    and aid not in used.answers
                ),
                None,
            )
            if hit is None:
                return None
            return {
                "session_id": hit[0],
                "answer_ids": [hit[1]] if hit[1] else [],
                "label": "answered out loud",
            }
        if item.kind in ("mock", "assessment"):
            sessions = self.db.scalars(
                select(PracticeSession).where(
                    PracticeSession.user_id == user.id,
                    PracticeSession.mode == PracticeMode.QUESTIONS,
                    PracticeSession.track == track,
                    PracticeSession.status == InterviewStatus.COMPLETED,
                    PracticeSession.started_at >= since,
                )
            ).all()
            want = "baseline" if item.kind == "assessment" else "practice"
            s = next(
                (
                    s
                    for s in sessions
                    if s.id not in used.sessions
                    and (s.plan or {}).get("purpose", "practice") == want
                    and (want == "baseline" or len((s.plan or {}).get("question_ids", [])) >= 5)
                ),
                None,
            )
            if s is None:
                return None
            return {"session_id": s.id, "answer_ids": self._round_answers([s.id]), "label": "round finished"}
        if item.kind == "learn":
            ev = self.db.scalar(
                select(LearnEvent)
                .where(
                    LearnEvent.user_id == user.id,
                    LearnEvent.unit_id == t.get("unit_id"),
                    LearnEvent.kind == "check_passed",
                    LearnEvent.created_at >= since,
                )
                .limit(1)
            )
            return (
                {"unit_id": ev.unit_id, "label": f"passed the check on version {ev.unit_version}"}
                if ev
                else None
            )
        if item.kind == "coding":
            row = self.db.execute(
                select(Submission)
                .join(Problem, Problem.id == Submission.problem_id)
                .where(
                    Submission.user_id == user.id,
                    Problem.slug == t.get("problem_slug"),
                    Submission.mode == SubmissionMode.SUBMIT,
                    # The judge's own failure isn't the learner's attempt judged (Volume 16, prompt 7).
                    Submission.status != SubmissionStatus.INTERNAL_ERROR,
                    Submission.created_at >= since,
                )
                .order_by(Submission.created_at.desc())
                .limit(1)
            ).first()
            if not row:
                return None
            sub = row[0]
            if sub.status == SubmissionStatus.PASSED:
                label = "submitted; passed"
            elif sub.status in JUDGED:
                label = "submitted; didn't pass yet"
            elif self.judge_enabled:
                label = "submitted; waiting for the judge"
            else:
                label = "submitted; saved, not judged here"
            return {"submission_id": sub.id, "label": label}
        return None  # review: only the learner can mark it

    # --- new evidence ------------------------------------------------------------------------

    def _new_checks(
        self, user: User, track: str, since: datetime, used: _Used
    ) -> tuple[list[tuple[LearnEvent, Any]], int]:
        """Lesson checks passed since this version (Volume 17, prompt 3): each unit of this career
        passed on its current version, once, that no activity used and that wasn't already passed
        before the version (it was evidence then). A pass on a version the lesson has since replaced
        is counted apart, to be said. Reading, starting or a failed check attempt is never here."""
        units = {u.id: u for u in units_for(track)}
        rows = self.db.scalars(
            select(LearnEvent)
            .where(
                LearnEvent.user_id == user.id,
                LearnEvent.kind == "check_passed",
                LearnEvent.unit_id.in_(list(units)),
            )
            .order_by(LearnEvent.created_at, LearnEvent.id)
        ).all()
        before = {e.unit_id for e in rows if _aware(e.created_at) < since}
        out: list[tuple[LearnEvent, Any]] = []
        seen: set[str] = set()
        older = 0
        for e in rows:
            if _aware(e.created_at) < since or e.unit_id in used.lessons or e.unit_id in before:
                continue
            unit = units[e.unit_id]
            if e.unit_version != unit.version:
                older += 1
            elif e.unit_id not in seen:
                seen.add(e.unit_id)
                out.append((e, unit))
        return out, older

    def _news(
        self,
        user: User,
        track: str,
        plan: PracticePlan,
        disputes: dict[tuple[str, str], Dispute],
        ev: Evidence,
        read: list[str] | None = None,
        read_lessons: list[dict[str, Any]] | None = None,
        evidence_rows: _EvidenceRows | None = None,
    ) -> PlanNews | None:
        """What's new since this version that would change it (docs/PLAN_UPDATES.md), or None.
        `read`, when given, gets the ids of the judged submissions it counted (for the version an
        update makes from them).

        New: scored answers and finished question rounds recorded since the version was made that
        no activity in it used. Not counted: answers too short to score and answers whose feedback
        as a whole is disputed (the planner doesn't use either). Whether it would change anything
        is the planner's own answer: it plans twice, from the evidence with and without what's
        new, and the update is offered only when what's chosen differs. Reading never saves.

        Each skill's line (Volume 17, prompt 9) is the planner's answer too: it plans once more per
        skill without that skill's new evidence, up to SKILLS_ASKED_ALONE skills, and once for the
        rest together. `evidence_rows` are the evidence's rows, already read for `ev`; every plan here is
        made in memory from them and from the code's facts, read once.
        """
        since = _aware(plan.created_at)
        used = self._used_evidence(plan)
        rows = self.db.execute(
            select(
                PracticeAnswer.id,
                PracticeAnswer.question_id,
                PracticeAnswer.score,
                PracticeAnswer.revises_answer_id,
                *eligibility_columns(),
            )
            .where(
                PracticeAnswer.user_id == user.id,
                PracticeAnswer.track == track,
                PracticeAnswer.created_at >= since,
            )
            .order_by(PracticeAnswer.created_at)
        ).all()
        fresh: list[tuple[str, str, int, bool]] = []
        too_short = disputed = 0
        for answer_id, qid, score, revises, level, words in rows:
            if answer_id in used.answers:
                continue
            if (answer_id, OVERALL) in disputes:
                disputed += 1
            elif (kind := eligibility(level, words)) == "too_short":
                too_short += 1
            elif kind == "scored":
                fresh.append((answer_id, qid, score, revises is not None))
        rounds = [
            r
            for r in self.db.scalars(
                select(PracticeSession)
                .where(
                    PracticeSession.user_id == user.id,
                    PracticeSession.mode == PracticeMode.QUESTIONS,
                    PracticeSession.track == track,
                    PracticeSession.status == InterviewStatus.COMPLETED,
                    PracticeSession.ended_at >= since,
                )
                .order_by(PracticeSession.ended_at)
            ).all()
            if r.id not in used.sessions
        ]
        # Judged submissions no activity used (Volume 14, prompt 2): a verdict on the learner's code,
        # to a problem or (Volume 16, prompt 7) a debugging exercise. Runs (public tests only) and
        # attempts only saved aren't evidence; nor is a submission the judge failed to run (its own
        # problem, not the learner's code), which is named as not counted.
        subs: list[tuple[Submission, Problem]] = []
        broken = 0
        if CATALOG[track].has_coding:
            for sub, problem in self.db.execute(
                select(Submission, Problem)
                .join(Problem, Problem.id == Submission.problem_id)
                .where(
                    Submission.user_id == user.id,
                    Submission.mode == SubmissionMode.SUBMIT,
                    Submission.status.in_([*JUDGED, SubmissionStatus.INTERNAL_ERROR]),
                    Submission.created_at >= since,
                    Problem.kind.in_(("problem", "debug")),
                )
                .order_by(Submission.created_at, Submission.id)
            ).all():
                if sub.id in used.submissions:
                    continue
                if sub.status == SubmissionStatus.INTERNAL_ERROR:
                    broken += 1
                else:
                    subs.append((sub, problem))
        checks, older = self._new_checks(user, track, since, used)
        if not fresh and not rounds and not subs and not checks:
            return None
        goal = self._goal(user, track)
        avoid = self._avoid(user, track)
        leave_out = _Used(
            {a[0] for a in fresh},
            {r.id for r in rounds},
            {sub.id for sub, _ in subs},
            {unit.id for _, unit in checks},
        )
        ev_rows = evidence_rows if evidence_rows is not None else self._evidence_rows(user, track)
        code_rows = ProgressService(self.db).fact_rows(user, plan=True) if CATALOG[track].has_coding else None

        def ask(leave: _Used | None) -> list[Spec]:
            """The planner's choice from the evidence leaving out what's named, made in memory."""
            e = replace(ev) if leave is None else _evidence_from(ev_rows, disputes, leave)
            e.withheld, e.choosing_only = [], True
            if code_rows is not None:
                e.code_facts = build_facts(code_rows, leave.submissions if leave else None, plan=True)
            return self._generate(user, track, goal, e, avoid)

        with_new = ask(None)
        without = ask(leave_out)
        if {s.key for s in with_new} == {s.key for s in without}:
            return None  # nothing the planner chooses would change: the plan stays, unoffered
        entries: list[NewEvidence] = []
        # Grouped by skill for the preview (Volume 16, prompt 7), oldest first within each kind, with
        # what each skill's own new evidence is, to plan without it (Volume 17, prompt 9).
        groups: dict[str, list[_Piece]] = {}
        own: dict[str, _Used] = {}

        def put(skill: str, piece: _Piece) -> _Used:
            groups.setdefault(skill, []).append(piece)
            return own.setdefault(skill, _Used(set(), set()))

        for answer_id, qid, score, retry in fresh:
            q = get_question(track, qid)
            title = q.title if q else "A question no longer in the bank"
            skill = question_skills(q)[0] if q else "Other questions"
            put(skill, _Piece("answer", title, ref=answer_id, score=score)).answers.add(answer_id)
            entries.append(
                NewEvidence(
                    kind="retry" if retry else "answer",
                    title=title,
                    score=score,
                    skill=skill,
                    href=f"/careers/{track}/questions/{qid}?answer={answer_id}",
                )
            )
        for r in rounds:
            n = len((r.plan or {}).get("question_ids", []))
            baseline = (r.plan or {}).get("purpose") == "baseline"
            title = (
                "Baseline check" if baseline else f"Practice round ({_plural(n, 'question', 'questions')})"
            )
            skill = "Baseline" if baseline else "Interview practice"  # the skill of the activity it ends
            put(skill, _Piece("round", title, ref=r.id)).sessions.add(r.id)
            entries.append(
                NewEvidence(kind="round", title=title, score=None, skill=skill, href=f"/interviews/{r.id}")
            )
        for sub, problem in subs:
            passed = sub.status == SubmissionStatus.PASSED
            skill = _code_skill(problem)
            exercise = problem.kind == "debug"
            for topic in _code_skills(problem):  # each topic the planner reads it for
                piece = _Piece(
                    "submission",
                    problem.title,
                    ref=sub.id,
                    passed=passed,
                    verdict=VERDICT[sub.status],
                    exercise=exercise,
                )
                put(topic, piece).submissions.add(sub.id)
            entries.append(
                NewEvidence(
                    kind="submission",
                    title=problem.title,
                    score=None,
                    verdict="passed" if passed else "not passed",
                    verdict_detail=VERDICT[sub.status],
                    exercise=exercise,
                    skill=skill,
                    href=f"/history/submissions/{sub.id}",
                )
            )
        for _check, unit in checks:
            skill = unit.skill or "Lessons"
            put(skill, _Piece("lesson", unit.title, ref=unit.id)).lessons.add(unit.id)
            entries.append(
                NewEvidence(
                    kind="lesson", title=unit.title, score=None, skill=skill, href=f"/learn/{unit.id}"
                )
            )
        names = list(groups)
        if len(names) == 1:
            alone = {names[0]: without}  # its own new evidence is all of it: no plan to make again
            past: list[str] = []
        else:
            # One more than the bound is asked about alone: the rest together would be that one.
            cut = SKILLS_ASKED_ALONE if len(names) > SKILLS_ASKED_ALONE + 1 else len(names)
            alone = {name: ask(own[name]) for name in names[:cut]}
            past = names[cut:]
        rest = None
        if past:
            rest_out = _Used(set(), set())
            for name in past:
                for mine, theirs in (
                    (rest_out.answers, own[name].answers),
                    (rest_out.sessions, own[name].sessions),
                    (rest_out.submissions, own[name].submissions),
                    (rest_out.lessons, own[name].lessons),
                ):
                    mine |= theirs
            rest = (past, ask(rest_out))
        total = len(fresh) + len(rounds) + len(subs) + len(checks)
        by_skill = self._by_skill(groups, with_new, without, alone, rest, total)
        if read is not None:
            read.extend(sub.id for sub, _ in subs)
        if read_lessons is not None:
            read_lessons.extend({"unit_id": unit.id, "version": e.unit_version} for e, unit in checks)
        not_passed = sum(sub.status != SubmissionStatus.PASSED for sub, _ in subs)
        retries = sum(a[3] for a in fresh)
        below = sum(a[2] < WEAK for a in fresh)
        not_counted = []
        if too_short:
            not_counted.append(
                f"{_plural(too_short, 'answer', 'answers')} too short to score {'isn’t' if too_short == 1 else 'aren’t'} counted."
            )
        if disputed:
            not_counted.append(
                f"{_plural(disputed, 'answer', 'answers')} whose feedback you disputed {'isn’t' if disputed == 1 else 'aren’t'} counted."
            )
        if older:
            not_counted.append(
                f"{_plural(older, 'lesson check', 'lesson checks')} passed on a version the lesson has since "
                f"replaced {'isn’t' if older == 1 else 'aren’t'} counted: pass its current version."
            )
        if broken:
            not_counted.append(
                f"{_plural(broken, 'submission', 'submissions')} the judge couldn't run {'isn’t' if broken == 1 else 'aren’t'} "
                "counted: that was a problem on the judge's side, not your code."
            )
        return PlanNews(
            text=news_text(
                len(fresh), retries, below, len(rounds), "this plan", len(subs), not_passed, len(checks)
            ),
            answers=len(fresh),
            retries=retries,
            below=below,
            rounds=len(rounds),
            submissions=len(subs),
            not_passed=not_passed,
            lessons=len(checks),
            entries=entries[:10],
            not_counted=not_counted,
            by_skill=by_skill,
            rule=CODE_RULE if subs else None,
        )

    @staticmethod
    def _by_skill(
        groups: dict[str, list[_Piece]],
        with_new: list[Spec],
        without: list[Spec],
        alone: dict[str, list[Spec]],
        rest: tuple[list[str], list[Spec]] | None,
        total: int,
    ) -> list[SkillNews]:
        """One sentence per skill: what the next version would suggest, or stop suggesting, because of
        that skill's new evidence alone (Volume 17, prompt 9): the plan with all of what's new,
        compared with the plan without that skill's (`alone`). Past the bound, the remaining skills
        are said together (`rest`). What no single skill moves, but all of it together does, is said
        once, for all of it together."""
        keys_with = {s.key for s in with_new}

        def moved(other: list[Spec]) -> tuple[list[Spec], list[Spec]]:
            keys_other = {s.key for s in other}
            return (
                [s for s in with_new if s.key not in keys_other],
                [s for s in other if s.key not in keys_with],
            )

        explained: set[tuple[str, str]] = set()
        out: list[SkillNews] = []
        for skill, plan in alone.items():
            came_in, left = moved(plan)
            explained.update(s.key for s in [*came_in, *left])
            out.append(
                SkillNews(
                    skill=skill,
                    count=len(groups[skill]),
                    text=_skill_sentence(skill, groups[skill], came_in, left),
                )
            )
        if rest is not None:
            names, plan = rest
            came_in, left = moved(plan)
            explained.update(s.key for s in [*came_in, *left])
            pieces = list({(p.kind, p.ref): p for n in names for p in groups[n]}.values())
            out.append(
                SkillNews(
                    skill=None,
                    skills=names,
                    count=len(pieces),
                    text=_skill_sentence(_together(names), pieces, came_in, left, alone="together"),
                )
            )
        came_in, left = moved(without)
        together = _moves(
            [s for s in came_in if s.key not in explained],
            [s for s in left if s.key not in explained],
            also=True,
        )
        if together:
            out.append(SkillNews(skill=None, count=total, text=f"From all of it together, {together}."))
        return out

    def update(self, user: User, track: str | None, seen: int, minutes: int) -> PlanOut:
        """The next version, from all the evidence, because the learner asked: bound to the version
        they saw. If another tab or device made a newer one first, nothing is made here and the
        reply says which version is current."""
        t = self._track(user, track)
        plan = self._latest(user, t)
        if plan is None or plan.version != seen:
            raise self._moved_on(plan)
        done = self._sync(user, plan)
        disputes = Disputes(self.db, user.id).active(t)
        read: list[str] = []
        read_lessons: list[dict[str, Any]] = []
        rows = self._evidence_rows(user, t)
        news = self._news(user, t, plan, disputes, _evidence_from(rows, disputes), read, read_lessons, rows)
        if news is None and not done:
            # Nothing new changes it (anymore): the same version, unchanged.
            self.db.commit()
            return self._out(user, t, plan, minutes)
        why = list(done)
        if news is not None:
            n = news
            why.insert(
                0,
                "Updated when you asked: "
                + news_text(
                    n.answers,
                    n.retries,
                    n.below,
                    n.rounds,
                    f"version {plan.version}",
                    n.submissions,
                    n.not_passed,
                    n.lessons,
                ),
            )
        self.db.flush()
        try:
            new = self._new_version(user, t, plan, why)
            new.read_submissions = read  # the version's own record of what this update read, by id
            new.read_lessons = read_lessons  # and the lesson checks, by unit and version (prompt 3)
            self.db.commit()
        except IntegrityError:
            # Another request saved this version number first.
            self.db.rollback()
            raise self._moved_on(self._latest(user, t)) from None
        return self._out(user, t, new, minutes)

    def _moved_on(self, current: PracticePlan | None) -> ConflictError:
        version = current.version if current else None
        return ConflictError(
            f"Your plan was already updated, in another tab or on another device: it's now version {version}."
            if version
            else "There's no plan to update yet. Open your plan first.",
            code="plan_changed",
            details={"version": version},
        )

    def plan(self, user: User, track: str | None, minutes: int) -> PlanOut:
        t = self._track(user, track)
        plan = self._latest(user, t)
        if plan is None:
            goal = self._goal(user, t)
            first = (
                "A starter plan from your goals."
                if goal and not goal.setup_skipped
                else "A starter plan for your career. Add goals any time to tailor it."
            )
            plan = self._save_version(user, t, lambda: self._new_version(user, t, None, [first]))
        else:
            done = self._sync(user, plan)
            goal = self._goal(user, t)
            goals_changed = goal is not None and _aware(goal.updated_at) > _aware(plan.created_at)
            open_items = [i for i in plan.items if i.status == "pending"]
            if done or goals_changed or not open_items:
                why = list(done)
                if goals_changed:
                    why.append("Your goals changed, so priorities were recalculated.")
                if not open_items and not done:
                    why.append("Everything in the last plan was done or set aside, so here's what's next.")
                self.db.flush()
                previous = plan
                plan = self._save_version(user, t, lambda: self._new_version(user, t, previous, why))
            else:
                self.db.commit()
            plan = self._latest(user, t) or plan
        return self._out(user, t, plan, minutes)

    def _save_version(self, user: User, track: str, build: Callable[[], PracticePlan]) -> PracticePlan:
        """Build and save a new plan version, or use the one another request saved first. Two
        tabs opening the plan at the same moment both build the same next version; the second
        hits the unique (user, track, version) constraint. That isn't an error: the plan exists."""
        try:
            plan = build()
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._latest(user, track)
            if existing is None:
                raise
            return existing
        return plan

    def _item(self, user: User, item_id: str) -> PlanItem:
        item = self.db.scalar(
            select(PlanItem).options(selectinload(PlanItem.plan)).where(PlanItem.id == item_id)
        )
        # The plan can read as missing too: with row-level security another learner's plan is
        # invisible (app/db/rls.py), and that's a 404 like any other item that isn't yours.
        if item is None or item.plan is None or item.plan.user_id != user.id:
            raise NotFoundError("Activity not found")
        latest = self._latest(user, item.plan.track)
        if latest is None or latest.id != item.plan_id or item.status != "pending":
            raise ConflictError("This activity is no longer open. Refresh your plan.", code="activity_closed")
        return item

    def skip(self, user: User, item_id: str) -> PlanItem:
        item = self._item(user, item_id)
        item.status = "skipped"
        item.resolved_at = _now()
        self.db.commit()
        return item

    def mark_reviewed(self, user: User, item_id: str) -> PlanItem:
        item = self._item(user, item_id)
        if item.kind != "review":
            raise ConflictError(
                "Only reading feedback can be marked done by hand; everything else completes from your work.",
                code="not_self_reportable",
            )
        item.status = "done"
        item.evidence = {"label": "marked reviewed (self-reported)"}
        item.resolved_at = _now()
        self.db.commit()
        return item

    def replace(self, user: User, item_id: str) -> PlanItem:
        item = self._item(user, item_id)
        if item.kind not in ("question", "voice", "coding"):
            raise ConflictError("This activity has no alternative to swap in.", code="no_alternative")
        track = item.plan.track
        ev = self._evidence(user, track, Disputes(self.db, user.id).active(track))
        taken = {
            str(i.target.get("question_id") or i.target.get("problem_slug"))
            for i in item.plan.items
            if i.target
        }
        taken |= self._avoid(user, track)
        spec: Spec | None = None
        if item.kind in ("question", "voice"):
            q = self._pick_question(track, item.skill, self._level(self._goal(user, track)), ev, taken)
            if q is not None:
                title = f"Answer out loud: {q.title}" if item.kind == "voice" else q.title
                spec = Spec(
                    item.kind,
                    item.skill,
                    title,
                    f"Swapped in for “{item.title}”, same skill ({item.skill}).",
                    item.completion,
                    item.minutes,
                    {"question_id": q.id},
                )
        else:
            for rec in ProgressService(self.db).recommend(user, limit=6):
                # Never longer than what it replaces: a swap mustn't quietly overrun the time chosen.
                if rec.slug not in taken and CODING_MINUTES.get(rec.difficulty, 20) <= item.minutes:
                    spec = Spec(
                        "coding",
                        rec.topics[0] if rec.topics else item.skill,
                        f"Solve: {rec.title}",
                        rec.reason,
                        item.completion,
                        CODING_MINUTES.get(rec.difficulty, 20),
                        {"problem_slug": rec.slug},
                    )
                    break
        if spec is None:
            raise ConflictError(
                f"There's no other activity like this one that fits in {item.minutes} minutes right now. "
                "This one stays in your plan; you can skip it instead.",
                code="no_alternative",
            )
        item.status = "replaced"
        item.resolved_at = _now()
        new = PlanItem(
            position=item.position,
            kind=spec.kind,
            skill=spec.skill,
            title=spec.title,
            reason=spec.reason,
            completion=spec.completion,
            minutes=spec.minutes,
            target=spec.target,
            status="pending",
            created_at=_now(),
        )
        item.plan.items.append(new)
        self.db.commit()
        return new

    # --- output -----------------------------------------------------------------------------

    def _item_out(self, track: str, i: PlanItem, disputes: dict[tuple[str, str], Dispute]) -> PlanItemOut:
        t = i.target or {}
        href: str | None = None
        rnd: RoundStart | None = None
        if i.kind in ("question", "retry"):
            href = f"/careers/{track}/questions/{t['question_id']}"
        elif i.kind == "review":
            href = f"/careers/{track}/questions/{t['question_id']}?answer={t.get('answer_id', '')}"
        elif i.kind == "coding":
            href = f"/problems/{t['problem_slug']}"
        elif i.kind == "learn":
            href = f"/learn/{t['unit_id']}"
        elif i.kind == "voice":
            rnd = RoundStart(track=track, question_ids=[t["question_id"]], duration_minutes=10)
        elif i.kind == "mock":
            rnd = RoundStart(track=track, difficulty=t.get("difficulty", "easy"), duration_minutes=15)
        elif i.kind == "assessment":
            rnd = RoundStart(track=track, purpose="baseline", duration_minutes=15)
        return PlanItemOut(
            id=i.id,
            position=i.position,
            kind=i.kind,
            skill=i.skill,
            title=i.title,
            reason=i.reason,
            completion=i.completion,
            minutes=i.minutes,
            status=i.status,
            evidence=(i.evidence or {}).get("label"),
            href=href,
            round=rnd,
            can_mark_reviewed=i.kind == "review" and i.status == "pending",
            can_replace=i.kind in ("question", "voice", "coding") and i.status == "pending",
            created_at=i.created_at,
            resolved_at=i.resolved_at,
            disputed=dispute_note(first_disputed(disputes, i.derived_from)),
        )

    def _today(self, items: list[PlanItemOut], minutes: int) -> TodayOut:
        pending = [i for i in items if i.status == "pending"]
        if not pending:
            return TodayOut(
                minutes_available=minutes,
                primary=None,
                follow_up=None,
                session_minutes=0,
                note="Nothing open right now. Your plan refreshes as you practise.",
            )
        fits = [i for i in pending if i.minutes <= minutes]
        note = None
        if fits:
            primary = fits[0]
            if primary is not pending[0]:
                note = f"Your next activity takes about {pending[0].minutes} minutes, so here's one that fits {minutes}."
        else:
            primary = min(pending, key=lambda i: i.minutes)
            note = f"Nothing fits in {minutes} minutes; this is the shortest activity (about {primary.minutes} minutes)."
        left = minutes - primary.minutes
        follow = next((i for i in pending if i is not primary and i.minutes <= left), None)
        return TodayOut(
            minutes_available=minutes,
            primary=primary,
            follow_up=follow,
            session_minutes=primary.minutes + (follow.minutes if follow else 0),
            note=note,
        )

    def _assessment(self, user: User, track: str, ev: Evidence, goal: PracticeGoal | None) -> AssessmentOut:
        stats: dict[str, list[int]] = defaultdict(list)
        answers_per: dict[str, int] = defaultdict(int)
        counts: dict[str, int] = defaultdict(int)
        for a in self.db.scalars(
            select(PracticeAnswer.question_id).where(
                PracticeAnswer.user_id == user.id, PracticeAnswer.track == track
            )
        ).all():
            counts[a] += 1
        for qid, s in ev.best.items():
            q = get_question(track, qid)
            for sk in question_skills(q) if q else ():
                stats[sk].append(s)
                answers_per[sk] += counts[qid]
        evaluated = [
            EvaluatedSkill(
                skill=sk, questions=len(v), answers=answers_per[sk], average_best_score=round(sum(v) / len(v))
            )
            for sk, v in sorted(stats.items(), key=lambda kv: -len(kv[1]))
        ]
        coding = None
        if CATALOG[track].has_coding:
            statuses = self.db.scalars(
                select(Submission.status).where(
                    Submission.user_id == user.id, Submission.mode == SubmissionMode.SUBMIT
                )
            ).all()
            coding = CodingEvidence(
                judge_available=self.judge_enabled,
                judged_attempts=sum(s in JUDGED for s in statuses),
                passed=sum(s == SubmissionStatus.PASSED for s in statuses),
                saved_not_judged=sum(
                    s in (SubmissionStatus.QUEUED, SubmissionStatus.RUNNING) for s in statuses
                ),
            )
        building = ev.answers < 3 and not ev.baseline_done
        note = (
            f"Building your baseline: {ev.answers} of 3 answers so far. Until then the plan starts broad."
            if building
            else f"Based on {ev.answers} answers across {len(ev.answered)} questions. Self-ratings, rubric scores and "
            "code results are shown separately and never combined into one readiness number."
        )
        return AssessmentOut(
            state="building_baseline" if building else "baseline_ready",
            note=note,
            self_reported=[
                SelfRating(skill=k, rating=v) for k, v in (goal.confidence if goal else {}).items()
            ],
            evaluated=evaluated,
            coding=coding,
        )

    def _out(self, user: User, track: str, plan: PracticePlan, minutes: int) -> PlanOut:
        goal = self._goal(user, track)
        disputes = Disputes(self.db, user.id).active(track)
        items = [
            self._item_out(track, i, disputes)
            for i in sorted(plan.items, key=lambda i: (i.position, _aware(i.created_at)))
        ]
        week = _now() - timedelta(days=7)
        recent = self.db.scalars(
            select(PlanItem)
            .join(PracticePlan, PracticePlan.id == PlanItem.plan_id)
            .where(
                PracticePlan.user_id == user.id,
                PracticePlan.track == track,
                PlanItem.status == "done",
                PlanItem.resolved_at >= week,
            )
        ).all()
        rows = self._evidence_rows(user, track)
        ev = _evidence_from(rows, disputes)
        news = self._news(user, track, plan, disputes, ev, evidence_rows=rows)
        days = (goal.target_date - _now().date()).days if goal and goal.target_date else None
        return PlanOut(
            track=track,
            career_title=CATALOG[track].title,
            version=plan.version,
            created_at=plan.created_at,
            changes=list(plan.changes or []),
            withheld=[
                Withheld(
                    text=w["text"],
                    href=w["href"],
                    reinstated=(w.get("answer_id"), w.get("criterion")) not in disputes,
                )
                for w in plan.withheld or []
            ],
            items=items,
            progress=PlanProgress(
                done_this_week=len(recent),
                minutes_this_week=sum(i.minutes for i in recent),
                weekly_minutes=(
                    goal.weekly_minutes if goal and goal.weekly_minutes else DEFAULT_WEEKLY_MINUTES
                ),
                done_in_plan=sum(i.status == "done" for i in items),
                open_in_plan=sum(i.status == "pending" for i in items),
            ),
            today=self._today(items, minutes),
            assessment=self._assessment(user, track, ev, goal),
            goals_saved=goal is not None,
            target_date=goal.target_date if goal else None,
            days_to_interview=days if days is not None and days >= 0 else None,
            news=news,
            read_submissions=self._read_submissions(user, plan),
            read_lessons=_read_lessons(track, plan),
            evidence_read=EVIDENCE_READ.format(
                career=CATALOG[track].title, code=EVIDENCE_READ_CODE if CATALOG[track].has_coding else ""
            ),
        )

    def _read_submissions(self, user: User, plan: PracticePlan) -> list[ReadSubmission] | None:
        """The submissions the update that made this version read, as it recorded them by id (one
        statement, only for such a version). One no longer stored is still listed, by id."""
        ids = plan.read_submissions
        if ids is None:
            return None  # not made by an update that recorded this: reads as before
        if not ids:
            return []
        rows = {
            sub_id: (status, title, kind)
            for sub_id, status, title, kind in self.db.execute(
                select(Submission.id, Submission.status, Problem.title, Problem.kind)
                .join(Problem, Problem.id == Submission.problem_id)
                .where(Submission.user_id == user.id, Submission.id.in_(ids))
            ).all()
        }
        out = []
        for sub_id in ids:
            row = rows.get(sub_id)
            if row is None:
                out.append(ReadSubmission(id=sub_id, title=None))
                continue
            status, title, kind = row
            out.append(
                ReadSubmission(
                    id=sub_id,
                    title=title,
                    verdict="passed" if status == SubmissionStatus.PASSED else "not passed",
                    exercise=kind == "debug",
                    href=f"/history/submissions/{sub_id}",
                )
            )
        return out

    def item_out(self, item: PlanItem) -> PlanItemOut:
        track = item.plan.track
        return self._item_out(track, item, Disputes(self.db, item.plan.user_id).active(track))
