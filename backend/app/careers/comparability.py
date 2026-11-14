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
Format = Literal["single", "interview", "retry"]
Source = Literal["rules", "ai", "person"]

# Who graded it, by the recorded coach name: only names that are known. Anything else is unknown.
SOURCES: dict[str, Source] = {"built-in (offline)": "rules"}
SOURCE_LABEL: dict[str, str] = {"rules": "fixed rules", "ai": "an AI coach", "person": "a person"}
FORMAT_LABEL: dict[str, str] = {
    "single": "on its own",
    "interview": "in a timed mock interview",
    "retry": "as a retry after a mock interview",
}
HELP_NONE = "No in-app help recorded"


@dataclass(frozen=True)
class AttemptFacts:
    """What the contract may look at, as recorded. ``None`` means not recorded."""

    id: str
    track: str
    question_id: str
    question_version: int
    scale: str | None  # e.g. "0-100"
    rubric: str | None  # e.g. "v10"
    source: Source | None
    scoring: Literal["scored", "too_short", "unknown"]
    format: Format | None
    help: tuple[str, ...] | None  # labels of in-app help shown before it, or (HELP_NONE,)
    help_recorded_from: date | None = None


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


def _help_text(labels: tuple[str, ...]) -> str:
    return "none recorded" if labels == (HELP_NONE,) else ", ".join(x.lower() for x in labels)


def classify(a: AttemptFacts, b: AttemptFacts) -> Classification:
    """``a`` is the earlier attempt, ``b`` the later one."""
    reasons: list[Reason] = []

    if (a.track, a.question_id) != (b.track, b.question_id):
        reasons.append(Reason("question", "incompatible", "they answer different questions"))
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
    elif a.rubric != b.rubric:
        reasons.append(
            Reason(
                "rubric",
                "partial_text",
                f"scored under different rubrics ({a.rubric} and {b.rubric}): compare what you wrote, not the numbers",
            )
        )
    if a.question_version != b.question_version:
        reasons.append(
            Reason(
                "question_version",
                "partial_text",
                f"the question was changed in between (version {a.question_version}, now {b.question_version}): "
                "compare what you wrote, not the numbers",
            )
        )
    if "unknown" in (a.scoring, b.scoring):
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
    elif a.format != b.format:
        reasons.append(
            Reason(
                "format",
                "partial_conditions",
                f"the conditions differed: the earlier one was answered {FORMAT_LABEL[a.format]}, "
                f"the later one {FORMAT_LABEL[b.format]}",
            )
        )
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

    kinds = {r.kind for r in reasons}
    if "incompatible" in kinds:
        decisive = tuple(r for r in reasons if r.kind == "incompatible")
        return _result("incompatible", False, False, decisive)
    if "unknown" in kinds:
        missing = tuple(r for r in reasons if r.kind == "unknown")
        return _result("unknown", False, False, missing)
    if reasons:
        scores = "partial_text" not in kinds
        return _result("partially_comparable", scores, True, tuple(reasons))
    return _result("comparable", True, True, ())


_LEAD: dict[str, str] = {
    "comparable": "Comparable: the same question and version, rubric, evaluator and conditions",
    "partially_comparable": "Partly comparable",
    "incompatible": "Not comparable",
    "unknown": "Can't tell whether these compare",
}


def _result(outcome: Outcome, scores: bool, points: bool, reasons: tuple[Reason, ...]) -> Classification:
    body = "; ".join(r.text for r in reasons)
    text = f"{_LEAD[outcome]}: {body}" if body else _LEAD[outcome]
    if outcome == "partially_comparable" and scores:
        text += ". The scores are on the same rubric, so both are shown"
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
