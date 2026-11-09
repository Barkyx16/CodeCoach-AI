"""The optional first-session introduction.

What's recorded is deliberately small: the learner's choices about the introduction itself (see
`OnboardingState`). Nothing here reads or stores answer text, and nothing here creates practice
activity: the tour never counts as an attempt, a score or progress. "Has the learner done a real
activity yet?" is answered from their actual answers and submissions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers import CATALOG, DEFAULT_TRACK
from app.careers.questions import questions_for
from app.models import Difficulty, OnboardingState, PracticeAnswer, Problem, Submission, User
from app.schemas.onboarding import CareerIntro, OnboardingOut, OnboardingUpdate, StarterActivity
from app.services.content import is_problem_retired

# The guided tour's length per format. The web app's step lists match these.
TOUR_STEPS = {"written": 5, "coding": 5}
TOUR_VERSION = 1
# The coding starter: a short, classic warm-up if it exists, else the first easy problem.
PREFERRED_PROBLEM = "two-sum"


def career_format(track: str) -> str:
    profile = CATALOG.get(track) or CATALOG[DEFAULT_TRACK]
    return "coding" if profile.has_coding else "written"


def starter_for(db: Session, track: str) -> StarterActivity | None:
    """A real, short activity for this career. Written careers get an easy knowledge question
    from their own bank (a nurse is never introduced through Java); coding careers get an easy
    problem. Retired content is never offered."""
    if track not in CATALOG:
        track = DEFAULT_TRACK
    if career_format(track) == "coding":
        preferred = db.scalar(select(Problem).where(Problem.slug == PREFERRED_PROBLEM))
        candidates = [preferred] if preferred is not None else []
        candidates += db.scalars(
            select(Problem)
            .where(Problem.difficulty == Difficulty.EASY, Problem.kind == "problem")
            .order_by(Problem.order_index, Problem.id)
        ).all()
        problem = next((p for p in candidates if not is_problem_retired(p.slug)), None)
        if problem is not None:
            return StarterActivity(
                kind="problem",
                track=track,
                ref=problem.slug,
                title=problem.title,
                difficulty=problem.difficulty.value,
                href=f"/problems/{problem.slug}",
                minutes=15,
            )
        # No coding problems on this server: fall back to a written question for the career.
    questions = [q for q in questions_for(track) if q.difficulty == "easy"]
    question = next((q for q in questions if q.kind == "knowledge"), None) or next(iter(questions), None)
    if question is None:
        return None
    return StarterActivity(
        kind="question",
        track=track,
        ref=question.id,
        title=question.title,
        difficulty=question.difficulty,
        href=f"/careers/{track}/questions/{question.id}",
        minutes=5,
    )


def first_activity_at(db: Session, user: User) -> datetime | None:
    """The learner's first real answer or code submission. Only timestamps are read."""
    answered = db.scalar(select(func.min(PracticeAnswer.created_at)).where(PracticeAnswer.user_id == user.id))
    submitted = db.scalar(select(func.min(Submission.created_at)).where(Submission.user_id == user.id))
    times = [t if t.tzinfo else t.replace(tzinfo=UTC) for t in (answered, submitted) if t is not None]
    return min(times) if times else None


class Onboarding:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _row(self, create: bool = False) -> OnboardingState | None:
        row = self.db.get(OnboardingState, self.user.id)
        if row is None and create:
            row = OnboardingState(
                user_id=self.user.id,
                tour_status="not_started",
                tour_step=0,
                tour_version=TOUR_VERSION,
                career_intros_seen=[],
                dismissed=[],
            )
            self.db.add(row)
        return row

    def get(self) -> OnboardingOut:
        row = self._row()
        track = self.user.career_track if self.user.career_track in CATALOG else DEFAULT_TRACK
        fmt = career_format(track)
        first = first_activity_at(self.db, self.user)
        status = row.tour_status if row else "not_started"
        kind = row.tour_kind if row else None
        dismissed = set(row.dismissed or []) if row else set()
        welcomed = row is not None and row.welcomed_at is not None
        career_intro = None
        # A career change after the welcome offers that career's format introduction once.
        if row is not None and welcomed and track not in (row.career_intros_seen or []):
            career_intro = CareerIntro(track=track, title=CATALOG[track].title, kind=fmt)
        return OnboardingOut(
            tour_status=status,
            tour_kind=kind,
            tour_step=row.tour_step if row else 0,
            tour_steps=TOUR_STEPS[kind or fmt],
            start_choice=row.start_choice if row else None,
            welcome_due=not welcomed and first is None and "welcome" not in dismissed,
            resume_due=status in ("in_progress", "paused") and "resume_tour" not in dismissed,
            career_intro=career_intro,
            first_activity_at=first,
            starter=starter_for(self.db, track),
            format=fmt,
        )

    def update(self, body: OnboardingUpdate) -> OnboardingOut:
        row = self._row(create=True)
        assert row is not None
        now = datetime.now(UTC)
        track = self.user.career_track if self.user.career_track in CATALOG else DEFAULT_TRACK
        fmt = career_format(track)

        if body.start_choice is not None:
            row.start_choice = body.start_choice
            if row.welcomed_at is None:
                row.welcomed_at = now
                row.intro_track = track
            row.career_intros_seen = sorted({*(row.career_intros_seen or []), track})
            if body.start_choice == "later" and row.tour_status == "not_started":
                row.tour_status = "skipped"

        if body.tour is not None:
            kind = body.tour_kind or row.tour_kind or fmt
            steps = TOUR_STEPS[kind]
            if body.tour == "start":
                row.tour_status = "in_progress"
                row.tour_kind = body.tour_kind or fmt
                row.tour_step = min(body.tour_step or 0, TOUR_STEPS[row.tour_kind] - 1)
                row.tour_version = TOUR_VERSION
                row.tour_started_at = now
                row.tour_finished_at = None
                row.dismissed = [d for d in (row.dismissed or []) if d != "resume_tour"]
                if row.welcomed_at is None:  # replayed from Help before ever seeing the welcome
                    row.welcomed_at = now
                    row.intro_track = track
            elif body.tour == "step":
                # Only moves a tour that's running or paused; a late "step" after finishing is a no-op.
                if row.tour_status in ("in_progress", "paused") and body.tour_step is not None:
                    row.tour_status = "in_progress"
                    row.tour_step = min(body.tour_step, steps - 1)
            elif body.tour == "pause":
                if row.tour_status == "in_progress":
                    row.tour_status = "paused"
            elif body.tour == "complete":
                if row.tour_status in ("in_progress", "paused"):
                    row.tour_status = "completed"
                    row.tour_step = steps - 1
                    row.tour_finished_at = now
            elif body.tour == "skip":
                if row.tour_status != "completed":
                    row.tour_status = "skipped"
                    row.tour_finished_at = now

        if body.dismiss is not None and body.dismiss not in (row.dismissed or []):
            row.dismissed = [*(row.dismissed or []), body.dismiss]

        if body.career_intro_seen:
            row.career_intros_seen = sorted({*(row.career_intros_seen or []), track})
            if row.welcomed_at is None:
                row.welcomed_at = now
                row.intro_track = track

        row.updated_at = now
        self.db.commit()
        return self.get()

    def export(self) -> dict | None:
        row = self._row()
        if row is None:
            return None
        return {
            "tour_status": row.tour_status,
            "tour_kind": row.tour_kind,
            "tour_step": row.tour_step,
            "start_choice": row.start_choice,
            "career_intros_seen": row.career_intros_seen,
            "dismissed": row.dismissed,
            "welcomed_at": row.welcomed_at.isoformat() if row.welcomed_at else None,
            "tour_started_at": row.tour_started_at.isoformat() if row.tour_started_at else None,
            "tour_finished_at": row.tour_finished_at.isoformat() if row.tour_finished_at else None,
        }
