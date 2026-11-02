"""Question rounds: mock interviews made of one career's written questions.

They live in the same tables as coding interviews (practice_sessions + interview_turns), follow
the same rules (one interview in progress per user, a server-side deadline applied lazily,
abandon), and appear in the same interview history.

    start ──▶ interviewer asks question 0
    answer i / skip i ──▶ graded (answer) and saved as a PracticeAnswer; next question asked
    after the last question ──▶ COMPLETED          deadline ──▶ EXPIRED      abandon ──▶ ABANDONED

Answers are idempotent per question: a repeated submit (double click, retry after a dropped
response) for a question that already has an answer returns the current state without grading
again. Answering a question that hasn't been asked yet is a conflict. No AI calls are made, so
rounds never use the AI budget; each answer counts toward the practice-answer hourly limit.
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.answers import OFFLINE_COACH, answer_out, graded_answer
from app.careers.grading import grade
from app.careers.questions import Question, get_question, questions_for
from app.errors import ConflictError, NotFoundError, RateLimitedError
from app.models import (
    InterviewStatus,
    InterviewTurn,
    PracticeAnswer,
    PracticeMode,
    PracticeSession,
    TurnRole,
    User,
)
from app.schemas.interview import InterviewStart, RoundAnswer, RoundQuestion, RoundSkip, RoundSummary
from app.services import engagement

ROUND = ("motivation", "knowledge", "situational", "behavioral", "leadership")
DEFAULT_TRACK = "software-engineer"


def _now() -> datetime:
    return datetime.now(UTC)


# Extra slots go to the substantive kinds (never a second "why this job?").
FILL_ORDER = ("behavioral", "situational", "knowledge", "leadership")


def pick_round(
    pool: list[Question], answered: set[str], rng: random.Random, size: int = len(ROUND)
) -> list[Question]:
    """One question of every kind the level has, then extra slots round-robin over FILL_ORDER;
    unanswered questions first, returned in interview order (why you → knowledge → scenario →
    a time you did it → leading others)."""
    shuffled = pool[:]
    rng.shuffle(shuffled)
    ranked = sorted(shuffled, key=lambda q: q.id in answered)  # stable: unanswered first
    picked: list[Question] = []

    def take(kind: str) -> bool:
        q = next((x for x in ranked if x.kind == kind and x not in picked), None)
        if q is not None:
            picked.append(q)
        return q is not None

    for kind in ROUND:
        take(kind)
    while len(picked) < size and any([take(k) for k in FILL_ORDER if len(picked) < size]):
        pass
    for q in ranked:  # kinds outside ROUND, if a career ever has them
        if len(picked) >= size:
            break
        if q not in picked:
            picked.append(q)
    order = {k: i for i, k in enumerate(ROUND)}
    return sorted(picked[:size], key=lambda q: order.get(q.kind, len(ROUND)))


class QuestionRounds:
    def __init__(self, db: Session, practice_limiter=None):
        self.db = db
        self.limiter = practice_limiter

    # --- commands ---------------------------------------------------------------------

    def start(self, user: User, body: InterviewStart) -> PracticeSession:
        track = body.track or user.career_track or DEFAULT_TRACK
        if track not in CATALOG:
            raise NotFoundError(f"Career '{track}' not found")
        difficulty = body.difficulty or "easy"
        pool = [q for q in questions_for(track) if q.difficulty == difficulty]
        answered = set(
            self.db.scalars(
                select(PracticeAnswer.question_id).where(
                    PracticeAnswer.user_id == user.id, PracticeAnswer.track == track
                )
            ).all()
        )
        picked = pick_round(pool, answered, random.Random())
        if not picked:
            raise NotFoundError("No questions are available at this level")
        now = _now()
        duration = body.duration_minutes * 60
        session = PracticeSession(
            user_id=user.id,
            mode=PracticeMode.QUESTIONS,
            status=InterviewStatus.IN_PROGRESS,
            duration_seconds=duration,
            started_at=now,
            deadline_at=now + timedelta(seconds=duration),
            track=track,
            plan={"difficulty": difficulty, "question_ids": [q.id for q in picked]},
            provider=OFFLINE_COACH,
        )
        self.db.add(session)
        self._ask(session, 0)
        self.db.flush()
        return session

    def answer(self, user: User, session: PracticeSession, body: RoundAnswer) -> None:
        if self._already_handled(session, body.question_index):
            return  # repeated submit: keep the first answer, don't grade again
        question = self._current(session, body.question_index)
        if self.limiter is not None:
            allowed, retry_after = self.limiter.hit(f"practice:{user.id}")
            if not allowed:
                raise RateLimitedError(
                    "You've answered a lot of questions this hour. Take a short break and try again soon.",
                    details={"retry_after_seconds": int(retry_after) + 1},
                )
        text = body.answer.strip()
        row = graded_answer(user.id, question, text)
        self.db.add(row)
        self.db.flush()
        read = engagement.for_career_answer(question, text, grade(question, text))
        self._add(
            session,
            TurnRole.CANDIDATE,
            text,
            body.question_index,
            answer_id=row.id,
            meta={"source": body.source, "engagement": read.model_dump(mode="json")},
        )
        self._advance(session, body.question_index)

    def skip(self, session: PracticeSession, body: RoundSkip) -> None:
        if self._already_handled(session, body.question_index):
            return
        self._current(session, body.question_index)
        self._add(session, TurnRole.CANDIDATE, "", body.question_index, meta={"skipped": True})
        self._advance(session, body.question_index)

    # --- reads ------------------------------------------------------------------------

    def questions_out(self, session: PracticeSession) -> list[RoundQuestion]:
        ids: list[str] = (session.plan or {}).get("question_ids", [])
        replies = {t.question_index: t for t in session.turns if t.role == TurnRole.CANDIDATE}
        answers = {
            a.id: a
            for a in self.db.scalars(
                select(PracticeAnswer).where(
                    PracticeAnswer.id.in_([t.answer_id for t in replies.values() if t.answer_id])
                )
            ).all()
        }
        current = self.current_index(session)
        out = []
        for i, qid in enumerate(ids):
            q = get_question(session.track or "", qid)
            if q is None:
                continue
            reply = replies.get(i)
            status: Literal["pending", "current", "answered", "skipped"]
            if reply is not None:
                status = "skipped" if (reply.meta or {}).get("skipped") else "answered"
            else:
                status = (
                    "current" if i == current and session.status == InterviewStatus.IN_PROGRESS else "pending"
                )
            row = answers.get(reply.answer_id) if reply is not None and reply.answer_id else None
            out.append(
                RoundQuestion(
                    index=i,
                    id=q.id,
                    title=q.title,
                    prompt=q.prompt,
                    kind=q.kind,
                    difficulty=q.difficulty,
                    status=status,
                    answer=answer_out(row) if row is not None else None,
                )
            )
        return out

    @staticmethod
    def summary(questions: list[RoundQuestion]) -> RoundSummary:
        answers = [q.answer for q in questions if q.status == "answered" and q.answer is not None]
        missed = Counter(p.label for a in answers for p in a.points if not p.covered)
        return RoundSummary(
            answered=len(answers),
            skipped=sum(q.status == "skipped" for q in questions),
            unanswered=sum(q.status in ("pending", "current") for q in questions),
            average_score=round(sum(a.score for a in answers) / len(answers)) if answers else None,
            focus=[label for label, _ in missed.most_common(3)],
        )

    @staticmethod
    def current_index(session: PracticeSession) -> int:
        return sum(1 for t in session.turns if t.role == TurnRole.CANDIDATE)

    # --- internals --------------------------------------------------------------------

    @staticmethod
    def _already_handled(session: PracticeSession, index: int) -> bool:
        return any(t.role == TurnRole.CANDIDATE and t.question_index == index for t in session.turns)

    def _current(self, session: PracticeSession, index: int) -> Question:
        expected = self.current_index(session)
        if index != expected:
            raise ConflictError(
                "That question hasn't been asked yet. Answer the current question first.",
                code="question_not_current",
                details={"current_question_index": expected},
            )
        ids = (session.plan or {}).get("question_ids", [])
        q = get_question(session.track or "", ids[index]) if index < len(ids) else None
        if q is None:
            raise NotFoundError("Question not found")
        return q

    def _ask(self, session: PracticeSession, index: int) -> None:
        ids = (session.plan or {}).get("question_ids", [])
        q = get_question(session.track or "", ids[index])
        assert q is not None
        self._add(session, TurnRole.INTERVIEWER, q.prompt, index)

    def _advance(self, session: PracticeSession, index: int) -> None:
        total = len((session.plan or {}).get("question_ids", []))
        if index + 1 < total:
            self._ask(session, index + 1)
        else:
            session.status = InterviewStatus.COMPLETED
            session.ended_at = _now()

    @staticmethod
    def _add(
        session: PracticeSession,
        role: TurnRole,
        content: str,
        index: int,
        *,
        answer_id: str | None = None,
        meta: dict | None = None,
    ) -> None:
        session.turns.append(
            InterviewTurn(
                seq=len(session.turns),
                role=role,
                phase=None,
                content=content,
                question_index=index,
                answer_id=answer_id,
                meta=meta,
            )
        )
