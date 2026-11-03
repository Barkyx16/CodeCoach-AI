from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class CareerSummary(APIModel):
    slug: str
    title: str
    category: str
    summary: str
    has_coding: bool = Field(description="Also has hands-on coding problems (the code judge)")
    question_count: int


class QuestionSummary(APIModel):
    id: str
    title: str
    prompt: str
    difficulty: str
    kind: str = Field(description="knowledge, behavioral, situational, leadership or motivation")
    best_score: int | None = Field(
        default=None, description="Your best score on this question, when signed in"
    )


class QuestionDetail(QuestionSummary):
    track: str
    career_title: str
    tips: list[str]
    rubric_labels: list[str] = Field(description="What a strong answer covers (shown after answering)")


class AnswerRequest(APIModel):
    answer: str = Field(min_length=1, max_length=6000)
    story_id: str | None = Field(
        default=None,
        max_length=36,
        description="One of your stories this answer rehearses (it isn't changed)",
    )


class FeedbackPoint(APIModel):
    label: str
    covered: bool
    advice: str


class AnswerOut(APIModel):
    id: str
    question_id: str
    answer: str
    score: int
    rating: str
    summary: str
    points: list[FeedbackPoint]
    notes: list[str]
    outline: list[str] = Field(description="What a strong answer would include")
    word_count: int
    coach: str = Field(description="Which coach graded it: 'built-in (offline)' or the AI provider")
    created_at: datetime
    content_version: int = Field(default=1, description="The question's version when this was answered")
    story_id: str | None = Field(default=None, description="The story this answer rehearsed, if any")


class TrackProgress(APIModel):
    track: str
    answered: int
    strong: int = Field(description="Questions with a best score of 85 or more")
    by_difficulty: dict[str, int]
    total_questions: int
