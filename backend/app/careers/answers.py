"""Building and presenting graded written answers (shared by single questions and question rounds)."""

from __future__ import annotations

from app.careers import evidence, grading
from app.careers.grading import MIN_WORDS, Feedback, grade
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
        feedback=feedback_dict(fb, question),
    )


def feedback_dict(fb: Feedback, question: Question) -> dict:
    """How a grade is stored: what the coach found, quoted evidence, and the versions it used."""
    return {
        "rating": fb.rating,
        "summary": fb.summary,
        "points": [
            {
                "label": p.label,
                "covered": p.covered,
                "advice": p.advice,
                "evidence": p.evidence,
                # where the quote is in `answer`, in code points (app/careers/evidence.py)
                "span": list(p.span) if p.span else None,
            }
            for p in fb.points
        ],
        "notes": list(fb.notes),
        "outline": list(question.outline),
        "word_count": fb.word_count,
        "evidence_level": fb.evidence_level,
        "rubric_version": grading.RUBRIC_VERSION,
        "evaluator": f"{OFFLINE_COACH} · rubric {grading.RUBRIC_VERSION}",
    }


def rubric_version_of(feedback: dict) -> str:
    """The rubric an older stored grade used (before it was stored separately it was in "evaluator")."""
    if feedback.get("rubric_version"):
        return str(feedback["rubric_version"])
    tail = str(feedback.get("evaluator", "")).rpartition("rubric ")[2].strip()
    return tail or "v1"


def feedback_points(answer: str, stored: list[dict]) -> list[FeedbackPoint]:
    """The stored points with their evidence checked against the answer they were given for
    (app/careers/evidence.py): a quote that doesn't check out isn't shown, and none is invented."""
    out = []
    for p in stored:
        e = evidence.check(answer, bool(p["covered"]), p.get("evidence"), p.get("span"))
        out.append(
            FeedbackPoint(
                label=p["label"],
                covered=p["covered"],
                advice=p["advice"],
                evidence=e.quote,
                span=list(e.span) if e.span else None,
                evidence_status=e.status,
            )
        )
    return out


def answer_out(row: PracticeAnswer) -> AnswerOut:
    fb = row.feedback
    return AnswerOut(
        id=row.id,
        question_id=row.question_id,
        answer=row.answer,
        score=row.score,
        rating=fb["rating"],
        summary=fb["summary"],
        points=feedback_points(row.answer, fb["points"]),
        rubric_version=rubric_version_of(fb),
        # Older answers didn't store this; their word count says it.
        evidence_level=fb.get("evidence_level")
        or ("insufficient" if fb["word_count"] < MIN_WORDS else "sufficient"),
        notes=fb["notes"],
        outline=fb["outline"],
        word_count=fb["word_count"],
        coach=row.provider,
        created_at=row.created_at,
        content_version=row.content_version or 1,
        story_id=row.story_id,
    )
