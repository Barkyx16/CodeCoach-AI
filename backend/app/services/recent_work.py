"""Recent work to continue (Volume 11, prompt 1; docs/CONTINUE.md): a few of the caller's own
records, newest first, from the times the records really keep. Only ids, titles and timestamps
are read: no note body, story text, transcript or terms. An interview in progress comes first.
Each kind of record is read on its own, in a savepoint: one that fails is named in `unavailable`
and the others are still listed. Archived records (and kits of archived applications) aren't
listed: archiving takes a record out of active views (docs/ARCHIVE.md).

Scenario runs in progress and test-design runs (Volume 19, prompt 6): a scenario run left in progress
(a finished one has nothing to continue), and a test-design run waiting for the judge, or finished in
the last week, in the words its run list uses. Neither's steps, cases nor report are read: a run's
result is two numbers taken from its report in the query, never the report itself.

Debugging exercises tried and not fixed, and a scenario run's last step (Volume 20, prompt 6): an
exercise none of whose submitted attempts passed (the plan's rule for "not fixed"), with its newest
attempt in the last week, is listed as "tried" at that attempt's time, with its verdict in the
exercise page's words; only titles, verdicts and times are read, never code. A scenario run in
progress is listed at its last step's time, taken from the run in the query (nothing else of the
steps is read), or at its start when it has none, and says which. Both are listed only for a page
that says it can show them (`shows`): a page cached from before gets what it did.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, func, literal_column, select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationEvent,
    ExecutionResult,
    ExperienceEntry,
    InterviewKit,
    InterviewStatus,
    Note,
    OfferComparison,
    PracticeMode,
    PracticeSession,
    Problem,
    ScenarioAttempt,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    TestDesignRun,
    User,
)
from app.services.activity import career_title

logger = logging.getLogger("codecoach.recent_work")
MAX_LIMIT = 12
# A test-design run that's no longer waiting has nothing to continue; its report stays a week here.
FINISHED_RUN_DAYS = 7
# A debugging exercise not fixed stays while its newest attempt is less than a week old.
TRIED_DAYS = 7
# What a page can show beyond the eight kinds it showed before Volume 20 (prompt 6). A page that
# doesn't say gets exactly what it did, so one cached from before never meets a kind it can't open.
SHOWS = frozenset({"debug_exercise", "last_step"})


@dataclass(frozen=True)
class Options:
    judge_enabled: bool = False
    shows: frozenset[str] = field(default_factory=frozenset)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _interviews(db: Session, user: User, n: int, _opts: Options) -> list[dict]:
    now = datetime.now(UTC)
    rows = db.execute(
        select(
            PracticeSession.id,
            PracticeSession.mode,
            PracticeSession.status,
            PracticeSession.started_at,
            PracticeSession.ended_at,
            PracticeSession.deadline_at,
            PracticeSession.track,
            Problem.title,
        )
        .outerjoin(Problem, Problem.id == PracticeSession.problem_id)
        .where(
            PracticeSession.user_id == user.id,
            PracticeSession.mode.in_((PracticeMode.INTERVIEW, PracticeMode.QUESTIONS)),
        )
        .order_by(func.coalesce(PracticeSession.ended_at, PracticeSession.started_at).desc())
        .limit(n)
    ).all()
    out = []
    for sid, mode, status, started, ended, deadline, track, problem in rows:
        title = (
            f"{career_title(track or '')} question round"
            if mode == PracticeMode.QUESTIONS
            else f"Coding interview: {problem}"
            if problem
            else "Coding interview"
        )
        if status == InterviewStatus.IN_PROGRESS:
            live = deadline is not None and _aware(deadline) > now
            state, at, meaning = ("in_progress" if live else "time_up"), started, "started"
        else:
            state = {"completed": "finished", "expired": "expired", "abandoned": "ended_early"}[str(status)]
            at, meaning = ended or started, "finished"
        out.append(
            {"type": "interview", "id": sid, "title": title, "state": state, "at": at, "at_meaning": meaning}
        )
    return out


def _notes(db: Session, user: User, n: int, _opts: Options) -> list[dict]:
    rows = db.execute(
        select(Note.id, Note.title, Note.updated_at)
        .where(Note.user_id == user.id, Note.deleted_at.is_(None), Note.archived.is_(False))
        .order_by(Note.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {"type": "note", "id": i, "title": t.strip() or "Untitled note", "at": at, "at_meaning": "saved"}
        for i, t, at in rows
    ]


def _stories(db: Session, user: User, n: int, _opts: Options) -> list[dict]:
    rows = db.execute(
        select(ExperienceEntry.id, ExperienceEntry.title, ExperienceEntry.updated_at)
        .where(ExperienceEntry.user_id == user.id, ExperienceEntry.archived.is_(False))
        .order_by(ExperienceEntry.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {"type": "story", "id": i, "title": t.strip() or "Untitled story", "at": at, "at_meaning": "saved"}
        for i, t, at in rows
    ]


def _kits(db: Session, user: User, n: int, _opts: Options) -> list[dict]:
    rows = db.execute(
        select(
            InterviewKit.event_id,
            InterviewKit.updated_at,
            ApplicationEvent.application_id,
            ApplicationEvent.title,
            ApplicationEvent.on_date,
            Application.employer,
        )
        .join(ApplicationEvent, ApplicationEvent.id == InterviewKit.event_id)
        .join(Application, Application.id == ApplicationEvent.application_id)
        .where(
            InterviewKit.user_id == user.id, Application.user_id == user.id, Application.archived.is_(False)
        )
        .order_by(InterviewKit.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {
            "type": "kit",
            "id": event_id,
            "parent_id": app_id,
            "title": f"Interview-day kit: {title}" + (f" ({employer})" if employer else ""),
            "detail": f"on {on_date.isoformat()}" if on_date else None,
            "at": at,
            "at_meaning": "saved",
        }
        for event_id, at, app_id, title, on_date, employer in rows
    ]


def _applications(db: Session, user: User, n: int, _opts: Options) -> list[dict]:
    rows = db.execute(
        select(
            Application.id,
            Application.role_title,
            Application.employer,
            Application.stage,
            Application.updated_at,
        )
        .where(Application.user_id == user.id, Application.archived.is_(False))
        .order_by(Application.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {
            "type": "application",
            "id": i,
            "title": f"{role} at {employer}" if role and employer else role or employer or "Application",
            "detail": stage.capitalize(),
            "at": at,
            "at_meaning": "saved",
        }
        for i, role, employer, stage, at in rows
    ]


def _offer_comparisons(db: Session, user: User, n: int, _opts: Options) -> list[dict]:
    rows = db.execute(
        select(OfferComparison.id, OfferComparison.title, OfferComparison.updated_at)
        .where(OfferComparison.user_id == user.id, OfferComparison.archived.is_(False))
        .order_by(OfferComparison.updated_at.desc())
        .limit(n)
    ).all()
    return [
        {
            "type": "offer_comparison",
            "id": i,
            "title": t.strip() or "Offer comparison",
            "at": at,
            "at_meaning": "saved",
        }
        for i, t, at in rows
    ]


def _last_step_at(db: Session) -> ColumnElement[str]:
    """A run's last step's time as its step recorded it: only that value, taken in the query."""
    if db.get_bind().dialect.name == "postgresql":
        return ScenarioAttempt.steps.op("->")(literal_column("-1")).op("->>")(literal_column("'at'"))
    return func.json_extract(ScenarioAttempt.steps, literal_column("'$[#-1].at'"))


def _parsed(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None  # not a time: the run is listed at its start, and says so


def _scenario_runs(db: Session, user: User, n: int, opts: Options) -> list[dict]:
    """Scenario runs left in progress: Resume opens the run at its current step. At its last step's
    time when the page can show it (its start when it has none), else at its start as before."""
    from app.scenarios import SCENARIO_INDEX

    last = "last_step" in opts.shows
    rows = db.execute(
        select(
            ScenarioAttempt.id,
            ScenarioAttempt.scenario_id,
            ScenarioAttempt.mode,
            ScenarioAttempt.created_at,
            _last_step_at(db) if last else literal_column("NULL"),
        )
        .where(ScenarioAttempt.user_id == user.id, ScenarioAttempt.status == "in_progress")
        # A step sets the run's updated_at, so the runs stepped most recently are the ones kept.
        .order_by((ScenarioAttempt.updated_at if last else ScenarioAttempt.created_at).desc())
        .limit(n)
    ).all()
    out = []
    for i, scenario, mode, started, last_step in rows:
        found = SCENARIO_INDEX.get(scenario)
        stepped = _parsed(last_step)
        out.append(
            {
                "type": "scenario_run",
                "id": i,
                "title": found.title if found else "A scenario that's no longer offered",
                "detail": "Exploration" if mode == "exploration" else None,
                "at": stepped or started,
                "at_meaning": "last_step" if stepped else "started",
            }
        )
    return out


def debug_verdict_words(
    status: SubmissionStatus, passed: int | None, total: int | None, judge_enabled: bool
) -> str:
    """An attempt's verdict in the debugging exercise's own words (the page's debrief heading,
    `DebugDebrief` in features/debugging/DebugLab.tsx; while it's judged, the status badge's)."""
    if not judge_enabled:
        return "Saved, not checked"
    if not status.is_terminal:
        return "Queued" if status == SubmissionStatus.QUEUED else "Running"
    if status == SubmissionStatus.PASSED:
        return "Fixed: every test passes"
    if passed is None or total is None:
        return "Not fixed yet"
    return f"Not fixed yet: {passed} of {total} tests pass"


def _debug_exercises(db: Session, user: User, n: int, opts: Options) -> list[dict]:
    """Debugging exercises tried and not fixed: none of the submitted attempts passed (the plan's
    rule), and the newest is less than a week old. Its title, verdict and time; never code."""
    if "debug_exercise" not in opts.shows:
        return []
    since = datetime.now(UTC) - timedelta(days=TRIED_DAYS)
    mine = (Submission.user_id == user.id, Submission.mode == SubmissionMode.SUBMIT)
    fixed = select(Submission.problem_id).where(*mine, Submission.status == SubmissionStatus.PASSED)
    newest = (
        select(Submission.problem_id, func.max(Submission.created_at).label("at"))
        .join(Problem, Problem.id == Submission.problem_id)
        .where(*mine, Problem.kind == "debug")
        .group_by(Submission.problem_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Problem.slug,
            Problem.title,
            Submission.status,
            ExecutionResult.passed_count,
            ExecutionResult.total_count,
            Submission.created_at,
        )
        .join(newest, (newest.c.problem_id == Submission.problem_id) & (newest.c.at == Submission.created_at))
        .join(Problem, Problem.id == Submission.problem_id)
        .outerjoin(ExecutionResult, ExecutionResult.submission_id == Submission.id)
        .where(*mine, Submission.problem_id.not_in(fixed), newest.c.at >= since)
        .order_by(Submission.created_at.desc())
        .limit(n)
    ).all()
    out: dict[str, dict] = {}
    for slug, title, status, passed, total, at in rows:
        out.setdefault(  # two attempts at the same instant: the exercise is listed once
            slug,
            {
                "type": "debug_exercise",
                "id": slug,
                "title": title,
                "detail": debug_verdict_words(status, passed, total, opts.judge_enabled),
                "at": at,
                "at_meaning": "tried",
            },
        )
    return list(out.values())


def _test_design_runs(db: Session, user: User, n: int, _opts: Options) -> list[dict]:
    """Test-design runs waiting for the judge, and those finished in the last week, in the words
    their run list uses. The result's two numbers are read from the report in the query."""
    from app.services.test_design import PENDING, outcome_words
    from app.testdesign import BY_SLUG

    since = datetime.now(UTC) - timedelta(days=FINISHED_RUN_DAYS)
    when = func.coalesce(TestDesignRun.judged_at, TestDesignRun.created_at)
    rows = db.execute(
        select(
            TestDesignRun.id,
            TestDesignRun.exercise_slug,
            TestDesignRun.exercise_version,
            TestDesignRun.status,
            TestDesignRun.report["caught"].as_integer(),
            TestDesignRun.report["total"].as_integer(),
            TestDesignRun.created_at,
            TestDesignRun.judged_at,
        )
        .where(
            TestDesignRun.user_id == user.id,
            TestDesignRun.status.in_(PENDING) | (when >= since),
        )
        .order_by(when.desc())
        .limit(n)
    ).all()
    out = []
    for i, slug, version, status, caught, total, created, judged in rows:
        found = BY_SLUG.get(slug)
        words = outcome_words(status, caught, total, version)
        out.append(
            {
                "type": "test_design_run",
                "id": i,
                "parent_id": slug,
                "title": found.title if found else "A test-design exercise that's no longer offered",
                "detail": words[:1].upper() + words[1:],
                "at": judged or created,
                "at_meaning": "finished" if judged is not None else "saved",
            }
        )
    return out


# What each kind is called when it can't be read ("Your notes couldn't be loaded").
SOURCES: dict[str, tuple[str, Callable[[Session, User, int, Options], list[dict]]]] = {
    "interviews": ("interviews", _interviews),
    "notes": ("notes", _notes),
    "stories": ("stories", _stories),
    "kits": ("interview-day kits", _kits),
    "applications": ("applications", _applications),
    "offer_comparisons": ("offer comparisons", _offer_comparisons),
    "scenario_runs": ("scenario runs", _scenario_runs),
    "test_design_runs": ("test-design runs", _test_design_runs),
    "debug_exercises": ("debugging exercises", _debug_exercises),
}


def recent_work(
    db: Session,
    user: User,
    limit: int = 6,
    *,
    judge_enabled: bool = False,
    shows: frozenset[str] = frozenset(),
) -> dict:
    limit = max(1, min(limit, MAX_LIMIT))
    opts = Options(judge_enabled=judge_enabled, shows=shows & SHOWS)
    items: list[dict] = []
    unavailable: list[str] = []
    for name, (label, read) in SOURCES.items():
        try:
            with db.begin_nested():  # a failing kind rolls back to here; the others still run
                items.extend(read(db, user, limit, opts))
        except Exception:
            logger.exception("recent work: %s couldn't be read", name)
            unavailable.append(label)
    for i in items:
        i["at"] = _aware(i["at"])
    # An interview whose clock is running comes first; then everything else, newest first.
    items.sort(key=lambda i: (i.get("state") != "in_progress", -i["at"].timestamp()))
    return {"items": items[:limit], "unavailable": unavailable}
