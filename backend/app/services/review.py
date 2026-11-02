"""The post-interview review: what happened, one to three grounded improvements, retries.

Everything is built from what was stored during the interview (turns with their recorded times,
graded answers, the rubric evaluation), so opening a review never re-runs an evaluator or uses
the AI budget. Audio is never kept, so the "replay" is the transcript. Coding correctness is
only ever the judge's: interview code isn't run, and the review says so.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.answers import answer_out, graded_answer
from app.careers.questions import Question, get_question
from app.errors import ConflictError, NotFoundError, RateLimitedError
from app.models import (
    InterviewPhase,
    InterviewRetry,
    InterviewStatus,
    PracticeAnswer,
    PracticeMode,
    PracticeSession,
    TurnRole,
    User,
)
from app.models import (
    ReviewItem as QueueRow,
)
from app.schemas.careers import AnswerOut
from app.schemas.interview import Engagement, InterviewProblem
from app.schemas.review import (
    Comparison,
    Dimension,
    EvidenceLink,
    Improvement,
    InterviewReview,
    PracticeAction,
    RetryIn,
    ReviewItem,
)
from app.services.activity import evaluator_key
from app.services.question_rounds import QuestionRounds

STATUS_LABEL = {
    InterviewStatus.COMPLETED: "Completed",
    InterviewStatus.ABANDONED: "Ended early",
    InterviewStatus.EXPIRED: "Time ran out",
    InterviewStatus.IN_PROGRESS: "In progress",
}
DIMENSION_TITLE = {
    "problem_solving": "Problem solving",
    "communication": "Communication",
    "code_quality": "Code quality",
    "complexity_analysis": "Complexity analysis",
    "testing": "Testing",
}
DIMENSION_GROUP = {
    "problem_solving": "Answer content",
    "communication": "Structure and clarity",
    "code_quality": "Technical reasoning",
    "complexity_analysis": "Technical reasoning",
    "testing": "Technical reasoning",
}
DIMENSION_PHASES = {
    "problem_solving": (InterviewPhase.APPROACH, InterviewPhase.CLARIFY),
    "communication": (InterviewPhase.CLARIFY, InterviewPhase.APPROACH),
    "code_quality": (InterviewPhase.CODING,),
    "complexity_analysis": (InterviewPhase.COMPLEXITY,),
    "testing": (InterviewPhase.WRAP_UP,),
}
PHASE_LABEL = {
    InterviewPhase.CLARIFY: "Clarify",
    InterviewPhase.APPROACH: "Approach",
    InterviewPhase.CODING: "Code",
    InterviewPhase.COMPLEXITY: "Complexity",
    InterviewPhase.WRAP_UP: "Test and wrap up",
}
LINE = re.compile(r"\bline (\d+)\b", re.I)
TRANSCRIBED = (
    "Spoken and transcribed by your browser's speech recognition, then sent as text. Recognition mistakes "
    "you didn't fix can lower the score; your voice itself isn't analysed or kept."
)


def _excerpt(text: str | None, limit: int = 160) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _elapsed(s: PracticeSession) -> int | None:
    if s.ended_at is None:
        return None
    start = s.started_at if s.started_at.tzinfo else s.started_at.replace(tzinfo=UTC)
    end = s.ended_at if s.ended_at.tzinfo else s.ended_at.replace(tzinfo=UTC)
    return max(0, int((end - start).total_seconds()))


class InterviewReviews:
    def __init__(self, db: Session, practice_limiter=None):
        self.db = db
        self.rounds = QuestionRounds(db, practice_limiter)
        self.limiter = practice_limiter

    def build(self, user: User, s: PracticeSession) -> InterviewReview:
        if s.status == InterviewStatus.IN_PROGRESS:
            raise ConflictError(
                "This interview is still in progress. Finish or end it to see the review.",
                code="interview_in_progress",
                details={"interview_id": s.id},
            )
        return self._round(user, s) if s.mode == PracticeMode.QUESTIONS else self._coding(s)

    # --- question rounds --------------------------------------------------------------------

    def _round(self, user: User, s: PracticeSession) -> InterviewReview:
        track = s.track or ""
        coding_career = CATALOG[track].has_coding if track in CATALOG else False
        questions = self.rounds.questions_out(s)
        asked = {t.question_index: t for t in s.turns if t.role == TurnRole.INTERVIEWER}
        replies = {t.question_index: t for t in s.turns if t.role == TurnRole.CANDIDATE}
        retries = Counter(
            self.db.scalars(
                select(InterviewRetry.question_index).where(InterviewRetry.session_id == s.id)
            ).all()
        )
        queued = set(
            self.db.scalars(
                select(QueueRow.question_id).where(
                    QueueRow.user_id == user.id, QueueRow.track == track, QueueRow.removed.is_(False)
                )
            ).all()
        )
        items: list[ReviewItem] = []
        for q in questions:
            reply = replies.get(q.index)
            meta = (reply.meta or {}) if reply else {}
            source = meta.get("source")
            status = (
                "answered"
                if q.status == "answered"
                else "skipped"
                if q.status == "skipped"
                else "not_reached"
            )
            items.append(
                ReviewItem(
                    key=f"q{q.index}",
                    index=q.index,
                    title=q.title,
                    prompt=q.prompt,
                    kind=q.kind,
                    role="question",
                    status=status,
                    asked_at=asked[q.index].created_at if q.index in asked else None,
                    answer_text=q.answer.answer if q.answer else None,
                    answered_at=reply.created_at if reply and q.answer else None,
                    source=source,
                    transcription_note=TRANSCRIBED if source in ("voice", "mixed") else None,
                    engagement=Engagement.model_validate(meta["engagement"])
                    if meta.get("engagement")
                    else None,
                    feedback=q.answer,
                    dimensions=self._answer_dimensions(q.answer, q.kind, source, coding_career)
                    if q.answer
                    else [],
                    retries=retries.get(q.index, 0),
                    in_review_queue=q.id in queued,
                    question_id=q.id,
                )
            )
        answered = [i for i in items if i.feedback]
        skipped = [i for i in items if i.status == "skipped"]
        missing = [i for i in items if i.status == "not_reached"]
        notices: list[str] = []
        if s.status == InterviewStatus.ABANDONED:
            notices.append(
                f"Ended early: {len(answered)} of {len(items)} questions answered. Only answered questions have feedback."
            )
        elif s.status == InterviewStatus.EXPIRED:
            notices.append(
                f"Time ran out with {len(missing)} question{'s' if len(missing) != 1 else ''} not reached. Those have no feedback."
            )
        if skipped:
            notices.append(
                f"{len(skipped)} skipped question{'s have' if len(skipped) != 1 else ' has'} no answer and no feedback."
            )
        if any(i.source in ("voice", "mixed") for i in answered):
            notices.append(
                "Some answers were spoken and transcribed by your browser; check them for recognition mistakes."
            )

        improvements: list[Improvement] = []
        missed: dict[str, list[ReviewItem]] = {}
        advice: dict[str, str] = {}
        for i in answered:
            for p in i.feedback.points if i.feedback else []:
                if not p.covered:
                    missed.setdefault(p.label, []).append(i)
                    advice.setdefault(p.label, p.advice)
        for label, its in sorted(missed.items(), key=lambda kv: -len(kv[1]))[:2]:
            worst = min(its, key=lambda i: i.feedback.score if i.feedback else 0)
            improvements.append(
                Improvement(
                    title=label,
                    why=f"{advice[label]} Missing in {len(its)} of {len(answered)} answers.",
                    evidence=[
                        EvidenceLink(item_key=i.key, label=i.title, excerpt=_excerpt(i.answer_text))
                        for i in its[:3]
                    ],
                    practice=PracticeAction(label=f"Retry “{worst.title}”", retry_index=worst.index),
                )
            )
        unanswered = skipped + missing
        if unanswered and len(improvements) < 3:
            first = unanswered[0]
            improvements.append(
                Improvement(
                    title="Answer the questions you didn't get to",
                    why="Unanswered questions give no evidence either way. Answering them shows where you stand.",
                    evidence=[
                        EvidenceLink(item_key=i.key, label=i.title, excerpt=None) for i in unanswered[:3]
                    ],
                    practice=PracticeAction(label=f"Answer “{first.title}”", retry_index=first.index),
                )
            )
        scores = [i.feedback.score for i in answered if i.feedback]
        evaluator = ", ".join(sorted({i.feedback.coach for i in answered if i.feedback})) or None
        overall = [
            Dimension(
                name="Answer content",
                status="evaluated" if answered else "not_evaluated",
                summary=(
                    f"Average {round(sum(scores) / len(scores))}/100 across {len(scores)} answered "
                    f"question{'s' if len(scores) != 1 else ''}; scores show how much of what interviewers "
                    "listen for each answer covered."
                    if scores
                    else "No answers, so nothing was evaluated."
                ),
            ),
        ]
        disclaimer = "Scores come from the built-in rubric: they measure what an answer covers and how it's structured, not whether it's correct."
        if not coding_career:
            disclaimer += (
                " The feedback is about interview communication; it isn't professional or clinical guidance."
            )
        return InterviewReview(
            id=s.id,
            kind="questions",
            track=track,
            career_title=CATALOG[track].title if track in CATALOG else None,
            problem=None,
            status=s.status,
            status_label=STATUS_LABEL[s.status],
            completed=s.status == InterviewStatus.COMPLETED,
            started_at=s.started_at,
            ended_at=s.ended_at,
            elapsed_seconds=_elapsed(s),
            time_limit_seconds=s.duration_seconds or 0,
            notices=notices,
            items=items,
            overall=overall,
            improvements=improvements,
            evaluation_available=bool(answered),
            evaluator=evaluator,
            disclaimer=disclaimer,
            final_code=None,
        )

    @staticmethod
    def _answer_dimensions(
        a: AnswerOut, kind: str, source: str | None, coding_career: bool
    ) -> list[Dimension]:
        covered = [p.label for p in a.points if p.covered]
        missing = [p.label for p in a.points if not p.covered]
        dims = [
            Dimension(
                name="Answer content",
                status="evaluated",
                summary=f"{a.score}/100 ({a.rating}). Covered {len(covered)} of {len(a.points)} points.",
                points=[f"Covered: {c}" for c in covered] + [f"Missing: {m}" for m in missing],
            ),
            Dimension(
                name="Structure and clarity",
                status="evaluated",
                summary=f"{a.word_count} words." + ("" if a.notes else " Length and structure were fine."),
                points=list(a.notes),
            ),
            Dimension(
                name="Reasoning",
                status="not_evaluated",
                summary=(
                    "Not judged: the built-in coach checks coverage and structure, not whether the reasoning "
                    "or the decisions described are right."
                    + (
                        ""
                        if coding_career
                        else " For clinical, safety or legal points, check a qualified source."
                    )
                ),
            ),
        ]
        if source in ("voice", "mixed"):
            dims.append(
                Dimension(
                    name="Spoken delivery",
                    status="not_evaluated",
                    summary="Not measured: only the transcript is scored. Accent, pace and tone aren't analysed or kept.",
                )
            )
        else:
            dims.append(Dimension(name="Spoken delivery", status="not_applicable", summary="Typed answer."))
        return dims

    # --- coding interviews ------------------------------------------------------------------

    def _coding(self, s: PracticeSession) -> InterviewReview:
        ev = s.evaluation or {}
        turns = list(s.turns)
        items = [
            ReviewItem(
                key=f"turn-{t.seq}",
                index=t.seq,
                title=("Interviewer" if t.role == TurnRole.INTERVIEWER else "You")
                + (f" · {PHASE_LABEL[t.phase]}" if t.phase else ""),
                prompt=t.content,
                kind=t.phase.value if t.phase else "",
                role="interviewer" if t.role == TurnRole.INTERVIEWER else "candidate",
                status="said",
                asked_at=t.created_at,
                answer_text=None,
                answered_at=None,
                source=(t.meta or {}).get("source"),
                transcription_note=TRANSCRIBED
                if (t.meta or {}).get("source") in ("voice", "mixed")
                else None,
                engagement=Engagement.model_validate((t.meta or {})["engagement"])
                if (t.meta or {}).get("engagement")
                else None,
                feedback=None,
                dimensions=[],
                retries=0,
                in_review_queue=False,
            )
            for t in turns
        ]
        code_lines = (s.final_code or "").splitlines()

        def evidence_for(dim: str, text: str) -> list[EvidenceLink]:
            links: list[EvidenceLink] = []
            for phase in DIMENSION_PHASES.get(dim, ()):
                turn = next((t for t in turns if t.role == TurnRole.CANDIDATE and t.phase == phase), None)
                if turn is not None:
                    links.append(
                        EvidenceLink(
                            item_key=f"turn-{turn.seq}",
                            label=f"Your answer in {PHASE_LABEL[phase]}",
                            excerpt=_excerpt(turn.content),
                        )
                    )
                    break
            else:
                links.append(EvidenceLink(item_key="", label="You didn't answer in this phase", excerpt=None))
            for m in LINE.finditer(text):
                n = int(m.group(1))
                if 1 <= n <= len(code_lines):
                    links.append(
                        EvidenceLink(
                            item_key="code", label=f"Line {n} of your code", excerpt=code_lines[n - 1].strip()
                        )
                    )
            return links

        scores = {x["dimension"]: x for x in ev.get("scores", [])}
        overall: list[Dimension] = []
        for dim in DIMENSION_TITLE:
            x = scores.get(dim)
            overall.append(
                Dimension(
                    name=f"{DIMENSION_GROUP[dim]}: {DIMENSION_TITLE[dim]}",
                    status="evaluated" if x else "not_evaluated",
                    summary=f"{x['score']} of 4. {x['evidence']}" if x else "Not evaluated.",
                    evidence=evidence_for(dim, x["evidence"]) if x else [],
                )
            )
        overall.append(
            Dimension(
                name="Spoken delivery",
                status="not_evaluated",
                summary="Not measured: spoken answers are scored from their transcript only.",
            )
        )
        overall.append(
            Dimension(
                name="Code execution",
                status="not_evaluated",
                summary="Not run: code written in an interview isn't sent to the judge, so there's no pass/fail here. "
                "Open the problem and submit to get a verdict.",
            )
        )
        notices: list[str] = []
        if s.status == InterviewStatus.ABANDONED:
            notices.append("Ended early. The feedback covers only what happened before you stopped.")
        elif s.status == InterviewStatus.EXPIRED:
            notices.append("Time ran out before you finished. The feedback covers what happened in time.")
        if not ev:
            notices.append("Feedback is unavailable for this interview.")
        if any(i.source in ("voice", "mixed") for i in items):
            notices.append(
                "Some messages were spoken and transcribed by your browser; check them for recognition mistakes."
            )
        improvements: list[Improvement] = []
        problem_href = f"/problems/{s.problem.slug}" if s.problem else "/problems"
        for dim, x in sorted(scores.items(), key=lambda kv: kv[1]["score"])[:2]:
            if x["score"] >= 3:
                break
            improvements.append(
                Improvement(
                    title=DIMENSION_TITLE.get(dim, dim),
                    why=x["evidence"],
                    evidence=evidence_for(dim, x["evidence"]),
                    practice=PracticeAction(label="Practise this problem", href=problem_href),
                )
            )
        if not improvements and ev.get("improvements"):
            improvements.append(
                Improvement(
                    title="Next time",
                    why=ev["improvements"][0],
                    evidence=[],
                    practice=PracticeAction(label="Practise this problem", href=problem_href),
                )
            )
        p = s.problem
        return InterviewReview(
            id=s.id,
            kind="coding",
            track=None,
            career_title=None,
            problem=InterviewProblem(slug=p.slug, title=p.title, difficulty=p.difficulty) if p else None,
            status=s.status,
            status_label=STATUS_LABEL[s.status],
            completed=s.status == InterviewStatus.COMPLETED,
            started_at=s.started_at,
            ended_at=s.ended_at,
            elapsed_seconds=_elapsed(s),
            time_limit_seconds=s.duration_seconds or 0,
            notices=notices,
            items=items,
            overall=overall,
            improvements=improvements,
            evaluation_available=bool(ev),
            evaluator=s.provider,
            disclaimer=f"Rubric feedback by {s.provider or 'the built-in interviewer'}"
            + (f" (confidence: {ev['confidence']})" if ev.get("confidence") else "")
            + ". Confidence describes the evaluator, not your answer. Pass/fail only ever comes from the judge.",
            final_code=s.final_code,
        )

    # --- retries ----------------------------------------------------------------------------

    def _question(self, s: PracticeSession, index: int) -> Question:
        if s.mode != PracticeMode.QUESTIONS:
            raise ConflictError(
                "Only question-round questions can be retried one at a time.", code="wrong_interview_kind"
            )
        ids = (s.plan or {}).get("question_ids", [])
        q = get_question(s.track or "", ids[index]) if 0 <= index < len(ids) else None
        if q is None:
            raise NotFoundError("Question not found in this interview")
        return q

    def retry(self, user: User, s: PracticeSession, index: int, body: RetryIn) -> Comparison:
        if s.status == InterviewStatus.IN_PROGRESS:
            raise ConflictError(
                "Finish or end the interview before retrying a question.", code="interview_in_progress"
            )
        q = self._question(s, index)
        if self.limiter is not None:
            allowed, retry_after = self.limiter.hit(f"practice:{user.id}")
            if not allowed:
                raise RateLimitedError(
                    "You've answered a lot of questions this hour. Take a short break and try again soon.",
                    details={"retry_after_seconds": int(retry_after) + 1},
                )
        row = graded_answer(user.id, q, body.answer.strip())
        self.db.add(row)
        self.db.flush()
        original = next(
            (t.answer_id for t in s.turns if t.role == TurnRole.CANDIDATE and t.question_index == index), None
        )
        self.db.add(
            InterviewRetry(
                user_id=user.id,
                session_id=s.id,
                question_index=index,
                original_answer_id=original,
                retry_answer_id=row.id,
            )
        )
        self.db.commit()
        return self.compare(s, index)

    def compare(self, s: PracticeSession, index: int) -> Comparison:
        q = self._question(s, index)
        turn = next((t for t in s.turns if t.role == TurnRole.CANDIDATE and t.question_index == index), None)
        original = self.db.get(PracticeAnswer, turn.answer_id) if turn and turn.answer_id else None
        retry_ids = self.db.scalars(
            select(InterviewRetry.retry_answer_id)
            .where(InterviewRetry.session_id == s.id, InterviewRetry.question_index == index)
            .order_by(InterviewRetry.created_at)
        ).all()
        retries = [a for a in (self.db.get(PracticeAnswer, rid) for rid in retry_ids) if a is not None]
        latest = retries[-1] if retries else None
        orig_out = answer_out(original) if original else None
        latest_out = answer_out(latest) if latest else None
        improved: list[str] = []
        still: list[str] = []
        newly: list[str] = []
        comparable = False
        note = "No retry yet."
        if latest_out is not None:
            now = {p.label: p.covered for p in latest_out.points}
            if orig_out is None:
                improved = [k for k, v in now.items() if v]
                still = [k for k, v in now.items() if not v]
                note = "There was no original answer to compare with."
            else:
                before = {p.label: p.covered for p in orig_out.points}
                improved = [k for k, v in now.items() if v and not before.get(k, False)]
                still = [k for k, v in now.items() if not v and not before.get(k, False)]
                newly = [k for k, v in now.items() if not v and before.get(k, False)]
                ka = evaluator_key(original.provider, original.feedback or {}) if original else ""
                kb = evaluator_key(latest.provider, latest.feedback or {}) if latest else ""
                comparable = ka == kb
                note = (
                    f"Both scored by {kb}, so the scores compare directly."
                    if comparable
                    else f"Scored by different evaluators ({ka} vs {kb}), so the scores aren't directly comparable; "
                    "compare the points covered instead."
                )
        return Comparison(
            question_title=q.title,
            prompt=q.prompt,
            original=orig_out,
            retries=[answer_out(a) for a in retries],
            latest=latest_out,
            comparable=comparable,
            comparability_note=note,
            improved=improved,
            still_missing=still,
            newly_missing=newly,
            score_change=(latest_out.score - orig_out.score)
            if latest_out and orig_out and comparable
            else None,
        )
