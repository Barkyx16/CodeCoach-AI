"""Can these two attempts be compared? One rule, used everywhere (Volume 12, prompt 6;
docs/COMPARING_ATTEMPTS.md).

Given two attempts, the contract answers:

- ``comparable``: same question and version, same scale, rubric and kind of evaluator, both long
  enough to score, the same format and the same recorded in-app help. Scores and points compare.
- ``partially_comparable``: what was written compares (the points covered), with what differs
  named. Some differences leave the scores comparable too (the format, the help shown); others
  don't (a different rubric or question version, one too short to score).
- ``incompatible``: different questions, scales or kinds of evaluator. Each keeps its own score.
- ``unknown``: something it needs wasn't recorded; the missing fields are named. Nothing missing is
  filled in by guessing.

Coding submissions use the same rules (Volume 14, prompt 1), with their own facts: the problem for the
question, its test version for the question's version, the judge as the evaluator, a run or a
submission for the format (never compared with each other: a run checks the public tests only), and
whether the judge gave a verdict. No written answer's classification changes, so the version stays.

Drills, whiteboard designs and work samples too (Volume 15, prompt 4): the drill, prompt or brief for
the question, the version its points were checked against for the question's version, the built-in
rules as the evaluator, and whether a result was stored. Their result is a checklist of the item's
points, so a changed checklist or a changed version of the rules that check it isn't comparable at
all (a written answer's text still compares under another rubric; a checklist's ticks don't). Different
help is partly comparable, as it is everywhere. No earlier classification changes, so the version
stays.

The rules are versioned (``CONTRACT_VERSION``); every result says which version decided it, so an
export keeps the classification it was made with. Pure: the facts are gathered elsewhere
(app/services/comparisons_of_attempts.py), the decision is made only here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

CONTRACT_VERSION = 1

Outcome = Literal["comparable", "partially_comparable", "incompatible", "unknown"]
Format = Literal["single", "interview", "retry", "submit", "run"]
Source = Literal["rules", "ai", "person", "judge"]
Kind = Literal["written", "code", "drill", "whiteboard", "work_sample", "code_review"]

# Who graded it, by the recorded coach name: only names that are known. Anything else is unknown.
SOURCES: dict[str, Source] = {"built-in (offline)": "rules"}
SOURCE_LABEL: dict[str, str] = {
    "rules": "fixed rules",
    "ai": "an AI coach",
    "person": "a person",
    "judge": "the code judge",
}
FORMAT_LABEL: dict[str, str] = {
    "single": "on its own",
    "interview": "in a timed mock interview",
    "retry": "as a retry after a mock interview",
    "submit": "as a submission (every test)",
    "run": "as a run (the public tests only)",
}
HELP_NONE = "No in-app help recorded"
# Formats whose result is a checklist of the item's points, checked by built-in rules. A code
# review's are the exercise's authored defects, matched to its findings by fixed rules (Volume 18,
# prompt 4).
CHECKLISTS: frozenset[str] = frozenset({"drill", "whiteboard", "work_sample", "code_review"})
KIND_NOUN: dict[str, str] = {
    "written": "a written answer",
    "code": "code",
    "drill": "a drill",
    "whiteboard": "a whiteboard design",
    "work_sample": "a work sample",
    "code_review": "a code review",
}
ITEM: dict[str, str] = {
    "drill": "drill",
    "whiteboard": "prompt",
    "work_sample": "brief",
    "code_review": "exercise",
}


@dataclass(frozen=True)
class AttemptFacts:
    """What the contract may look at, as recorded. ``None`` means not recorded."""

    id: str
    track: str
    question_id: str
    question_version: int | None  # a written answer's is always known; a submission's test version may not be
    scale: str | None  # e.g. "0-100"
    rubric: str | None  # e.g. "v10"
    source: Source | None
    # A submission is "scored" when the judge gave a verdict on the learner's code, "not_judged" when it
    # didn't (the judge failed, or the attempt was only saved).
    scoring: Literal["scored", "too_short", "unknown", "not_judged"]
    format: Format | None
    help: tuple[str, ...] | None  # labels of in-app help shown before it, or (HELP_NONE,)
    help_recorded_from: date | None = None
    # An interview round answer's recorded format (Volume 13, prompt 3): it names what differed, and
    # changes no verdict.
    timed_minutes: int | None = None
    follow_up: str | None = None  # "answered" | "skipped": the interviewer's follow-up, part of the format
    kind: Kind = "written"


@dataclass(frozen=True)
class Reason:
    rule: str  # question | scale | source | rubric | question_version | scoring | format | help
    kind: Literal["incompatible", "unknown", "partial_text", "partial_conditions"]
    text: str


@dataclass(frozen=True)
class Classification:
    outcome: Outcome
    scores_comparable: bool
    points_comparable: bool
    reasons: tuple[Reason, ...]
    explanation: str
    contract_version: int = CONTRACT_VERSION
    rules: tuple[str, ...] = field(default=())


def _how(f: AttemptFacts) -> str:
    """How an attempt was given, as recorded: the round's time limit and follow-up when known."""
    if f.format == "interview":
        text = f"in a {f.timed_minutes}-minute mock interview" if f.timed_minutes else "in a mock interview"
        if f.follow_up == "answered":
            text += ", with a follow-up from the interviewer"
        elif f.follow_up == "skipped":
            text += ", with a follow-up you skipped"
        return text
    return FORMAT_LABEL[f.format] if f.format else "in a way that wasn't recorded"


def _format_text(a: AttemptFacts, b: AttemptFacts) -> str:
    """Which condition differed: a timed interview answer and one that wasn't timed say so."""
    if a.format == "interview" and b.format != "interview":
        return f"the conditions differed: the earlier one was timed (answered {_how(a)}); this one wasn't (answered {_how(b)})"
    if b.format == "interview" and a.format != "interview":
        return f"the conditions differed: the earlier one wasn't timed (answered {_how(a)}); this one was (answered {_how(b)})"
    return (
        f"the conditions differed: the earlier one was answered {FORMAT_LABEL[a.format or 'single']}, "
        f"the later one {FORMAT_LABEL[b.format or 'single']}"
    )


def _help_text(labels: tuple[str, ...]) -> str:
    return "none recorded" if labels == (HELP_NONE,) else ", ".join(x.lower() for x in labels)


def classify(a: AttemptFacts, b: AttemptFacts) -> Classification:
    """``a`` is the earlier attempt, ``b`` the later one."""
    reasons: list[Reason] = []
    code = a.kind == "code" or b.kind == "code"
    checklist = a.kind == b.kind and a.kind in CHECKLISTS
    item = ITEM.get(a.kind, "")

    if a.kind != b.kind:
        text = (
            "one is a written answer and the other is code"
            if {a.kind, b.kind} == {"written", "code"}
            else f"one is {KIND_NOUN[a.kind]} and the other is {KIND_NOUN[b.kind]}"
        )
        reasons.append(Reason("question", "incompatible", text))
    elif (a.track, a.question_id) != (b.track, b.question_id):
        if checklist and a.question_id == b.question_id:
            # A drill's prompt is worded for the career it was asked for.
            text = "the drill's prompt was worded for a different career each time"
        elif checklist:
            text = f"they're attempts at different {item}s"
        else:
            text = "they're attempts at different problems" if code else "they answer different questions"
        reasons.append(Reason("question", "incompatible", text))
    if a.scale is None or b.scale is None:
        reasons.append(Reason("scale", "unknown", "the score scale wasn't recorded"))
    elif a.scale != b.scale:
        reasons.append(
            Reason(
                "scale",
                "incompatible",
                f"they're scored on different scales ({a.scale} and {b.scale}); each keeps its own score, "
                "never converted",
            )
        )
    if a.source is None or b.source is None:
        reasons.append(Reason("source", "unknown", "who graded one of them wasn't recorded"))
    elif a.source != b.source:
        reasons.append(
            Reason(
                "source",
                "incompatible",
                f"different kinds of evaluator graded them ({SOURCE_LABEL[a.source]} and {SOURCE_LABEL[b.source]})",
            )
        )
    if a.rubric is None or b.rubric is None:
        reasons.append(Reason("rubric", "unknown", "which rubric graded one of them wasn't recorded"))
    elif a.rubric != b.rubric and checklist:
        reasons.append(
            Reason(
                "rubric",
                "incompatible",
                f"they were checked by different versions of the rules ({a.rubric} and {b.rubric}); "
                "each keeps its own result",
            )
        )
    elif a.rubric != b.rubric:
        reasons.append(
            Reason(
                "rubric",
                "partial_text",
                f"scored under different rubrics ({a.rubric} and {b.rubric}): compare what you wrote, not the numbers",
            )
        )
    if a.question_version is None or b.question_version is None:
        reasons.append(
            Reason(
                "question_version",
                "unknown",
                f"which version of the {item} one of them was checked against wasn't recorded"
                if checklist
                else "which version of the problem's tests judged one of them wasn't recorded",
            )
        )
    elif a.question_version != b.question_version and checklist:
        reasons.append(
            Reason(
                "question_version",
                "incompatible",
                f"the {item}'s points changed in between (version {a.question_version}, now "
                f"{b.question_version}); each keeps its own result",
            )
        )
    elif a.question_version != b.question_version:
        reasons.append(
            Reason(
                "question_version",
                "partial_text",
                f"the problem's tests changed in between (version {a.question_version}, now {b.question_version}): "
                "compare the code, not the counts"
                if code
                else f"the question was changed in between (version {a.question_version}, now {b.question_version}): "
                "compare what you wrote, not the numbers",
            )
        )
    if "not_judged" in (a.scoring, b.scoring):
        done = "assessed" if checklist else "judged"
        which = (
            f"neither was {done}"
            if a.scoring == b.scoring
            else f"the earlier one wasn't {done}"
            if a.scoring == "not_judged"
            else f"this one wasn't {done}"
        )
        result = "result" if checklist else "verdict"
        reasons.append(
            Reason("scoring", "incompatible", f"{which}, so there's no {result} to set beside the other")
        )
    elif "unknown" in (a.scoring, b.scoring):
        reasons.append(
            Reason("scoring", "unknown", "whether one of them was long enough to score wasn't recorded")
        )
    elif "too_short" in (a.scoring, b.scoring):
        which = "both were" if a.scoring == b.scoring else "one was"
        reasons.append(
            Reason(
                "scoring",
                "partial_text",
                f"{which} too short to score: compare what you wrote, not the numbers",
            )
        )
    if a.format is None or b.format is None:
        reasons.append(Reason("format", "unknown", "how one of them was given wasn't recorded"))
    elif code and a.format != b.format:
        reasons.append(
            Reason(
                "format",
                "incompatible",
                "a run checks the public tests only and a submission checks every test",
            )
        )
    elif a.format != b.format:
        reasons.append(Reason("format", "partial_conditions", _format_text(a, b)))
    if a.help is None or b.help is None:
        since = a.help_recorded_from or b.help_recorded_from
        when = f" (it's recorded from {since.day} {since:%b %Y})" if since else ""
        reasons.append(Reason("help", "unknown", f"in-app help before one of them wasn't recorded{when}"))
    elif set(a.help) != set(b.help):
        reasons.append(
            Reason(
                "help",
                "partial_conditions",
                f"the in-app help differed: before the earlier one, {_help_text(a.help)}; "
                f"before the later one, {_help_text(b.help)}",
            )
        )

    kind: Kind = "code" if code else a.kind if checklist else "written"
    kinds = {r.kind for r in reasons}
    if "incompatible" in kinds:
        decisive = tuple(r for r in reasons if r.kind == "incompatible")
        return _result("incompatible", False, False, decisive, kind)
    if "unknown" in kinds:
        missing = tuple(r for r in reasons if r.kind == "unknown")
        return _result("unknown", False, False, missing, kind)
    if reasons:
        scores = "partial_text" not in kinds
        return _result("partially_comparable", scores, True, tuple(reasons), kind)
    return _result("comparable", True, True, (), kind)


_LEAD: dict[str, str] = {
    "comparable": "Comparable: the same question and version, rubric, evaluator and conditions",
    "partially_comparable": "Partly comparable",
    "incompatible": "Not comparable",
    "unknown": "Can't tell whether these compare",
}
_CODE_COMPARABLE = "Comparable: the same problem and tests, judged the same way, with the same in-app help"
# Both checked by the same fixed rules; never self-assessed (none of these formats is).
_CHECKLIST_COMPARABLE = (
    "Comparable: the same {item} and version, checked by the same fixed rules, with the same in-app help"
)
_SAME_SCORES = {
    "written": ". The scores are on the same rubric, so both are shown",
    "code": ". The counts are from the same tests, so both are shown",
}
_SAME_CHECKS = ". The results are from the same checks by the same fixed rules, so both are shown"


def _result(
    outcome: Outcome, scores: bool, points: bool, reasons: tuple[Reason, ...], kind: Kind = "written"
) -> Classification:
    body = "; ".join(r.text for r in reasons)
    if outcome == "comparable" and kind == "code":
        lead = _CODE_COMPARABLE
    elif outcome == "comparable" and kind in CHECKLISTS:
        lead = _CHECKLIST_COMPARABLE.format(item=ITEM[kind])
    else:
        lead = _LEAD[outcome]
    text = f"{lead}: {body}" if body else lead
    if outcome == "partially_comparable" and scores:
        text += _SAME_SCORES.get(kind, _SAME_CHECKS)
    return Classification(
        outcome=outcome,
        scores_comparable=scores,
        points_comparable=points,
        reasons=reasons,
        explanation=f"{text}. (Comparison rules v{CONTRACT_VERSION})",
        rules=tuple(r.rule for r in reasons),
    )


# --- which attempts a trend may average ---------------------------------------------------------


def score_basis(f: AttemptFacts) -> tuple[str | None, Reason | None]:
    """The series a trend may put this attempt in: attempts whose scores are on the same scale, from
    the same kind of evaluator and rubric, and long enough to score (the rules above that decide
    whether two scores compare). A trend averages different questions within one series; the
    conditions (format, help) don't split it. Otherwise: why it isn't counted, never a guess."""
    if f.scoring == "too_short":
        return None, Reason("scoring", "partial_text", "too short to score")
    if f.scoring == "unknown":
        return None, Reason("scoring", "unknown", "whether it was long enough to score wasn't recorded")
    if f.scale is None:
        return None, Reason("scale", "unknown", "its score scale wasn't recorded")
    if f.source is None:
        return None, Reason("source", "unknown", "who graded it wasn't recorded")
    if f.rubric is None:
        return None, Reason("rubric", "unknown", "which rubric graded it wasn't recorded")
    return f"Graded by {SOURCE_LABEL[f.source]}, rubric {f.rubric}, scored {f.scale}", None


# --- which attempt an attempt is compared with --------------------------------------------------


def previous_of(ordered: list, index: int, revises: dict[str, str | None]) -> int | None:
    """The attempt an attempt is compared with, among one question's attempts oldest first: the one
    it revises (a stored link), else the one just before it. The same choice everywhere."""
    me = ordered[index]
    parent = revises.get(me.id)
    if parent is not None:
        for j in range(index - 1, -1, -1):
            if ordered[j].id == parent:
                return j
    return index - 1 if index > 0 else None
