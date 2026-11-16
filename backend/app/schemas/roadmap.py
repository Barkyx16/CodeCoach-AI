"""Practice goals, the adaptive plan, today's session and the baseline assessment."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.disputes import DisputeNote

Experience = Literal["new", "early", "mid", "senior"]
Format = Literal["written", "voice", "coding"]
ItemKind = Literal["assessment", "question", "retry", "review", "voice", "mock", "coding", "learn"]
ItemStatus = Literal["pending", "done", "skipped", "replaced"]


class GoalsIn(APIModel):
    track: str | None = Field(default=None, max_length=64, description="Default: your current career")
    specialty: str | None = Field(default=None, max_length=120)
    experience: Experience | None = None
    target_date: date | None = Field(default=None, description="Your interview date, if you know it")
    weekly_minutes: int | None = Field(default=None, ge=10, le=1200)
    focus_areas: list[str] = Field(default_factory=list, max_length=8, description="Skills of this career")
    formats: list[Format] = Field(default_factory=list, max_length=3)
    confidence: dict[str, int] = Field(
        default_factory=dict,
        description="Self-reported confidence per skill, 1-5 (never blended with scores)",
    )
    setup_skipped: bool = False


class GoalsOut(GoalsIn):
    track: str
    career_title: str
    has_coding: bool
    skills: list[str] = Field(
        description="Skills this career's questions practise (for focus and confidence)"
    )
    saved: bool = Field(description="False until goals are saved or setup is skipped")


class RoundStart(APIModel):
    """How to start the round an activity needs (POST /interviews with these fields)."""

    track: str
    difficulty: str | None = None
    question_ids: list[str] | None = None
    purpose: Literal["practice", "baseline"] = "practice"
    duration_minutes: int


class Withheld(APIModel):
    text: str = Field(description="One line: 'Not suggested: … you disputed this point on 3 November.'")
    href: str
    reinstated: bool = Field(
        default=False, description="Reinstated since: it can be suggested again at the plan's next update"
    )


class PlanItemOut(APIModel):
    id: str
    position: int
    kind: ItemKind
    skill: str
    title: str
    reason: str = Field(description="Why this activity was chosen")
    completion: str = Field(description="What counts as done")
    minutes: int = Field(description="Estimated duration")
    status: ItemStatus
    evidence: str | None = Field(description="What completed it, e.g. 'Answered, scored 72/100'")
    href: str | None = Field(description="Where to do it, when it's a page")
    round: RoundStart | None = Field(description="When it's a mock-interview round to start")
    can_mark_reviewed: bool
    can_replace: bool
    created_at: datetime
    resolved_at: datetime | None
    disputed: DisputeNote | None = Field(
        default=None, description="Derived from feedback you've disputed since (it stays; you decide)"
    )


class TodayOut(APIModel):
    minutes_available: int
    primary: PlanItemOut | None
    follow_up: PlanItemOut | None
    session_minutes: int
    note: str | None = Field(description="Explains the choice when nothing fits exactly")


class SelfRating(APIModel):
    skill: str
    rating: int


class EvaluatedSkill(APIModel):
    skill: str
    questions: int
    answers: int
    average_best_score: int


class CodingEvidence(APIModel):
    judge_available: bool
    judged_attempts: int
    passed: int
    saved_not_judged: int


class AssessmentOut(APIModel):
    state: Literal["building_baseline", "baseline_ready"]
    note: str
    self_reported: list[SelfRating] = Field(description="What you said; not a measurement")
    evaluated: list[EvaluatedSkill] = Field(description="Rubric scores of your answers; not correctness")
    coding: CodingEvidence | None = Field(description="Judge results only; null for careers without coding")


class PlanProgress(APIModel):
    done_this_week: int
    minutes_this_week: int = Field(description="Estimated minutes of activities completed in the last 7 days")
    weekly_minutes: int = Field(description="Your weekly practice time (default 60)")
    done_in_plan: int
    open_in_plan: int


class NewEvidence(APIModel):
    kind: Literal["answer", "retry", "round", "submission", "lesson"] = Field(
        description="A written answer, an answer revising an earlier one, a finished question round, a "
        "judged coding submission, or a Learn lesson's check passed (Volume 17, prompt 3)"
    )
    title: str
    score: int | None = Field(description="An answer's score; none for a round or a submission")
    verdict: Literal["passed", "not passed"] | None = Field(
        default=None, description="A submission's verdict, as judged"
    )
    verdict_detail: str | None = Field(
        default=None,
        description="A submission's verdict in the judge's terms: 'passed', 'tests failed', 'compile error', "
        "'runtime error', 'time limit exceeded' or 'memory limit exceeded' (never a score)",
    )
    exercise: bool = Field(default=False, description="A submission to a debugging exercise, not a problem")
    skill: str | None = Field(
        default=None,
        description="The skill it's evidence for, as grouped in `by_skill`: a question's skill, a problem's "
        "first topic, a debugging exercise's first topic after 'debugging', or the kind of round",
    )
    href: str


class SkillNews(APIModel):
    """What's new for one skill and what it would move in the next version, in one sentence."""

    skill: str | None = Field(
        description="The skill; none for what all of what's new moves together, when it can't be put on one"
    )
    count: int = Field(description="How many of the new pieces of evidence are for this skill")
    text: str = Field(
        description="One sentence: what's new, what it counts as, and what the next version would suggest "
        "or stop suggesting because of it (or that it changes nothing on its own)"
    )


class ReadSubmission(APIModel):
    id: str
    title: str | None = Field(description="The problem or exercise; none if it's no longer stored")
    verdict: Literal["passed", "not passed"] | None = None
    exercise: bool = False
    href: str | None = None


class ReadLesson(APIModel):
    """A lesson check an update read as new evidence (Volume 17, prompt 3), by unit and version."""

    unit_id: str
    version: int
    title: str | None = Field(description="The lesson; none if it's no longer offered")
    href: str | None = None


class PlanNews(APIModel):
    """Practice since this version that would change what the plan suggests (docs/PLAN_UPDATES.md).
    Shown only then; the plan stays as it is until the learner asks for the update."""

    text: str = Field(description="One line, e.g. '2 answers since this plan, one below 70.'")
    answers: int = Field(description="Scored answers since this version that no activity used")
    retries: int = Field(description="How many of those revise an earlier answer")
    below: int = Field(description="How many of those scored below 70")
    rounds: int = Field(description="Question rounds finished since this version that no activity used")
    submissions: int = Field(
        default=0, description="Judged coding submissions since this version that no activity used"
    )
    not_passed: int = Field(default=0, description="How many of those didn't pass")
    lessons: int = Field(
        default=0, description="Lesson checks passed since this version (on the lesson's current version)"
    )
    entries: list[NewEvidence] = Field(description="Them, oldest first (at most 10)")
    not_counted: list[str] = Field(
        default_factory=list,
        description="Practice since this version the plan doesn't use: answers too short to score or "
        "disputed, and submissions the judge couldn't run (its problem, not the learner's code)",
    )
    by_skill: list[SkillNews] = Field(
        default_factory=list,
        description="What's new grouped by skill, oldest first, one sentence each (Volume 16, prompt 7)",
    )
    rule: str | None = Field(
        default=None, description="How a verdict counts, when submissions are among what's new"
    )


class PlanUpdateIn(APIModel):
    version: int = Field(
        ge=1, description="The plan version you saw: the update is refused if it's no longer the latest"
    )
    track: str | None = Field(default=None, max_length=64, description="Default: your current career")


class PlanOut(APIModel):
    track: str
    career_title: str
    version: int
    created_at: datetime
    changes: list[str] = Field(description="Why this version differs from the last one")
    items: list[PlanItemOut]
    withheld: list[Withheld] = Field(
        default_factory=list, description="Suggestions this version didn't make because of a dispute"
    )
    progress: PlanProgress
    today: TodayOut
    assessment: AssessmentOut
    goals_saved: bool
    target_date: date | None
    days_to_interview: int | None
    news: PlanNews | None = Field(
        default=None,
        description="New practice this version doesn't use that would change it; the plan updates only when asked",
    )
    read_submissions: list[ReadSubmission] | None = Field(
        default=None,
        description="The judged submissions the update that made this version read as new evidence, oldest "
        "first; none when the version wasn't made by 'Update my plan' (or was made before this was recorded)",
    )
    read_lessons: list[ReadLesson] | None = Field(
        default=None,
        description="The lesson checks the update that made this version read as new evidence; none when "
        "the version wasn't made by 'Update my plan' (or was made before this was recorded)",
    )
    evidence_read: str = Field(
        default="",
        description="Which kinds of evidence this career's plan reads, in a sentence",
    )
