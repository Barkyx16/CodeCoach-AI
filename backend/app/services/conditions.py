"""The conditions of a practice attempt (Volume 12, prompt 3; docs/ATTEMPT_CONDITIONS.md).

Worked out when read, from records the app already keeps: no separate help log.

- A coding attempt (a submission): the hints shown for the same problem and version before it was
  made (the coach's saved hints, one row per hint, so a request sent again after a lost reply is
  still one). Levels 1-3 are "Hint shown"; level 4 is "Solution revealed", because the app says it
  explains the full solution. A hint that failed was never saved, so it isn't shown.
- A career written answer: the Learn lessons that prepare for that question, read before it was
  answered while the question was at the answer's version, as "Hint shown".

Help is matched by question and version and belongs to the first attempt after it (in the same
mode): an attempt shows the help since the previous one. Help opened afterwards belongs to the
next attempt and never changes an earlier one. Nothing outside the app is known, and
accessibility settings (dictation, captions, screen readers, text size, contrast, reduced motion)
aren't inputs here at all. An attempt from before recording began, with nothing recorded, is "Not
recorded", never "none". Labels change no score, verdict or count.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers.questions import content_key
from app.learn import Unit, units_for
from app.models import (
    AIAction,
    AIInteraction,
    ContentVersion,
    LearnEvent,
    PracticeAnswer,
    Submission,
    TestCase,
    User,
)
from app.schemas.ai import HINT_LEVEL_NAMES
from app.schemas.conditions import AttemptConditions, HelpShown

RECORDED_FROM = datetime(2026, 11, 14, tzinfo=UTC)
SOLUTION_LEVEL = 4
NOTE = (
    "Only help shown in CodeCoach is recorded. Help from anywhere else isn't known, and "
    "accessibility settings such as dictation or captions are never counted as help."
)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def problem_version(db: Session, problem_id: int) -> int:
    """A coding problem's version now: its tests' version (versions only grow)."""
    return db.scalar(select(func.max(TestCase.version)).where(TestCase.problem_id == problem_id)) or 1


def problem_versions(db: Session, problem_ids: set[int]) -> dict[int, int]:
    """Several problems' versions in one statement."""
    found = dict(
        db.execute(
            select(TestCase.problem_id, func.max(TestCase.version))
            .where(TestCase.problem_id.in_(problem_ids))
            .group_by(TestCase.problem_id)
        ).all()
    )
    return {pid: found.get(pid) or 1 for pid in problem_ids}


def conditions(help: list[HelpShown], attempted_at: datetime, *, unknown: bool = False) -> AttemptConditions:
    help = sorted(help, key=lambda h: _aware(h.at))
    labels: list = []
    for h in help:
        if h.label not in labels:
            labels.append(h.label)
    if not labels:
        # Nothing recorded: from before recording began (or with help whose version isn't known),
        # that's "not recorded", never "none".
        labels = [
            "Not recorded" if unknown or _aware(attempted_at) < RECORDED_FROM else "No in-app help recorded"
        ]
    return AttemptConditions(labels=labels, help=help, recorded_from=RECORDED_FROM.date(), note=NOTE)


class Conditions:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- coding attempts --------------------------------------------------------------------------

    def for_submissions(self, subs: Iterable[Submission]) -> dict[str, AttemptConditions]:
        subs = list(subs)
        if not subs:
            return {}
        problem_ids = {s.problem_id for s in subs}
        current = problem_versions(self.db, problem_ids)
        hints: dict[int, list[AIInteraction]] = defaultdict(list)
        for h in self.db.scalars(
            select(AIInteraction)
            .where(
                AIInteraction.user_id == self.user.id,
                AIInteraction.problem_id.in_(problem_ids),
                AIInteraction.action == AIAction.HINT,
                AIInteraction.response.is_not(None),  # shown: a failed request saved nothing
            )
            .order_by(AIInteraction.created_at)
        ):
            hints[h.problem_id].append(h)

        # Every attempt of these problems in the same mode, to find the one before each: help
        # belongs to the first attempt after it, so an attempt shows only what came since the last.
        attempts: dict[tuple[int, str], list[datetime]] = defaultdict(list)
        for pid, mode, at in self.db.execute(
            select(Submission.problem_id, Submission.mode, Submission.created_at)
            .where(Submission.user_id == self.user.id, Submission.problem_id.in_(problem_ids))
            .order_by(Submission.created_at)
        ):
            attempts[(pid, str(mode))].append(_aware(at))

        def version(recorded: int | None, pid: int) -> int | None:
            # Not recorded: known only if the problem never had another version.
            return recorded if recorded is not None else (1 if current[pid] == 1 else None)

        out: dict[str, AttemptConditions] = {}
        for s in subs:
            at = _aware(s.created_at)
            since = max((t for t in attempts[(s.problem_id, str(s.mode))] if t < at), default=None)
            sv = version(s.content_version, s.problem_id)
            shown: list[HelpShown] = []
            unknown = False
            for h in hints[s.problem_id]:
                when = _aware(h.created_at)
                if when >= at:
                    break  # afterwards: the next attempt's, never this one's
                if since is not None and when <= since:
                    continue  # before the previous attempt: that one's
                hv = version(h.content_version, s.problem_id)
                if hv is None or sv is None:
                    unknown = True
                    continue
                if hv != sv or h.hint_level is None:
                    continue
                level = h.hint_level
                shown.append(
                    HelpShown(
                        label="Solution revealed" if level >= SOLUTION_LEVEL else "Hint shown",
                        detail=f"Level {level} hint ({HINT_LEVEL_NAMES.get(level, 'hint')})"
                        + (": the full explanation" if level >= SOLUTION_LEVEL else ""),
                        at=h.created_at,
                    )
                )
            out[s.id] = conditions(shown, s.created_at, unknown=unknown)
        return out

    def for_submission(self, sub: Submission) -> AttemptConditions:
        return self.for_submissions([sub])[sub.id]

    # --- career written answers -------------------------------------------------------------------

    @staticmethod
    def _prepares(u: Unit, question_id: str) -> bool:
        return question_id in u.question_ids or (
            u.practice.kind == "question" and u.practice.ref_id == question_id
        )

    def for_answers(self, answers: Iterable[PracticeAnswer]) -> dict[str, AttemptConditions]:
        answers = list(answers)
        if not answers:
            return {}
        units: dict[str, Unit] = {}
        for track in {a.track for a in answers}:
            for u in units_for(track):
                units[u.id] = u
        reads: dict[str, list[LearnEvent]] = defaultdict(list)
        if units:
            for e in self.db.scalars(
                select(LearnEvent)
                .where(
                    LearnEvent.user_id == self.user.id,
                    LearnEvent.kind == "read",
                    LearnEvent.unit_id.in_(list(units)),
                )
                .order_by(LearnEvent.created_at)
            ):
                reads[e.unit_id].append(e)
        if not any(reads.values()):
            # No lesson read: nothing to match, and nothing more to look up.
            return {a.id: conditions([], a.created_at) for a in answers}
        keys = {content_key(a.track, a.question_id) for a in answers}
        history: dict[str, list[tuple[int, datetime]]] = defaultdict(list)
        for v in self.db.scalars(
            select(ContentVersion).where(
                ContentVersion.content_type == "question", ContentVersion.content_id.in_(keys)
            )
        ):
            history[v.content_id].append((v.version, _aware(v.created_at)))

        def version_at(key: str, at: datetime) -> int:
            """The question's version when something happened (1 until a correction was published)."""
            return max((v for v, when in history[key] if when <= _aware(at)), default=1)

        # Every answer to these questions, to find the one before each (help belongs to the first
        # answer after it).
        earlier: dict[tuple[str, str], list[datetime]] = defaultdict(list)
        for track, qid, at in self.db.execute(
            select(PracticeAnswer.track, PracticeAnswer.question_id, PracticeAnswer.created_at)
            .where(
                PracticeAnswer.user_id == self.user.id,
                PracticeAnswer.question_id.in_({a.question_id for a in answers}),
            )
            .order_by(PracticeAnswer.created_at)
        ):
            earlier[(track, qid)].append(_aware(at))

        out: dict[str, AttemptConditions] = {}
        for a in answers:
            key = content_key(a.track, a.question_id)
            at = _aware(a.created_at)
            since = max((t for t in earlier[(a.track, a.question_id)] if t < at), default=None)
            av = a.content_version or 1
            shown: list[HelpShown] = []
            for u in units.values():
                if u.track != a.track or not self._prepares(u, a.question_id):
                    continue
                for e in reads[u.id]:
                    when = _aware(e.created_at)
                    if when >= at:
                        break
                    if since is not None and when <= since:
                        continue  # the previous answer's
                    if version_at(key, e.created_at) != av:
                        continue  # read while the question was at another version
                    shown.append(
                        HelpShown(label="Hint shown", detail=f"Lesson “{u.title}” read", at=e.created_at)
                    )
                    break  # one entry per lesson
            out[a.id] = conditions(shown, a.created_at)
        return out

    def for_answer(self, answer: PracticeAnswer) -> AttemptConditions:
        return self.for_answers([answer])[answer.id]
