"""Building and presenting graded written answers (shared by single questions and question rounds)."""

from __future__ import annotations

import hashlib
import hmac
import json

from app.careers import evidence, grading
from app.careers.eligibility import feedback_eligibility
from app.careers.grading import Feedback, grade
from app.careers.questions import Question
from app.careers.support import evaluation_for, scope_note
from app.models import PracticeAnswer
from app.schemas.careers import AnswerOut, FeedbackPoint
from app.schemas.conditions import AttemptConditions

OFFLINE_COACH = "built-in (offline)"


# A keyed request's fingerprint: what it asked for, so a resend can be told from a different request
# with the same key. Versioned: a stored fingerprint is only ever compared with one computed the same
# way, and a version this code doesn't know is reported as unverifiable, never as a match.
FINGERPRINT_VERSION = "v1"


def request_fingerprint(
    track: str,
    question_id: str,
    answer: str,
    story_id: str | None,
    revises_answer_id: str | None,
    follows_up_answer_id: str | None = None,
) -> str:
    """v1: sha256 of the request's own fields exactly as sent (answer text unnormalized, so a
    changed answer is a different request). A follow-up's link is included only when set, so every
    earlier fingerprint stays the same."""
    payload = {
        "track": track,
        "question_id": question_id,
        "answer": answer,
        "story_id": story_id,
        "revises_answer_id": revises_answer_id,
    }
    if follows_up_answer_id is not None:
        payload["follows_up_answer_id"] = follows_up_answer_id
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return f"{FINGERPRINT_VERSION}:{digest}"


def same_request(stored: str | None, fingerprint: str) -> bool | None:
    """Whether a stored fingerprint is this request's: True, False, or None when it can't be told
    (no fingerprint stored, or one from a version this code doesn't compute)."""
    if not stored or ":" not in stored:
        return None
    if stored.split(":", 1)[0] != FINGERPRINT_VERSION:
        return None
    return hmac.compare_digest(stored, fingerprint)


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
                scope_note=scope_note(p["label"]),
            )
        )
    return out


_LEVEL = {"scored": "sufficient", "too_short": "insufficient", "unknown": "unknown"}


def _evidence_level(fb: dict) -> str:
    """The stored level; older answers didn't store it, and their recorded word count says it. One
    rule with the summaries (app/careers/eligibility.py): with neither recorded it's unknown."""
    return _LEVEL[feedback_eligibility(fb)]


def answer_out(row: PracticeAnswer, conditions: AttemptConditions | None = None) -> AnswerOut:
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
        evidence_level=_evidence_level(fb),
        notes=fb["notes"],
        outline=fb["outline"],
        # Not recorded (only in an "unknown" answer): counted from the stored text, as a fact about
        # the text, never used to decide whether the answer could be scored.
        word_count=fb["word_count"] if fb.get("word_count") is not None else len(row.answer.split()),
        coach=row.provider,
        created_at=row.created_at,
        content_version=row.content_version or 1,
        story_id=row.story_id,
        track=row.track,
        evaluation_status=evaluation_for(row.track).status,
        evaluation_note=evaluation_for(row.track).note,
        revises_answer_id=row.revises_answer_id,
        follows_up_answer_id=row.follows_up_answer_id,
        conditions=conditions,
    )
