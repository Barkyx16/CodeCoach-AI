"""Career tracks and their interview questions.

Questions are generated from the career catalog (app/careers), so these endpoints never touch a
problems table. Answers are stored per user with the feedback they received.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_user
from app.careers import CATALOG, CATEGORIES
from app.careers.answers import answer_out, graded_answer
from app.careers.questions import Question, get_question, questions_for
from app.errors import NotFoundError, RateLimitedError
from app.models import PracticeAnswer, User
from app.schemas.careers import (
    AnswerOut,
    AnswerRequest,
    CareerSummary,
    QuestionDetail,
    QuestionSummary,
    TrackProgress,
)
from app.schemas.common import Page, error_responses
from app.schemas.problem import DifficultyCounts
from app.services import search

router = APIRouter(prefix="/api/v1", tags=["careers"])


def _track_or_404(slug: str) -> str:
    if slug not in CATALOG:
        raise NotFoundError(f"Career '{slug}' not found")
    return slug


def _searchable(q: Question) -> search.Searchable:
    return search.Searchable(
        title=q.title.lower(),
        topics=" ".join((*q.tags, q.kind)).lower(),
        summary=q.prompt.lower(),
        statement=" ".join(rp.label for rp in q.rubric).lower(),
    )


def _matching(track: str, q: str | None) -> list[Question]:
    questions = list(questions_for(track))
    if q and q.strip():
        questions = search.rank(((x, _searchable(x)) for x in questions), q)
    return questions


def _best_scores(db: Session, user: User | None, track: str) -> dict[str, int]:
    if user is None:
        return {}
    rows = db.execute(
        select(PracticeAnswer.question_id, func.max(PracticeAnswer.score))
        .where(PracticeAnswer.user_id == user.id, PracticeAnswer.track == track)
        .group_by(PracticeAnswer.question_id)
    ).all()
    return {qid: int(score) for qid, score in rows}


def _summary(q: Question, best: dict[str, int]) -> QuestionSummary:
    return QuestionSummary(
        id=q.id,
        title=q.title,
        prompt=q.prompt,
        difficulty=q.difficulty,
        kind=q.kind,
        best_score=best.get(q.id),
    )


@router.get("/careers", response_model=list[CareerSummary], summary="Every career you can practice for")
def list_careers() -> list[CareerSummary]:
    order = {c: i for i, c in enumerate(CATEGORIES)}
    profiles = sorted(CATALOG.values(), key=lambda p: (order[p.category], p.title))
    return [
        CareerSummary(
            slug=p.slug,
            title=p.title,
            category=p.category,
            summary=p.summary,
            has_coding=p.has_coding,
            question_count=len(questions_for(p.slug)),
        )
        for p in profiles
    ]


@router.get(
    "/careers/{slug}/questions",
    response_model=Page[QuestionSummary],
    responses=error_responses(404),
    summary="Interview questions for a career (filterable, searchable)",
)
def list_questions(
    slug: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    difficulty: str | None = Query(default=None, pattern="^(easy|medium|hard)$"),
    q: str | None = Query(default=None, max_length=80, description="Keywords or a plain description"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> Page[QuestionSummary]:
    track = _track_or_404(slug)
    rows = _matching(track, q)
    if difficulty:
        rows = [x for x in rows if x.difficulty == difficulty]
    best = _best_scores(db, user, track)
    start = (page - 1) * page_size
    return Page[QuestionSummary](
        items=[_summary(x, best) for x in rows[start : start + page_size]],
        total=len(rows),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/careers/{slug}/questions/counts",
    response_model=DifficultyCounts,
    responses=error_responses(404),
    summary="How many questions match, per difficulty",
)
def count_questions(slug: str, q: str | None = Query(default=None, max_length=80)) -> DifficultyCounts:
    counts = {"easy": 0, "medium": 0, "hard": 0}
    for x in _matching(_track_or_404(slug), q):
        counts[x.difficulty] += 1
    return DifficultyCounts(**counts)


@router.get(
    "/careers/{slug}/questions/{question_id}",
    response_model=QuestionDetail,
    responses=error_responses(404),
    summary="One interview question with tips",
)
def get_one(
    slug: str, question_id: str, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> QuestionDetail:
    question = get_question(_track_or_404(slug), question_id)
    if question is None:
        raise NotFoundError(f"Question '{question_id}' not found")
    best = _best_scores(db, user, slug)
    return QuestionDetail(
        **_summary(question, best).model_dump(),
        track=slug,
        career_title=CATALOG[slug].title,
        tips=list(question.tips),
        rubric_labels=[rp.label for rp in question.rubric],
    )


@router.post(
    "/careers/{slug}/questions/{question_id}/answers",
    response_model=AnswerOut,
    status_code=201,
    responses=error_responses(401, 404, 429),
    summary="Answer a question and get feedback",
)
def answer_question(
    slug: str,
    question_id: str,
    body: AnswerRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnswerOut:
    question = get_question(_track_or_404(slug), question_id)
    if question is None:
        raise NotFoundError(f"Question '{question_id}' not found")
    allowed, retry_after = request.app.state.practice_limiter.hit(f"practice:{user.id}")
    if not allowed:
        raise RateLimitedError(
            "You've answered a lot of questions this hour. Take a short break and try again soon.",
            details={"retry_after_seconds": int(retry_after) + 1},
        )
    row = graded_answer(user.id, question, body.answer)
    db.add(row)
    db.commit()
    return answer_out(row)


@router.get(
    "/careers/{slug}/questions/{question_id}/answers",
    response_model=list[AnswerOut],
    responses=error_responses(401, 404),
    summary="Your past answers to a question, newest first",
)
def my_answers(
    slug: str, question_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AnswerOut]:
    if get_question(_track_or_404(slug), question_id) is None:
        raise NotFoundError(f"Question '{question_id}' not found")
    rows = db.scalars(
        select(PracticeAnswer)
        .where(
            PracticeAnswer.user_id == user.id,
            PracticeAnswer.track == slug,
            PracticeAnswer.question_id == question_id,
        )
        .order_by(PracticeAnswer.created_at.desc())
        .limit(20)
    ).all()
    return [answer_out(r) for r in rows]


@router.get(
    "/careers/{slug}/progress",
    response_model=TrackProgress,
    responses=error_responses(401, 404),
    summary="Your progress on a career's questions",
)
def track_progress(
    slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TrackProgress:
    track = _track_or_404(slug)
    best = _best_scores(db, user, track)
    by_id = {x.id: x.difficulty for x in questions_for(track)}
    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}
    for qid in best:
        if qid in by_id:
            by_difficulty[by_id[qid]] += 1
    return TrackProgress(
        track=track,
        answered=sum(by_difficulty.values()),
        strong=sum(1 for qid, s in best.items() if s >= 85 and qid in by_id),
        by_difficulty=by_difficulty,
        total_questions=len(by_id),
    )
