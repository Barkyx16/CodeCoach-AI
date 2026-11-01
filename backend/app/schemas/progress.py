from datetime import date, datetime
from typing import Literal

from app.models import Difficulty, SubmissionStatus
from app.schemas.common import APIModel


class TopicProgress(APIModel):
    topic: str
    total_problems: int
    attempted: int
    solved: int


class DifficultyProgress(APIModel):
    difficulty: str
    total_problems: int
    solved: int


class ProblemStatus(APIModel):
    slug: str
    status: Literal["solved", "attempted", "in_progress", "not_started"]
    last_submission_status: SubmissionStatus | None
    submissions: int
    hints_used: int


class ActivityDay(APIModel):
    day: date
    events: int


class ProgressOut(APIModel):
    total_problems: int
    attempted: int
    solved: int
    submissions: int
    accepted_submissions: int
    acceptance_rate: float | None
    hints_used: int
    reviews_requested: int
    current_streak_days: int
    longest_streak_days: int
    last_active_at: datetime | None
    by_topic: list[TopicProgress]
    by_difficulty: list[DifficultyProgress]
    problems: list[ProblemStatus]
    activity: list[ActivityDay]
    weakest_topics: list[str]
    recommended_next: list[str]


class Recommendation(APIModel):
    slug: str
    title: str
    difficulty: Difficulty
    topics: list[str]
    reason: str
    kind: Literal["retry", "weak_topic", "next_step", "interview"]
