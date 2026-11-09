"""Comparing a learner's review with the authored one (docs/CODE_REVIEW_PRACTICE.md).

Fixed rules, not a model. What they look at, for each of the learner's findings:
- where it points: the lines it cites overlap an authored defect, an authored observation, or
  neither; a finding citing more than BROAD lines isn't matched at all (citing the whole file would
  otherwise line up with everything). Matching is by location, never by wording, so any phrasing of the same point lines up,
  and nothing is marked wrong for not using the reference's words;
- whether it says what happens because of the problem (a consequence), and whether it proposes a
  next step (a change, or a test that would show the problem).

What they can't do: tell whether the explanation is right. A finding at the right lines with a
wrong explanation still "lines up", and the page says the check compares locations only, with the
two explanations side by side. There is no score, and more findings never count for more: findings
the authored review doesn't support are named as unsupported, and several of them get a note that
a short review with evidence helps more than a long list.

The rules read the attempt's snapshot, so an old attempt is explained against the version it saw.
"""

from __future__ import annotations

import re
from typing import Any

RUBRIC_VERSION = 1
CONSEQUENCE_WORDS = 3
REPAIR_WORDS = 2
LONG_LIST = 3  # unsupported findings before the "short review" note
BROAD = 6  # a finding citing more lines than this isn't matched (citing everything would match everything)

_WORD = re.compile(r"[\w']+")


def words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def _spans(ref: dict[str, Any]) -> list[tuple[int, int]]:
    return [tuple(ref["lines"])] + [tuple(s) for s in ref.get("related_lines", [])]  # type: ignore[misc]


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def _where(start: int, end: int) -> str:
    return f"line {start}" if start == end else f"lines {start}–{end}"


def evaluate(snapshot: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    reference: list[dict[str, Any]] = snapshot["reference"]
    defects = [r for r in reference if r["kind"] == "defect"]
    raised_by: dict[str, list[str]] = {r["id"]: [] for r in reference}
    out: list[dict[str, Any]] = []
    for f in findings:
        span = (int(f["start_line"]), int(f["end_line"]))
        broad = span[1] - span[0] + 1 > BROAD
        matches = [] if broad else [r for r in reference if any(_overlaps(span, s) for s in _spans(r))]
        for r in matches:
            raised_by[r["id"]].append(f["id"])
        hit_defects = [r for r in matches if r["kind"] == "defect"]
        hit_observations = [r for r in matches if r["kind"] == "observation"]
        notes: list[str] = []
        if broad:
            location = "broad"
            notes.append(
                f"Cites {span[1] - span[0] + 1} lines. Narrow it to where the problem is ({BROAD} lines at most) "
                "so it can be compared."
            )
        elif hit_defects:
            location = "defect"
            titles = ", ".join(f"“{r['title']}”" for r in hit_defects)
            notes.append(
                f"Points at the same code as the authored defect {titles}. The check compares where findings "
                "point, not their wording: read the two explanations side by side."
            )
        elif hit_observations:
            location = "observation"
            titles = ", ".join(f"“{r['title']}”" for r in hit_observations)
            notes.append(
                f"Points at the same code as the authored observation {titles}, which the reference treats as "
                "a preference, not a defect. If you called it a bug, check the reasoning in the reference."
            )
        else:
            location = "unsupported"
            notes.append(
                f"No authored finding covers {_where(*span)}. That doesn't make it wrong, but nothing here "
                "supports it yet: an input that makes the code give a wrong answer would."
            )
        has_consequence = words(f.get("consequence", "")) >= CONSEQUENCE_WORDS
        has_repair = words(f.get("repair", "")) >= REPAIR_WORDS
        notes.append(
            "Says what happens because of it."
            if has_consequence
            else "Add what happens because of it: which input goes wrong, and how."
        )
        notes.append(
            "Suggests a next step."
            if has_repair
            else "Add a next step: a change, or a test that would show the problem."
        )
        out.append(
            {
                "id": f["id"],
                "location": location,
                "matches": [r["id"] for r in matches],
                "consequence": has_consequence,
                "repair": has_repair,
                "notes": notes,
            }
        )
    unsupported = sum(1 for f in out if f["location"] == "unsupported")
    found = sum(1 for r in defects if raised_by[r["id"]])
    lines: list[str] = []
    if not defects:
        lines.append(
            "The authored review found no defect in this code: it passes every test of the problem. "
            "Its notes are preferences."
        )
        if not findings:
            lines.append("You raised nothing, and the authored review agrees there's no defect to raise.")
        elif any(f["location"] != "observation" for f in out):
            lines.append(
                "Check any finding you called a bug against the tests before sending it to the author."
            )
    else:
        n = len(defects)
        if n == 1:
            lines.append(
                "The authored review has one defect, shown by a public test. "
                + ("Your review points at it." if found else "Your review doesn't point at it.")
            )
        else:
            lines.append(
                f"The authored review has {n} defects, each shown by a public test. Your review points at {found} of them."
            )
        if not findings:
            lines.append("You didn't raise a finding; the authored review is below.")
    if unsupported >= LONG_LIST:
        lines.append(
            "Several of your findings aren't covered by the authored review. A short review where each point "
            "has evidence helps an author more than a long list."
        )
    return {
        "rubric_version": RUBRIC_VERSION,
        "findings": out,
        "reference": [{"id": r["id"], "raised_by": raised_by[r["id"]]} for r in reference],
        "defects_total": len(defects),
        "defects_raised": found,
        "unsupported": unsupported,
        "summary": lines,
        "method": "Fixed rules, not AI: where each finding points, and whether it says what happens and what to "
        "change. They can't judge whether an explanation is right; compare it with the reference.",
    }
