"""Reviewed follow-up problems (Volume 14, prompt 10; docs/FOLLOW_UPS.md, "Coding problems").

A small, authored list: after a judged submission of problem A passes, problem B is offered as a
fresh, different problem that shares one idea with A. Each pair names the idea they share and how B
differs, and records who reviewed it and how. The content gate (app/content/validate.py) checks
every one: both problems are in the bank with a reference solution, the pair is reviewed, and no
pair is listed twice or points a problem at itself.

Nothing is inferred from topics or generated: when no reviewed pair exists, nothing is offered.
A follow-up's verdict is its own and is never set beside the first problem's: a passed follow-up
doesn't show that anything was learned, only that this problem passed too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ProblemFollowUp:
    from_slug: str
    to_slug: str
    shares: str  # the idea A and B share
    difference: str  # how B differs, in the learner's words
    review_status: str  # who reviewed it, when and against what


_REVIEWED = (
    "Reviewed 2026-11-15 against both problems' statements, tests and reference solutions in the "
    "bank: one idea in common, a different problem."
)

PAIRS: tuple[ProblemFollowUp, ...] = (
    ProblemFollowUp(
        from_slug="two-sum",
        to_slug="two-sum-sorted",
        shares="Finding the two values that add up to a target",
        difference="The array is sorted and extra space is limited, so two pointers replace the hash map",
        review_status=_REVIEWED,
    ),
    ProblemFollowUp(
        from_slug="two-sum-sorted",
        to_slug="three-sum",
        shares="Two pointers closing in on a target over a sorted array",
        difference="Three values instead of two: fix one, then run the two pointers on the rest, skipping repeats",
        review_status=_REVIEWED,
    ),
    ProblemFollowUp(
        from_slug="contains-duplicate",
        to_slug="valid-anagram",
        shares="Remembering what you've already seen in one pass",
        difference="Count each letter instead of noting whether a value appeared",
        review_status=_REVIEWED,
    ),
    ProblemFollowUp(
        from_slug="valid-anagram",
        to_slug="group-anagrams",
        shares="A word's letter counts as its signature",
        difference="Use the signature as a map key to group many words, not to compare two",
        review_status=_REVIEWED,
    ),
    ProblemFollowUp(
        from_slug="valid-palindrome",
        to_slug="reverse-string",
        shares="Two pointers walking in from both ends of a string",
        difference="Build the reversed string instead of comparing the ends",
        review_status=_REVIEWED,
    ),
)


def follow_ups_from(slug: str) -> list[ProblemFollowUp]:
    return [p for p in PAIRS if p.from_slug == slug]


def follow_up_between(from_slug: str, to_slug: str) -> ProblemFollowUp | None:
    return next((p for p in PAIRS if p.from_slug == from_slug and p.to_slug == to_slug), None)


def problems(pairs: tuple[ProblemFollowUp, ...], exists: Callable[[str], bool]) -> list[str]:
    """What's wrong with the pair list (the content gate's check)."""
    out: list[str] = []
    seen: set[tuple[str, str]] = set()
    for p in pairs:
        where = f"problem follow-up {p.from_slug} -> {p.to_slug}"
        if (p.from_slug, p.to_slug) in seen:
            out.append(f"{where}: listed twice")
        seen.add((p.from_slug, p.to_slug))
        if p.from_slug == p.to_slug:
            out.append(f"{where}: a problem can't follow itself")
        for slug in (p.from_slug, p.to_slug):
            if not exists(slug):
                out.append(f"{where}: problem {slug!r} isn't in the bank (with a reference solution)")
        if not p.shares.strip() or not p.difference.strip():
            out.append(f"{where}: needs the idea they share and how the second differs")
        if not p.review_status.strip().startswith("Reviewed "):
            out.append(f"{where}: not reviewed")
    return out
