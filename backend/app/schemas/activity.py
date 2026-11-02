"""The shared activity model: one shape for everything a learner does, across careers."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

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
    average_best_score: int | None


class TrendPoint(APIModel):
    week_start: date
    answers: int
    average_score: int | None


class TrendSeries(APIModel):
    evaluator: str = Field(description="Scores are only compared within one evaluator and rubric version")
    points: list[TrendPoint]


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
