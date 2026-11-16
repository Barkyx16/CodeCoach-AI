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
- A code-review exercise, a sample-answer comparison or a work sample (Volume 15, prompt 3): the Learn
  lessons that prepare it, by the same rule, and the format's own answer when it was shown before the
  attempt, which the attempt has always stored: a code review written after the authored review was
  shown (`after_reveal`), a comparison sent after its explanation was opened (`revealed_early`), each
  "Solution revealed". A work sample's section hints are shown to everyone with the brief, so they're
  not help (like a question's tips); no lesson prepares a brief yet.

Help is matched by question and version and belongs to the first attempt after it (in the same
mode): an attempt shows the help since the previous one. Help opened afterwards belongs to the
next attempt and never changes an earlier one. Nothing outside the app is known, and
accessibility settings (dictation, captions, screen readers, text size, contrast, reduced motion)
aren't inputs here at all. An attempt from before recording began, with nothing recorded, is "Not
recorded", never "none". Labels change no score, verdict or count.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers.questions import content_key
from app.learn import UNIT_INDEX, Unit, units_for
from app.models import (
    AIAction,
    AIInteraction,
    CodeReviewAttempt,
    ComparisonAttempt,
    ContentVersion,
    DrillAttempt,
    InterviewStatus,
    InterviewTurn,
    LabReveal,
    LearnEvent,
    PracticeAnswer,
    PracticeMode,
    PracticeSession,
    Problem,
    ScenarioAttempt,
    Submission,
    TestCase,
    TurnRole,
    User,
    WhiteboardAttempt,
    WorkSampleAttempt,
)
from app.schemas.ai import HINT_LEVEL_NAMES
from app.schemas.conditions import (
    AttemptConditions,
    CheckMade,
    HelpShown,
    InterviewFormat,
    RoundConditions,
)

RECORDED_FROM = datetime(2026, 11, 14, tzinfo=UTC)
# Interview round answers record their conditions when saved from this day (Volume 13, prompt 3).
ROUND_RECORDED_FROM = datetime(2026, 11, 15, tzinfo=UTC)
# Drills, scenarios and whiteboards from this day (Volume 14, prompt 4).
FORMATS_RECORDED_FROM = datetime(2026, 11, 15, tzinfo=UTC)
# A debugging exercise's explanation opened, and a coding interview's checked messages, from this day
# (Volume 16, prompt 2). Before it, neither was recorded anywhere.
LAB_RECORDED_FROM = datetime(2026, 11, 16, tzinfo=UTC)
DEBUGGING_DIR = Path(__file__).resolve().parents[1] / "seed" / "debugging"
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
    "whiteboard:<id>", "code_review:<slug>", "comparison:<id>", "work_sample:<id>", "debug:<slug>"),
    or None if there's no such thing."""
    from app.comparisons import BY_ID as COMPARISONS
    from app.drills import BY_ID as DRILLS
    from app.drills import RUBRIC_VERSION as DRILL_VERSION
    from app.reviews import BY_SLUG as REVIEWS
    from app.scenarios import get_scenario
    from app.whiteboard import BY_ID as PROMPTS
    from app.worksamples import BY_ID as BRIEFS

    kind, _, cid = ref.partition(":")
    if kind == "scenario":
        sc = get_scenario(cid)
        return sc.version if sc is not None else None
    if kind == "drill":
        return DRILL_VERSION if cid in DRILLS else None  # a drill's version is its rubric's
    if kind == "whiteboard":
        p = PROMPTS.get(cid)
        return p.version if p is not None else None
    if kind == "code_review":
        ex = REVIEWS.get(cid)
        return ex.version if ex is not None else None
    if kind == "comparison":
        ls = COMPARISONS.get(cid)
        return ls.version if ls is not None else None
    if kind == "work_sample":
        b = BRIEFS.get(cid)
        return b.version if b is not None else None
    if kind == "debug":
        return debug_versions().get(cid)
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
    unrecorded: str | None = None,
) -> AttemptConditions:
    """`unrecorded`: a kind of help that wasn't recorded yet when this attempt was made (said, never
    guessed); with nothing else found, the attempt is "Not recorded"."""
    help = sorted(help, key=lambda h: _aware(h.at))
    labels: list = []
    for h in help:
        if h.label not in labels:
            labels.append(h.label)
    if not labels:
        # Nothing recorded: from before recording began (or with help whose version isn't known),
        # that's "not recorded", never "none".
        labels = [
            "Not recorded"
            if unknown or unrecorded or _aware(attempted_at) < recorded_from
            else "No in-app help recorded"
        ]
    return AttemptConditions(
        labels=labels, help=help, recorded_from=recorded_from.date(), note=NOTE, unrecorded=unrecorded
    )


@lru_cache(maxsize=1)
def debug_versions() -> dict[str, int]:
    """Each debugging exercise's version now, from its authored file (app/seed/debugging)."""
    out: dict[str, int] = {}
    for path in sorted(DEBUGGING_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["slug"]] = int(data["lab"]["version"])
    return out


def _day(dt: datetime) -> str:
    return f"{dt.day} {dt:%b %Y}"


LAB_UNRECORDED = (
    f"Opening the exercise's explanation and repair wasn't recorded before {_day(LAB_RECORDED_FROM)}, "
    "so whether it was opened before this attempt isn't known."
)


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


def interview_format(session: PracticeSession) -> InterviewFormat:
    """A coding interview's format, from what it stores: never help."""
    minutes = (session.duration_seconds or 0) // 60 or None
    ending: str | None = {
        InterviewStatus.COMPLETED: "finished",
        InterviewStatus.ABANDONED: "ended_early",
        InterviewStatus.EXPIRED: "time_expired",
    }.get(session.status)
    recorded = _aware(session.started_at) >= LAB_RECORDED_FROM
    sent = [t for t in session.turns if t.role == TurnRole.CANDIDATE]
    checks: list[CheckMade] = []
    for n, t in enumerate(sent, start=1):
        if (t.meta or {}).get("checked"):
            checks.append(
                CheckMade(what=f"Message {n}", detail="checked before it was sent", at=t.created_at)
            )
    read = (session.plan or {}).get("feedback_read")
    confirmed = read.get("confirmed") if isinstance(read, dict) else None
    feedback_line = None
    if isinstance(read, dict) and read.get("checked") and read.get("at"):
        checks.append(
            CheckMade(
                what="The feedback's material",
                detail="checked before it was scored",
                at=datetime.fromisoformat(read["at"]),
            )
        )
        feedback_line = "the feedback's material checked before it was scored"
    elif isinstance(confirmed, dict) and confirmed.get("at"):
        # "I've checked this" before an unchecked ending (Volume 16, prompt 3), compared when scored.
        when = "before time ran out" if ending == "time_expired" else "before it was scored"
        at = datetime.fromisoformat(confirmed["at"])
        if confirmed.get("matched"):
            checks.append(CheckMade(what="The feedback's material", detail=f"checked {when}", at=at))
            feedback_line = f"the feedback's material checked {when}"
        else:
            changed = ", ".join(confirmed.get("changed") or [])
            checks.append(
                CheckMade(
                    what="An earlier version of the feedback's material",
                    detail=f"checked; it changed after ({changed})",
                    at=at,
                )
            )
            feedback_line = "an earlier version of the feedback's material checked"
    text = f"A {minutes}-minute coding interview" if minutes else "A coding interview"
    text += {
        "finished": ", finished",
        "ended_early": ", ended early",
        "time_expired": "; time ran out",
        None: ", in progress",
    }[ending]
    messages = sum(1 for c in checks if c.what.startswith("Message "))
    if not recorded:
        text += "; whether messages were checked before they were sent wasn't recorded then"
    elif sent:
        text += f"; {messages} of {len(sent)} {'message' if len(sent) == 1 else 'messages'} checked before sending"
    else:
        text += "; no messages sent"
    if feedback_line is not None:
        text += f"; {feedback_line}"
    elif ending is not None and isinstance(read, dict) and read.get("checked") is False:
        text += "; the feedback's material not checked"
    return InterviewFormat(
        timed_minutes=minutes,
        ending=ending,
        checks_recorded=recorded,
        checks=sorted(checks, key=lambda c: _aware(c.at)),
        text=text + ".",
    )


class Conditions:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- coding attempts --------------------------------------------------------------------------

    def _hints(self, problem_ids: set[int]) -> dict[int, list[AIInteraction]]:
        """The hints shown for these problems, oldest first (a failed request saved nothing)."""
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
        return hints

    def _reveals(self, problem_ids: set[int]) -> dict[int, list[LabReveal]]:
        """When this learner opened these debugging exercises' explanations, oldest first."""
        out: dict[int, list[LabReveal]] = defaultdict(list)
        for r in self.db.scalars(
            select(LabReveal)
            .where(LabReveal.user_id == self.user.id, LabReveal.problem_id.in_(problem_ids))
            .order_by(LabReveal.created_at)
        ):
            out[r.problem_id].append(r)
        return out

    def for_submissions(self, subs: Iterable[Submission]) -> dict[str, AttemptConditions]:
        """Hints for the problem; for a debugging exercise also its explanation and repair opened
        (Volume 16, prompt 2) and any lesson that prepares it, each since the previous attempt."""
        subs = list(subs)
        if not subs:
            return {}
        problem_ids = {s.problem_id for s in subs}
        current = problem_versions(self.db, problem_ids)
        hints = self._hints(problem_ids)

        # Every attempt of these problems in the same mode, to find the one before each: help
        # belongs to the first attempt after it, so an attempt shows only what came since the last.
        attempts: dict[tuple[int, str], list[datetime]] = defaultdict(list)
        for pid, mode, at in self.db.execute(
            select(Submission.problem_id, Submission.mode, Submission.created_at)
            .where(Submission.user_id == self.user.id, Submission.problem_id.in_(problem_ids))
            .order_by(Submission.created_at)
        ):
            attempts[(pid, str(mode))].append(_aware(at))

        # A debugging exercise's attempt records the exercise's version (it always has: the lab and
        # that column arrived together), so it's told apart without another read.
        debug = [s for s in subs if s.lab_version is not None]
        reveals: dict[int, list[LabReveal]] = defaultdict(list)
        lessons: dict[str, tuple[list[HelpShown], bool]] = {}
        if debug:
            reveals = self._reveals({s.problem_id for s in debug})
            if any(ref.startswith("debug:") for u in UNIT_INDEX.values() for ref in u.prepares):
                slugs = dict(
                    self.db.execute(
                        select(Problem.id, Problem.slug).where(Problem.id.in_({s.problem_id for s in debug}))
                    ).all()
                )
                earlier = {
                    (slugs[pid], mode): times for (pid, mode), times in attempts.items() if pid in slugs
                }
                lessons = self._lesson_help(
                    [
                        (s.id, f"debug:{slugs[s.problem_id]}", s.lab_version or 0, s.created_at, str(s.mode))
                        for s in debug
                    ],
                    earlier,
                )

        def version(recorded: int | None, pid: int) -> int | None:
            # Not recorded: known only if the problem never had another version.
            return recorded if recorded is not None else (1 if current[pid] == 1 else None)

        out: dict[str, AttemptConditions] = {}
        for s in subs:
            at = _aware(s.created_at)
            since = max((t for t in attempts[(s.problem_id, str(s.mode))] if t < at), default=None)
            shown, unknown = self._hints_between(
                hints[s.problem_id], since, at, s.content_version, version, s.problem_id
            )
            unrecorded = None
            if s.lab_version is not None:
                if at < LAB_RECORDED_FROM:
                    unrecorded = LAB_UNRECORDED
                for r in reveals[s.problem_id]:
                    when = _aware(r.created_at)
                    if when >= at:
                        break  # afterwards: the next attempt's
                    if since is not None and when <= since:
                        continue  # before the previous attempt: that one's
                    if r.lab_version != s.lab_version:
                        continue  # opened while the exercise was at another version
                    shown.append(
                        HelpShown(
                            label="Solution revealed",
                            detail=f"The exercise's explanation and a correct repair (version {r.lab_version})",
                            at=r.created_at,
                        )
                    )
                    break  # one opening per attempt: asking again is the same one
                read, read_unknown = lessons.get(s.id, ([], False))
                shown.extend(read)
                unknown = unknown or read_unknown
            out[s.id] = conditions(shown, s.created_at, unknown=unknown, unrecorded=unrecorded)
        return out

    @staticmethod
    def _hints_between(
        rows: list[AIInteraction],
        since: datetime | None,
        at: datetime,
        recorded_version: int | None,
        version,
        problem_id: int,
        *,
        title: str | None = None,
        started_at: datetime | None = None,
    ) -> tuple[list[HelpShown], bool]:
        """The hints shown after `since` and before `at`, at the attempt's version: each as "Hint shown"
        (levels 1-3) or "Solution revealed" (level 4). With `title`, a coding interview's: each says
        which problem and whether it was before or during the interview, in the hint panel's words."""
        sv = version(recorded_version, problem_id)
        shown: list[HelpShown] = []
        unknown = False
        for h in rows:
            when = _aware(h.created_at)
            if when >= at:
                break  # afterwards: the next attempt's, never this one's
            if since is not None and when <= since:
                continue  # before the previous attempt: that one's
            hv = version(h.content_version, problem_id)
            if hv is None or sv is None:
                unknown = True
                continue
            if hv != sv or h.hint_level is None:
                continue
            level = h.hint_level
            name = HINT_LEVEL_NAMES.get(level, "hint")
            if title is None:
                detail = f"Level {level} hint ({name})" + (
                    ": the full explanation" if level >= SOLUTION_LEVEL else ""
                )
            else:
                during = started_at is not None and when >= _aware(started_at)
                detail = f"Level {level} hint, “{name.capitalize()}”, on {title}, " + (
                    "during the interview" if during else "before the interview"
                )
            shown.append(
                HelpShown(
                    label="Solution revealed" if level >= SOLUTION_LEVEL else "Hint shown",
                    detail=detail,
                    at=h.created_at,
                )
            )
        return shown, unknown

    def for_submission(self, sub: Submission) -> AttemptConditions:
        return self.for_submissions([sub])[sub.id]

    # --- coding interviews ------------------------------------------------------------------------

    def for_interviews(self, sessions: Iterable[PracticeSession]) -> dict[str, AttemptConditions]:
        """A coding interview (Volume 16, prompt 2): the hints for its problem shown before it ended,
        since the previous coding interview of that problem ended, at the problem's version when it
        started; and its format, read from what it stores: the time limit, how it ended, and each
        message and the feedback checked before it was sent, once it's over. Checking is never help. A career
        interview's answers have their own (`for_answers`); they aren't described here."""
        rows = [
            x
            for x in sessions
            if x.mode == PracticeMode.INTERVIEW
            and x.problem_id is not None
            and x.status != InterviewStatus.IN_PROGRESS  # described once it's over
        ]
        if not rows:
            return {}
        problem_ids = {x.problem_id for x in rows if x.problem_id is not None}
        current = problem_versions(self.db, problem_ids)
        hints = self._hints(problem_ids)
        titles = dict(
            self.db.execute(select(Problem.id, Problem.title).where(Problem.id.in_(problem_ids))).all()
        )
        ends: dict[int, list[datetime]] = defaultdict(list)
        for pid, ended in self.db.execute(
            select(PracticeSession.problem_id, PracticeSession.ended_at).where(
                PracticeSession.user_id == self.user.id,
                PracticeSession.mode == PracticeMode.INTERVIEW,
                PracticeSession.problem_id.in_(problem_ids),
                PracticeSession.ended_at.is_not(None),
            )
        ):
            if pid is not None and ended is not None:
                ends[pid].append(_aware(ended))

        def version(recorded: int | None, pid: int) -> int | None:
            return recorded if recorded is not None else (1 if current[pid] == 1 else None)

        now = datetime.now(UTC)
        out: dict[str, AttemptConditions] = {}
        for x in rows:
            pid = x.problem_id
            assert pid is not None
            end = _aware(x.ended_at) if x.ended_at else now  # closed: ended_at is set; `now` is a guard
            since = max((t for t in ends[pid] if t < end), default=None)
            plan = x.plan or {}
            shown, unknown = self._hints_between(
                hints[pid],
                since,
                end,
                plan.get("content_version"),
                version,
                pid,
                title=f"“{titles.get(pid, 'this problem')}”",
                started_at=x.started_at,
            )
            c = conditions(shown, x.started_at, unknown=unknown)
            out[x.id] = c.model_copy(update={"interview": interview_format(x)})
        return out

    def for_interview(self, session: PracticeSession) -> AttemptConditions | None:
        return self.for_interviews([session]).get(session.id)

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

    def for_code_reviews(self, rows: Iterable[CodeReviewAttempt]) -> dict[str, AttemptConditions]:
        """Lessons that prepare the exercise, and its authored review when it was shown first."""
        rows = list(rows)
        earlier = self._times(
            CodeReviewAttempt, CodeReviewAttempt.exercise_slug, {r.exercise_slug for r in rows}
        )
        shown = {
            r.id: [
                HelpShown(
                    label="Solution revealed",
                    detail="The authored review was shown before this was written",
                    at=r.created_at,
                )
            ]
            for r in rows
            if r.after_reveal
        }
        return self._practice(
            [(r.id, f"code_review:{r.exercise_slug}", r.exercise_version, r.created_at, "") for r in rows],
            earlier,
            shown,
        )

    def for_comparisons(self, rows: Iterable[ComparisonAttempt]) -> dict[str, AttemptConditions]:
        """Lessons that prepare the comparison, and its explanation when it was opened first."""
        rows = list(rows)
        earlier = self._times(ComparisonAttempt, ComparisonAttempt.lesson_id, {r.lesson_id for r in rows})
        shown = {
            r.id: [
                HelpShown(
                    label="Solution revealed",
                    detail="The explanation was opened before this was sent",
                    at=r.created_at,
                )
            ]
            for r in rows
            if r.revealed_early
        }
        return self._practice(
            [(r.id, f"comparison:{r.lesson_id}", r.lesson_version, r.created_at, "") for r in rows],
            earlier,
            shown,
        )

    def for_work_samples(self, rows: Iterable[WorkSampleAttempt]) -> dict[str, AttemptConditions]:
        """Lessons that prepare the brief (none yet). Its section hints are shown to everyone."""
        rows = list(rows)
        earlier = self._times(WorkSampleAttempt, WorkSampleAttempt.brief_id, {r.brief_id for r in rows})
        return self._practice(
            [(r.id, f"work_sample:{r.brief_id}", r.brief_version, r.created_at, "") for r in rows], earlier
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
        stored: dict[str, list[HelpShown]] | None = None,
    ) -> dict[str, AttemptConditions]:
        """(id, ref, version, made at, mode) → the lessons preparing `ref` read since the previous
        attempt at it (in the same mode), before this one, while it was at this version; plus any
        help the attempt itself stored (`stored`, by id)."""
        found = self._lesson_help(items, earlier)
        made = {item_id: at for item_id, _, _, at, _ in items}
        return {
            item_id: conditions(
                list((stored or {}).get(item_id, [])) + shown,
                made[item_id],
                unknown=unknown,
                recorded_from=FORMATS_RECORDED_FROM,
            )
            for item_id, (shown, unknown) in found.items()
        }

    def _lesson_help(
        self,
        items: list[tuple[str, str, int, datetime, str]],
        earlier: dict[tuple[str, str], list[datetime]],
    ) -> dict[str, tuple[list[HelpShown], bool]]:
        """The lesson reads `_practice` describes, by id, and whether one's version wasn't known."""
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
        out: dict[str, tuple[list[HelpShown], bool]] = {}
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
            out[item_id] = (shown, unknown)
        return out
