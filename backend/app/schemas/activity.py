"""The shared activity model: one shape for everything a learner does, across careers."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.careers import AttemptComparison
from app.schemas.common import APIModel

ActivityType = Literal["problem_opened", "code_submission", "coaching", "written_answer", "interview"]
ActivityStatus = Literal[
    "opened",  # a page was opened: activity, not an attempt
    "saved_not_judged",  # a code submission saved where the judge isn't available
    "awaiting_judge",  # queued or running
    "passed",
    "failed",
    "evaluation_unavailable",  # the judge had an internal error
    "scored",  # a written answer graded by the career rubric (a score, not "correct")
    "too_short",  # a written answer too short to score: its stored score is capped and isn't counted
    "completed",  # coaching delivered, or an interview finished
    "in_progress",
    "expired",
    "abandoned",
]
CODING = "coding"  # the career key for coding activity (problems are shared by coding careers)


class ActivityTarget(APIModel):
    """Where the row opens: a page path plus the stable ids it refers to."""

    href: str
    problem_slug: str | None = None
    track: str | None = None
    question_id: str | None = None
    submission_id: str | None = None
    answer_id: str | None = None
    interview_id: str | None = None
    ai_interaction_id: str | None = None


class ActivityItem(APIModel):
    id: str = Field(description="Stable: '<type>:<source id>'")
    type: ActivityType
    occurred_at: datetime
    career: str = Field(description="A career slug, or 'coding' for coding problems")
    career_title: str
    title: str
    detail: str | None = Field(description="e.g. 'Hint, level 2' or 'Interview, 3 of 5 answered'")
    skills: list[str]
    status: ActivityStatus
    status_label: str
    score: int | None = Field(description="Written answers only: 0-100 rubric score (not correctness)")
    session_id: str | None = Field(description="The interview this activity was part of, if any")
    target: ActivityTarget


class FacetOption(APIModel):
    value: str
    label: str
    count: int


class ActivityFacets(APIModel):
    careers: list[FacetOption]
    types: list[FacetOption]
    statuses: list[FacetOption]
    skills: list[FacetOption] = Field(description="For the chosen career, or empty when none is chosen")


class SkillStat(APIModel):
    skill: str
    total_questions: int = Field(description="Questions in this career that practise the skill")
    questions_answered: int
    answers: int
    average_best_score: int | None = Field(
        description="Average of your best scoreable score on each answered question of this skill; None when "
        "none of them has an answer long enough to score"
    )
    questions_scored: int = Field(default=0, description="How many of those questions the average covers")


class TrendPoint(APIModel):
    week_start: date
    answers: int = Field(
        description="Answers averaged this week: the series' cohort, the average's denominator"
    )
    average_score: int | None


class TrendSeries(APIModel):
    evaluator: str = Field(
        description="The series: the same scale, kind of evaluator and rubric (docs/COMPARING_ATTEMPTS.md)"
    )
    attempts: int = Field(default=0, description="Answers in this series in the range (the cohort)")
    points: list[TrendPoint]


class NotCounted(APIModel):
    rule: str
    reason: str
    count: int


class ChartAttempt(APIModel):
    answer_id: str
    question_id: str
    question_title: str
    href: str
    created_at: datetime
    score: int = Field(description="Its own score, on its own scale; never converted")
    scoring: Literal["scored", "too_short", "unknown"] = Field(
        description="Long enough to score, too short, or not recorded (app/careers/eligibility.py)"
    )
    scale: str
    series: str | None = Field(description="The trend series it's in, or null when it isn't counted")
    not_counted: str | None = Field(description="Why it isn't in the trend, when it isn't")
    comparison: AttemptComparison | None = Field(
        description="Compared with your answer before it to the same question, by the same contract as the "
        "question page and an interview retry"
    )


class ChartAttempts(APIModel):
    total: int = Field(description="Answers in the range")
    in_chart: int = Field(description="Of those, in the trend (equals the trend's attempts)")
    offset: int
    items: list[ChartAttempt]


class DayCount(APIModel):
    day: date
    answers: int
    interviews: int


class InterviewCounts(APIModel):
    completed: int
    in_progress: int
    expired: int
    abandoned: int


class CareerAnalytics(APIModel):
    track: str
    career_title: str
    since: date | None = Field(description="Start of the range (inclusive); null means all time")
    until: date
    questions_practiced: int
    answers: int
    strong_questions: int = Field(description="Questions whose best score is 85 or more")
    total_questions: int
    skills: list[SkillStat] = Field(
        description="Every skill this career's questions practise, practised or not"
    )
    kinds: list[FacetOption]
    interviews: InterviewCounts
    trends: list[TrendSeries]
    not_in_trend: list[NotCounted] = Field(
        default_factory=list, description="Answers in the range that the trend doesn't count, by reason"
    )
    comparison_rules: int = Field(
        default=1, description="The comparison contract's version that decided this"
    )
    by_day: list[DayCount]
    definitions: dict[str, str]


class ResumeInterview(APIModel):
    id: str
    kind: Literal["coding", "questions"]
    title: str
    deadline_at: datetime
    seconds_remaining: int


class ResumeProblem(APIModel):
    slug: str
    title: str
    last_status: str
    at: datetime


class ResumeQuestion(APIModel):
    track: str
    question_id: str
    title: str
    at: datetime


class ResumeOut(APIModel):
    interview: ResumeInterview | None
    unfinished_problem: ResumeProblem | None = Field(
        description="Most recent submitted, never-solved problem"
    )
    last_question: ResumeQuestion | None
