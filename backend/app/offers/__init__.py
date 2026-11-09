"""Offer-conversation rehearsals (Volume 10, prompt 8; docs/OFFER_REHEARSAL.md).

A fictional fact card (the role, the stated terms with their units and currency, the terms the
offer leaves unknown) and an authored counterpart: what it says when a term is asked about, when
a request is made, and the counteroffer it brings to the last phase. Everything here is made up
and labelled so; nothing is a market rate, an employer budget or a legal entitlement, and nothing
is sent to anyone. The counterpart never adds a term the card doesn't have.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Phase = Literal["clarify", "request", "respond"]
PHASES: tuple[Phase, ...] = ("clarify", "request", "respond")
PHASE_TITLES: dict[Phase, str] = {
    "clarify": "Clarify the terms",
    "request": "Make a reasoned request",
    "respond": "Respond to the counteroffer",
}


@dataclass(frozen=True)
class Term:
    id: str
    label: str
    aliases: tuple[str, ...]  # words that name it in a message (lowercase, no apostrophes)
    value: str | None  # as the card states it; None: the offer doesn't say (unknown stays unknown)
    amount: float | None = None  # a number the card states, for arithmetic in its own unit
    unit: str | None = None  # "per year", "per hour", "days"
    request: str | None = None  # the counterpart's authored reply to a request about this term


@dataclass(frozen=True)
class Counter:
    """The counteroffer the counterpart brings to the last phase (fictional)."""

    text: str
    term: str  # the term it changes
    amount: float | None  # the new amount, in the term's unit


@dataclass(frozen=True)
class OfferCase:
    id: str
    version: int
    title: str
    role: str
    employer: str
    counterpart: str  # who's on the other side (a fictional person and role)
    currency: str | None  # ISO code of every amount on the card
    hours_per_week: float | None  # stated on the card; used only to show a weekly difference
    terms: tuple[Term, ...]
    counter: Counter
    opener: str  # the counterpart's first line
    review_status: str
    _index: dict[str, Term] = field(default_factory=dict, compare=False, repr=False)

    def term(self, term_id: str) -> Term | None:
        if not self._index:
            self._index.update({t.id: t for t in self.terms})
        return self._index.get(term_id)

    def snapshot(self) -> dict[str, Any]:
        """The card as a rehearsal keeps it: a later edit doesn't change an earlier debrief."""
        data = asdict(self)
        data.pop("_index", None)
        return data


REVIEW = (
    "Fictional case, written for practice and checked for internal consistency. Its numbers are made up: "
    "they aren't market rates, an employer's budget or what anyone is entitled to."
)
UNKNOWN_REPLY = "That isn't set out in the offer you have. I don't want to guess, so I'll check and confirm it in writing."

SUPPORT_ANALYST = OfferCase(
    id="offer-support-analyst",
    version=1,
    title="A first offer for a support analyst role",
    role="IT support analyst",
    employer="Northfield Logistics (fictional)",
    counterpart="Sam, the recruiter (fictional)",
    currency="GBP",
    hours_per_week=None,
    terms=(
        Term(
            "base",
            "Base salary",
            ("salary", "base", "pay", "wage", "money", "compensation"),
            "£31,000 per year",
            31000,
            "per year",
            "I can't agree a different salary on this call. I'll take your request, and your reasons, to the "
            "hiring manager and come back to you.",
        ),
        Term("start", "Start date", ("start", "first day", "begin"), "Monday 2 March"),
        Term(
            "hybrid",
            "Working from home",
            ("from home", "remote", "hybrid", "wfh", "office"),
            "2 days a week",
            2,
            "days a week",
            "The team is in the office three days a week. I can ask whether there's any flexibility, but I "
            "can't promise it.",
        ),
        Term(
            "leave",
            "Annual leave",
            ("holiday", "leave", "vacation", "days off"),
            "25 days plus public holidays",
            25,
            "days",
        ),
        Term("probation", "Probation", ("probation", "trial period"), "6 months"),
        Term("bonus", "Bonus", ("bonus", "incentive"), None),
        Term(
            "training",
            "Training budget",
            ("training", "course", "certification", "learning budget"),
            None,
            request="I'll ask whether there's a training budget for this role. I don't know yet.",
        ),
    ),
    counter=Counter(
        "I've spoken to the hiring manager. In this fictional case they can offer a base salary of £32,500 "
        "instead of £31,000, with a salary review at the end of probation. The other terms stay as they are. "
        "Would that work for you?",
        "base",
        32500,
    ),
    opener="Thanks for making time. You've got the offer in front of you: is there anything you'd like me to "
    "clarify first?",
    review_status=REVIEW,
)

TEAM_LEAD = OfferCase(
    id="offer-warehouse-team-lead",
    version=1,
    title="An hourly offer for a warehouse team lead",
    role="Warehouse team lead",
    employer="Harbour Point Distribution (fictional)",
    counterpart="Jordan, the operations manager (fictional)",
    currency="USD",
    hours_per_week=40,
    terms=(
        Term(
            "rate",
            "Hourly rate",
            ("rate", "hourly", "per hour", "pay", "wage", "money"),
            "$21.50 per hour",
            21.5,
            "per hour",
            "I hear you. I can't change the rate today; I'll put your request and your reasons to our "
            "regional manager.",
        ),
        Term(
            "shifts",
            "Shift pattern",
            ("shift", "shifts", "schedule", "hours", "days"),
            "Four 10-hour days a week (40 hours)",
        ),
        Term("overtime", "Overtime", ("overtime", "extra hours"), "Time and a half after 40 hours a week"),
        Term("health", "Health insurance", ("health", "insurance", "medical"), "Starts after 60 days"),
        Term("start", "Start date", ("start", "first day", "begin"), "In two weeks"),
        Term("parking", "Parking", ("parking", "car park", "park"), None),
        Term(
            "uniform",
            "Uniform and boots allowance",
            ("uniform", "boots", "allowance", "safety gear"),
            None,
            request="I'll check what we provide for boots and uniform. I don't want to tell you something wrong.",
        ),
    ),
    counter=Counter(
        "I checked with the regional manager. In this fictional case we can offer $22.25 an hour after a 90-day "
        "review, starting at $21.50. Everything else stays as it is. How does that sound?",
        "rate",
        22.25,
    ),
    opener="Good to talk again. Before we go further, is anything in the offer unclear?",
    review_status=REVIEW,
)


def from_snapshot(data: dict[str, Any]) -> OfferCase:
    """The case as a rehearsal recorded it (its snapshot), so a debrief reads that version."""
    return OfferCase(
        **{
            **data,
            "terms": tuple(Term(**{**t, "aliases": tuple(t["aliases"])}) for t in data["terms"]),
            "counter": Counter(**data["counter"]),
        }
    )


CASES: tuple[OfferCase, ...] = (SUPPORT_ANALYST, TEAM_LEAD)
BY_ID: dict[str, OfferCase] = {c.id: c for c in CASES}


def check(case: OfferCase) -> list[str]:
    """Authoring checks (validate-content and the tests): a counteroffer about a stated amount,
    at least one unknown term, aliases in the normalised form messages are matched in."""
    problems: list[str] = []
    ids = [t.id for t in case.terms]
    if len(ids) != len(set(ids)):
        problems.append("term ids must be unique")
    if not any(t.value is None for t in case.terms):
        problems.append("at least one term must be unknown, so clarifying has something to find")
    target = case.term(case.counter.term)
    if target is None or target.amount is None:
        problems.append("the counteroffer must change a term with a stated amount")
    for t in case.terms:
        if t.value is None and t.amount is not None:
            problems.append(f"{t.id}: an unknown term can't have an amount")
        if any(a != a.lower() or "'" in a or "’" in a for a in t.aliases) or not t.aliases:
            problems.append(f"{t.id}: aliases must be lowercase without apostrophes")
    if case.currency is None and any(t.amount is not None and t.unit and "per" in t.unit for t in case.terms):
        problems.append("money amounts need a currency")
    return problems
