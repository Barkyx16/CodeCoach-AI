"""The conditions of a practice attempt (Volume 12, prompt 3; docs/ATTEMPT_CONDITIONS.md).

Worked out when read, from records the app already keeps: no separate help log.

- A coding attempt (a submission): the hints shown for the same problem and version before it was
  made (the coach's saved hints, one row per hint, so a request sent again after a lost reply is
  still one). Levels 1-3 are "Hint shown"; level 4 is "Solution revealed", because the app says it
  explains the full solution. A hint that failed was never saved, so it isn't shown.
- A career written answer: the Learn lessons that prepare for that question, read before it was
  answered while the question was at the answer's version, as "Hint shown".

- An answer given in an interview round (Volume 13, prompt 3): the same help, worked out when the
  answer is saved and stored with the round's turn, with the round's format (timed, the
  interviewer's follow-up asked or skipped, ended early). A round answer from before that began
  has its format but its help is "Not recorded"; nothing is worked out for it later.
- A drill attempt, a scenario run or a whiteboard attempt (Volume 14, prompt 4): the Learn lessons
  that prepare that drill or scenario (`Unit.prepares`), read before it while it was at the
  attempt's version, as "Hint shown". A lesson read records the version of what it prepares from
  15 Nov 2026 (`learn_events.detail`); an earlier read matches only what has never had another
  version. No lesson prepares a whiteboard prompt, so a whiteboard attempt has none to show.

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
from app.learn import UNIT_INDEX, Unit, units_for
from app.models import (
    AIAction,
    AIInteraction,
    ContentVersion,
    DrillAttempt,
    InterviewStatus,
    InterviewTurn,
    LearnEvent,
    PracticeAnswer,
    PracticeSession,
    ScenarioAttempt,
    Submission,
    TestCase,
    User,
    WhiteboardAttempt,
)
from app.schemas.ai import HINT_LEVEL_NAMES
from app.schemas.conditions import AttemptConditions, HelpShown, RoundConditions

RECORDED_FROM = datetime(2026, 11, 14, tzinfo=UTC)
# Interview round answers record their conditions when saved from this day (Volume 13, prompt 3).
ROUND_RECORDED_FROM = datetime(2026, 11, 15, tzinfo=UTC)
# Drills, scenarios and whiteboards from this day (Volume 14, prompt 4).
FORMATS_RECORDED_FROM = datetime(2026, 11, 15, tzinfo=UTC)
ENDED_EARLY = {InterviewStatus.ABANDONED, InterviewStatus.EXPIRED}
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


def practice_version(ref: str) -> int | None:
    """The version now of what a lesson prepares ("scenario:<id>", "drill:<id>",
    "whiteboard:<id>"), or None if there's no such thing."""
    from app.drills import BY_ID as DRILLS
    from app.drills import RUBRIC_VERSION as DRILL_VERSION
    from app.scenarios import get_scenario
    from app.whiteboard import BY_ID as PROMPTS

    kind, _, cid = ref.partition(":")
    if kind == "scenario":
        sc = get_scenario(cid)
        return sc.version if sc is not None else None
    if kind == "drill":
        return DRILL_VERSION if cid in DRILLS else None  # a drill's version is its rubric's
    if kind == "whiteboard":
        p = PROMPTS.get(cid)
        return p.version if p is not None else None
    return None


def prepared_versions(u: Unit) -> dict[str, int]:
    """What a lesson read records (from 15 Nov 2026): the version of each thing it prepares now."""
    return {ref: v for ref in u.prepares if (v := practice_version(ref)) is not None}


def _help_words(c: AttemptConditions) -> str:
    return (
        "none recorded" if c.labels == ["No in-app help recorded"] else ", ".join(x.lower() for x in c.labels)
    )


def help_changed(earlier: AttemptConditions | None, later: AttemptConditions | None) -> str | None:
    """One line for a comparison when the help before two attempts differed, or wasn't recorded
    for one of them, in the comparison contract's words; None when it was the same."""
    if earlier is None or later is None:
        return None
    if "Not recorded" in earlier.labels or "Not recorded" in later.labels:
        since = later.recorded_from
        return (
            f"In-app help before one of them wasn't recorded (it's recorded from {since.day} {since:%b %Y})."
        )
    if set(earlier.labels) != set(later.labels):
        return (
            f"The in-app help differed: before the earlier one, {_help_words(earlier)}; "
            f"before this one, {_help_words(later)}."
        )
    return None


def conditions(
    help: list[HelpShown],
    attempted_at: datetime,
    *,
    unknown: bool = False,
    recorded_from: datetime = RECORDED_FROM,
) -> AttemptConditions:
    help = sorted(help, key=lambda h: _aware(h.at))
    labels: list = []
    for h in help:
        if h.label not in labels:
            labels.append(h.label)
    if not labels:
        # Nothing recorded: from before recording began (or with help whose version isn't known),
        # that's "not recorded", never "none".
        labels = [
            "Not recorded" if unknown or _aware(attempted_at) < recorded_from else "No in-app help recorded"
        ]
    return AttemptConditions(labels=labels, help=help, recorded_from=recorded_from.date(), note=NOTE)


def round_text(timed_minutes: int | None, follow_up: str | None, ended_early: bool) -> str:
    """One line for a round answer's format: how it was given, never help."""
    text = (
        f"A {timed_minutes}-minute timed mock interview" if timed_minutes else "A mock interview, not timed"
    )
    if follow_up == "answered":
        text += "; the interviewer asked a follow-up, which you answered"
    elif follow_up == "skipped":
        text += "; the interviewer asked a follow-up, which you skipped"
    else:
        text += "; no follow-up"
    if ended_early:
        text += "; the round ended early"
    return text + "."


def _round(
    meta: dict, status: InterviewStatus, duration_seconds: int | None, recorded: bool
) -> RoundConditions:
    follow_up = (meta.get("followup") or {}).get("status")
    minutes = (meta.get("conditions") or {}).get("timed_minutes")
    if minutes is None and duration_seconds:
        minutes = duration_seconds // 60
    ended = status in ENDED_EARLY
    return RoundConditions(
        recorded=recorded,
        timed_minutes=minutes,
        follow_up=follow_up if follow_up in ("answered", "skipped") else None,
        ended_early=ended,
        text=round_text(minutes, follow_up, ended),
    )


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

    def record_for_round(self, row: PracticeAnswer, timed_minutes: int | None) -> dict:
        """What an interview round stores with an answer when it's saved: the help worked out now
        (so a lesson read later can't change it) and the round's time limit."""
        c = self._worked_out([row])[row.id]
        return {
            "v": 1,
            "labels": list(c.labels),
            "help": [h.model_dump(mode="json") for h in c.help],
            "timed_minutes": timed_minutes,
        }

    def for_answers(
        self, answers: Iterable[PracticeAnswer], *, rounds_possible: bool = True
    ) -> dict[str, AttemptConditions]:
        """Every answer's conditions: an interview round's as recorded with it, the others worked
        out from what's kept. `rounds_possible=False`: the caller knows none of them was given in a
        round (an answer saved on its own question page), so the round lookup is skipped."""
        answers = list(answers)
        if not answers:
            return {}
        if not rounds_possible:
            return self._worked_out(answers)
        rounds = {
            aid: (meta or {}, status, duration)
            for aid, meta, status, duration in self.db.execute(
                select(
                    InterviewTurn.answer_id,
                    InterviewTurn.meta,
                    PracticeSession.status,
                    PracticeSession.duration_seconds,
                )
                .join(PracticeSession, PracticeSession.id == InterviewTurn.session_id)
                .where(
                    PracticeSession.user_id == self.user.id,
                    InterviewTurn.answer_id.in_([a.id for a in answers]),
                )
            )
            if aid is not None
        }
        out = self._worked_out([a for a in answers if a.id not in rounds])
        for a in answers:
            if a.id not in rounds:
                continue
            meta, status, duration = rounds[a.id]
            stored = meta.get("conditions")
            if stored:
                out[a.id] = AttemptConditions(
                    labels=stored["labels"],
                    help=[HelpShown.model_validate(h) for h in stored.get("help", [])],
                    recorded_from=ROUND_RECORDED_FROM.date(),
                    note=NOTE,
                    round=_round(meta, status, duration, recorded=True),
                )
            else:
                # From before rounds recorded it: nothing is worked out now, so a lesson read since
                # can't be taken for help that was there.
                out[a.id] = AttemptConditions(
                    labels=["Not recorded"],
                    help=[],
                    recorded_from=ROUND_RECORDED_FROM.date(),
                    note=NOTE,
                    round=_round(meta, status, duration, recorded=False),
                )
        return out

    def _worked_out(self, answers: list[PracticeAnswer]) -> dict[str, AttemptConditions]:
        """Written answers' help, worked out from the lessons read (docs/ATTEMPT_CONDITIONS.md)."""
        if not answers:
            return {}
        # Only lessons that prepare one of these questions can count; most questions have none, and
        # then there's nothing to look up.
        units: dict[str, Unit] = {}
        for track in {a.track for a in answers}:
            asked = {a.question_id for a in answers if a.track == track}
            for u in units_for(track):
                if any(self._prepares(u, qid) for qid in asked):
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

    def for_answer(self, answer: PracticeAnswer, *, rounds_possible: bool = True) -> AttemptConditions:
        return self.for_answers([answer], rounds_possible=rounds_possible)[answer.id]

    # --- drills, scenarios and whiteboards (Volume 14, prompt 4) ------------------------------

    def for_drills(self, rows: Iterable[DrillAttempt]) -> dict[str, AttemptConditions]:
        rows = list(rows)
        earlier = self._times(DrillAttempt, DrillAttempt.drill_id, {r.drill_id for r in rows})
        return self._practice(
            [(r.id, f"drill:{r.drill_id}", r.rubric_version, r.created_at, "") for r in rows], earlier
        )

    def for_scenarios(self, rows: Iterable[ScenarioAttempt]) -> dict[str, AttemptConditions]:
        """A run's help is what came before it started, counted apart for assessed runs and "try
        another approach" explorations (as a Run and a Submit are)."""
        rows = list(rows)
        earlier = self._times(
            ScenarioAttempt, ScenarioAttempt.scenario_id, {r.scenario_id for r in rows}, ScenarioAttempt.mode
        )
        return self._practice(
            [(r.id, f"scenario:{r.scenario_id}", r.version, r.created_at, r.mode) for r in rows], earlier
        )

    def for_whiteboards(self, rows: Iterable[WhiteboardAttempt]) -> dict[str, AttemptConditions]:
        rows = list(rows)
        earlier = self._times(WhiteboardAttempt, WhiteboardAttempt.prompt_id, {r.prompt_id for r in rows})
        return self._practice(
            [(r.id, f"whiteboard:{r.prompt_id}", r.prompt_version, r.created_at, "") for r in rows], earlier
        )

    def _times(
        self, model, content_col, ids: set[str], mode_col=None
    ) -> dict[tuple[str, str], list[datetime]]:
        """When each of this learner's attempts at these items was made, by item (and mode)."""
        if not ids:
            return {}
        cols = [content_col, model.created_at] + ([mode_col] if mode_col is not None else [])
        out: dict[tuple[str, str], list[datetime]] = defaultdict(list)
        for row in self.db.execute(
            select(*cols)
            .where(model.user_id == self.user.id, content_col.in_(ids))
            .order_by(model.created_at)
        ):
            out[(row[0], row[2] if mode_col is not None else "")].append(_aware(row[1]))
        return out

    def _practice(
        self,
        items: list[tuple[str, str, int, datetime, str]],
        earlier: dict[tuple[str, str], list[datetime]],
    ) -> dict[str, AttemptConditions]:
        """(id, ref, version, made at, mode) → the lessons preparing `ref` read since the previous
        attempt at it (in the same mode), before this one, while it was at this version."""
        if not items:
            return {}
        refs = {ref for _, ref, _, _, _ in items}
        units = {u.id: u for u in UNIT_INDEX.values() if refs & set(u.prepares)}
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
        out: dict[str, AttemptConditions] = {}
        for item_id, ref, version, made, mode in items:
            at = _aware(made)
            cid = ref.partition(":")[2]
            since = max((t for t in earlier.get((cid, mode), []) if t < at), default=None)
            shown: list[HelpShown] = []
            unknown = False
            for u in units.values():
                if ref not in u.prepares:
                    continue
                for e in reads[u.id]:
                    when = _aware(e.created_at)
                    if when >= at:
                        break
                    if since is not None and when <= since:
                        continue  # the previous attempt's
                    read_version = ((e.detail or {}).get("prepares") or {}).get(ref)
                    if read_version is None and practice_version(ref) == 1:
                        read_version = 1  # read before versions were recorded; it has only ever had one
                    if read_version is None:
                        unknown = True  # read while it may have been at another version
                        continue
                    if read_version != version:
                        continue  # read while it was at another version
                    shown.append(
                        HelpShown(label="Hint shown", detail=f"Lesson “{u.title}” read", at=e.created_at)
                    )
                    break  # one entry per lesson
            out[item_id] = conditions(shown, made, unknown=unknown, recorded_from=FORMATS_RECORDED_FROM)
        return out
