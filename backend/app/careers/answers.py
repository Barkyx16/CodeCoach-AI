"""Building and presenting graded written answers (shared by single questions and question rounds)."""

from __future__ import annotations

from app.careers.grading import RUBRIC_VERSION, grade
from app.careers.questions import Question
from app.models import PracticeAnswer
from app.schemas.careers import AnswerOut, FeedbackPoint

OFFLINE_COACH = "built-in (offline)"


def graded_answer(user_id: str, question: Question, text: str) -> PracticeAnswer:
    """Grade `text` with the offline coach and return the (unsaved) answer row."""
    fb = grade(question, text)
    return PracticeAnswer(
        user_id=user_id,
        track=question.track,
        question_id=question.id,
        difficulty=question.difficulty,
        answer=text,
        score=fb.score,
        provider=OFFLINE_COACH,
        content_version=question.version,  # the version answered; later corrections never touch it
        feedback={
            "rating": fb.rating,
            "summary": fb.summary,
            "points": [{"label": p.label, "covered": p.covered, "advice": p.advice} for p in fb.points],
            "notes": list(fb.notes),
            "outline": list(question.outline),
            "word_count": fb.word_count,
            "evaluator": f"{OFFLINE_COACH} · rubric {RUBRIC_VERSION}",
        },
    )


def answer_out(row: PracticeAnswer) -> AnswerOut:
    fb = row.feedback
    return AnswerOut(
        id=row.id,
        question_id=row.question_id,
        answer=row.answer,
        score=row.score,
        rating=fb["rating"],
        summary=fb["summary"],
        points=[FeedbackPoint(**p) for p in fb["points"]],
        notes=fb["notes"],
        outline=fb["outline"],
        word_count=fb["word_count"],
        coach=row.provider,
        created_at=row.created_at,
        content_version=row.content_version or 1,
    )
