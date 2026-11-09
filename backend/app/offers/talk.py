"""The authored counterpart and the debrief for offer rehearsals (docs/OFFER_REHEARSAL.md).

Both are fixed rules, not AI, and read the same normalised text whether the learner typed or
dictated (lowercase, apostrophes and filler sounds out, the same filler pattern the interview
rubric uses), so feedback doesn't depend on how an answer was entered.

The counterpart only ever states what the card states. An unknown term gets "I'll check", never a
guess; a request gets an authored reply that agrees to nothing; the last phase brings the card's
own counteroffer. The debrief separates the card's facts, the learner's goals, the counterpart's
authored replies and qualitative coaching, and only does arithmetic on amounts the card states, in
their own units (no tax, no annualising hours the card doesn't state, no legal conclusions).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.careers.grading import _FILLER
from app.offers import PHASE_TITLES, UNKNOWN_REPLY, OfferCase, Phase, Term, from_snapshot

Intent = Literal["accept", "decline", "time", "counter", "unclear"]
RULES_VERSION = 1
MODE = "Authored responses (no AI)"
METHOD = (
    "Fixed rules, not AI, the same for typed and spoken answers: where you asked about terms, whether your "
    "request names what you want and why, whether what you said matches the card, and how clearly you "
    "answered the counteroffer. Tone, accent and personality aren't judged."
)
DISCLAIMER = (
    "The counterpart is a script. A favourable reply here isn't evidence that a real employer would agree, or "
    "what they'd think of you. Nothing was sent to anyone, and no real offer or application changed."
)
NO_TAX = "Amounts are before tax and in the card's own units. This rehearsal doesn't work out tax or say what anyone is entitled to."

_APOSTROPHE = re.compile(r"['’]")
_NUMBER = re.compile(r"([£$€])?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?(k\b|thousand\b|grand\b)?")
_QUESTION_START = re.compile(
    r"(?:^|[.!?]\s+)(?:what|when|how|which|who|is|are|does|do|can|could|would|will|whats)\b"
)
_REQUEST_WORDS = (
    "could",
    "would",
    "like",
    "ask",
    "asking",
    "can i",
    "can we",
    "possible",
    "hoping",
    "looking for",
    "request",
)
_REASON_WORDS = ("because", "since", "given", "as i", "so that", "based on", "reason", "due to")
_RESPECT_WORDS = ("thank", "appreciate", "understand", "grateful", "sounds", "fair", "glad")
_UNSUPPORTED = (
    "another offer",
    "other offer",
    "competing offer",
    "counter offer from",
    "market rate",
    "industry standard",
    "everyone gets",
    "everyone else",
    "my friend earns",
    "going rate",
    "legally entitled",
    "by law",
)
_PRESSURE = (
    "or i walk",
    "or ill walk",
    "take it or leave it",
    "final offer",
    "ultimatum",
    "or i leave",
    "or im out",
    "non negotiable",
    "unless you",
)
_DECLINE = (
    "decline",
    "turn it down",
    "turn down",
    "not going to accept",
    "wont be accepting",
    "cant accept",
    "cannot accept",
    "have to say no",
    "no thank you",
    "pass on",
    "not for me",
)
_TIME = (
    "time to think",
    "think about it",
    "think it over",
    "get back to you",
    "come back to you",
    "sleep on it",
    "a few days",
    "need some time",
    "take some time",
    "a day or two",
)
_WHEN = re.compile(
    r"\b(?:by|until|on)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|the end of|end of|next)\b|\btomorrow\b|\bend of (?:the )?(?:day|week)\b|\b\d+\s+(?:days?|hours?)\b|\bthis week\b"
)
_ACCEPT = (
    "i accept",
    "accept the",
    "happy to go ahead",
    "that works",
    "sounds good",
    "i agree",
    "deal",
    "yes please",
    "happy to accept",
    "pleased to accept",
)
_COUNTER = (
    "could you",
    "would you consider",
    "is there any",
    "can you do",
    "could we",
    "would it be possible",
    "meet me",
)
_SYMBOL = {"GBP": "£", "USD": "$", "EUR": "€"}


def normal(text: str) -> str:
    t = _FILLER.sub(" ", text)
    t = _APOSTROPHE.sub("", t).lower()
    return " ".join(t.split())


def _has(text: str, phrases: tuple[str, ...]) -> list[str]:
    return [p for p in phrases if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text)]


def terms_in(case: OfferCase, text: str) -> list[Term]:
    return [t for t in case.terms if _has(text, t.aliases)]


def numbers(text: str) -> list[float]:
    out = []
    for m in _NUMBER.finditer(text):
        value = float(m.group(2).replace(",", ""))
        if m.group(3):
            value *= 1000
        out.append(value)
    return out


def amount_for(term: Term, text: str) -> float | None:
    """A number in the message that's plausibly about this term (half to three times the card's
    amount), so "25 days" isn't read as a salary."""
    if term.amount is None:
        return None
    for n in numbers(text):
        if 0.5 * term.amount <= n <= 3 * term.amount:
            return n
    return None


_MONEY_HINT = re.compile(
    r"[£$€]|\d\s?(?:k|thousand|grand)\b|\b(?:pounds?|dollars?|euros?|quid|bucks)\b|\bper (?:hour|year)\b|\ban hour\b|\ba year\b"
)


def target(case: OfferCase, text: str) -> tuple[Term | None, float | None]:
    """What a request is about: a named term with a plausible amount; else, when the message talks
    money, the pay term whose amount it plausibly is; else the first term named."""
    named = terms_in(case, text)
    for t in named:
        amount = amount_for(t, text)
        if amount is not None:
            return t, amount
    if _MONEY_HINT.search(text):
        for t in case.terms:
            amount = amount_for(t, text)
            if amount is not None and t.unit and t.unit.startswith("per"):
                return t, amount
    return (named[0], None) if named else (None, None)


def is_question(raw: str, text: str) -> bool:
    return "?" in raw or bool(_QUESTION_START.search(text))


def intent(text: str, case: OfferCase) -> Intent:
    if _has(text, _DECLINE):
        return "decline"
    if _has(text, _TIME):
        return "time"
    target = case.term(case.counter.term)
    if (target is not None and amount_for(target, text) not in (None, case.counter.amount)) or _has(
        text, _COUNTER
    ):
        return "counter"
    if _has(text, _ACCEPT):
        return "accept"
    return "unclear"


def money(case: OfferCase, amount: float, unit: str | None = None) -> str:
    symbol = _SYMBOL.get(case.currency or "", "")
    number = f"{amount:,.2f}" if amount != int(amount) else f"{int(amount):,}"
    return f"{symbol}{number}{f' {unit}' if unit else ''}"


@dataclass(frozen=True)
class Reply:
    text: str
    concluded: bool = False  # the learner gave a definite answer to the counteroffer


def opener(case: OfferCase, phase: Phase) -> str:
    if phase == "clarify":
        return case.opener
    if phase == "request":
        return "Thanks for those questions. What would you like to discuss about the offer?"
    return case.counter.text


def reply(case: OfferCase, phase: Phase, raw: str) -> Reply:
    """The counterpart's answer to one learner turn: authored lines, the card's own values."""
    text = normal(raw)
    named = terms_in(case, text)
    calm = "I understand this matters to you. " if _has(text, _PRESSURE) else ""
    other = (
        "I can only go on what's in this offer; I can't comment on other offers or figures. "
        if _has(text, _UNSUPPORTED)
        else ""
    )
    if phase == "clarify":
        lines = []
        for t in named:
            said = amount_for(t, text)
            if t.value is None:
                lines.append(f"{t.label}: {UNKNOWN_REPLY}")
            elif said is not None and said != t.amount and not is_question(raw, text):
                lines.append(f"Just to check, the offer says {t.label.lower()} is {t.value}.")
            else:
                lines.append(f"{t.label}: {t.value}.")
        if lines:
            return Reply(calm + other + " ".join(lines))
        if is_question(raw, text):
            stated = ", ".join(t.label.lower() for t in case.terms if t.value is not None)
            return Reply(f"{calm}{other}Which part would you like me to clarify? The offer covers {stated}.")
        return Reply(f"{calm}{other}Is there anything in the offer you'd like me to clarify?")
    if phase == "request":
        about, _ = target(case, text)
        for t in ([about] if about else []) + named:
            if t.request:
                return Reply(calm + other + t.request)
        if about or named:
            return Reply(
                f"{calm}{other}I'll note that and check what's possible. I can't agree to anything today."
            )
        return Reply(f"{calm}{other}What exactly would you like to change, and why?")
    kind = intent(text, case)
    if kind == "accept":
        return Reply(
            "Thank you. With a real offer you'd want the revised terms in writing before you accept anything. "
            "That's the end of the rehearsal.",
            concluded=True,
        )
    if kind == "decline":
        return Reply("Thank you for telling me directly. I'll let the hiring manager know.", concluded=True)
    if kind == "time":
        if _WHEN.search(text):
            return Reply("That's fine. I'll note that you'll come back to me by then.", concluded=True)
        return Reply("Of course. When do you think you can let me know?")
    if kind == "counter":
        return Reply(f"{calm}{other}I can't go further on this call, but I'll pass that on.")
    return Reply("Just so I understand: would you like to accept, take some time, or ask for something else?")


def _claims(case: OfferCase, raw: str, text: str, phase: str) -> list[dict[str, str]]:
    """Statements that don't match the card: a stated amount said differently (not a request or a
    question), or a fact the card doesn't contain (another offer, a market rate, an entitlement)."""
    found = []
    if phase != "request" and not is_question(raw, text):
        for t in terms_in(case, text):
            said = amount_for(t, text)
            if (
                t.value is not None
                and said is not None
                and said != t.amount
                and not _has(text, _REQUEST_WORDS)
            ):
                found.append(
                    {
                        "kind": "mismatch",
                        "quote": raw.strip(),
                        "note": f"The card says {t.label.lower()} is {t.value}.",
                    }
                )
    for phrase in _has(text, _UNSUPPORTED):
        found.append(
            {
                "kind": "unsupported",
                "quote": raw.strip(),
                "note": f"“{phrase}” isn't on the card, so it can't be checked here.",
            }
        )
    return found


def debrief(snapshot: dict[str, Any], turns: list[dict[str, Any]], goals: list[str]) -> dict[str, Any]:
    """The debrief of one rehearsal, from its snapshot (the card as shown then) and its turns."""
    oc = from_snapshot(snapshot)
    mine = [t for t in turns if t["speaker"] == "learner"]
    by_phase = {p: [t for t in mine if t["phase"] == p] for p in PHASE_TITLES}
    known = {t.id: t for t in oc.terms}
    used: dict[str, Term] = {}
    asked: set[str] = set()
    claims: list[dict[str, str]] = []
    pressure: list[str] = []
    for t in mine:
        text = normal(t["text"])
        for term in terms_in(oc, text):
            used[term.id] = term
            if t["phase"] == "clarify":
                asked.add(term.id)
        claims += _claims(oc, t["text"], text, t["phase"])
        pressure += _has(text, _PRESSURE)

    request = None
    for t in by_phase["request"]:
        text = normal(t["text"])
        found, amount = target(oc, text)
        if found is None:
            continue
        term = found
        sums = None
        if amount is not None and term.amount is not None:
            diff = amount - term.amount
            sums = {
                "offered": money(oc, term.amount, term.unit),
                "requested": money(oc, amount, term.unit),
                "difference": f"{'+' if diff >= 0 else '-'}{money(oc, abs(diff))} ({diff / term.amount * 100:+.1f}%)",
                "per_week": (
                    f"{'+' if diff >= 0 else '-'}{money(oc, abs(diff) * oc.hours_per_week)} a week at the card's "
                    f"{oc.hours_per_week:g} hours"
                    if oc.hours_per_week and term.unit == "per hour"
                    else None
                ),
            }
        request = {
            "quote": t["text"].strip(),
            "term": term.label,
            "amount": money(oc, amount, term.unit) if amount is not None else None,
            "reasons": bool(_has(text, _REASON_WORDS)),
            "specific": amount is not None or term.amount is None or bool(_has(text, _REQUEST_WORDS)),
            "arithmetic": sums,
        }
        break

    changed = known.get(oc.counter.term)
    counter_sums = None
    if changed is not None and changed.amount is not None and oc.counter.amount is not None:
        diff = oc.counter.amount - changed.amount
        counter_sums = {
            "from": money(oc, changed.amount, changed.unit),
            "to": money(oc, oc.counter.amount, changed.unit),
            "difference": f"+{money(oc, diff)} ({diff / changed.amount * 100:+.1f}%)",
        }

    answer = by_phase["respond"][-1] if by_phase["respond"] else None
    outcome: Intent | None = intent(normal(answer["text"]), oc) if answer else None
    respectful = any(_has(normal(t["text"]), _RESPECT_WORDS) for t in by_phase["respond"])
    unknown: list[dict[str, Any]] = [
        {"label": t.label, "asked": t.id in asked} for t in oc.terms if t.value is None
    ]

    criteria: list[dict[str, Any]] = [
        {
            "id": "accurate",
            "label": "What you said matches the card",
            "met": not claims,
            "note": "Nothing you said contradicts the card or relies on facts it doesn't have."
            if not claims
            else claims[0]["note"],
        },
        {
            "id": "request",
            "label": "A clear request",
            "met": bool(request and request["specific"]),
            "note": f"You asked about {request['term'].lower()}{f' ({request["amount"]})' if request and request['amount'] else ''}."
            if request
            else "No request named a term from the offer."
            if by_phase["request"]
            else "You didn't reach the request.",
        },
        {
            "id": "reasons",
            "label": "A reason for it",
            "met": bool(request and request["reasons"]),
            "note": "Your request gives a reason."
            if request and request["reasons"]
            else "The request doesn't say why.",
        },
        {
            "id": "asked",
            "label": "Questions about what the offer leaves open",
            "met": any(u["asked"] for u in unknown),
            "note": "You asked about " + ", ".join(u["label"].lower() for u in unknown if u["asked"]) + "."
            if any(u["asked"] for u in unknown)
            else "You didn't ask about the terms the offer leaves open.",
        },
        {
            "id": "response",
            "label": "A clear answer to the counteroffer",
            "met": outcome in ("accept", "decline", "time", "counter"),
            "note": {
                "accept": "You accepted.",
                "decline": "You declined clearly. Declining is a complete answer.",
                "time": "You asked for time.",
                "counter": "You made a counter.",
                "unclear": "Your answer didn't say whether you accept, need time, decline or want something else.",
                None: "You didn't reach the counteroffer.",
            }[outcome]
            + (" You thanked them or acknowledged their position." if respectful else ""),
        },
    ]
    tips = {
        "accurate": (
            f"Stick to what the card says: {claims[0]['note']} Give a reason from your own situation instead."
            if claims
            else ""
        ),
        "request": "Say exactly what you're asking for: the term and, for pay, the number. For example: “I'd like to ask "
        "for a base of …, because …”.",
        "reasons": "Give one reason that rests on something real: your experience, what the role involves, or a term "
        "on the card.",
        "asked": "Before negotiating, ask about what the offer leaves open ("
        + ", ".join(u["label"].lower() for u in unknown)
        + "), so you know the whole package.",
        "response": "Answer the counteroffer clearly: accept, ask for time and say by when, decline, or make one specific "
        "counter. A thank-you first helps.",
    }
    first = next((c for c in criteria if not c["met"]), None)
    improvement = (
        tips[first["id"]]
        if first
        else (
            "Everything here was covered. Next time, try a different approach: ask for time, or practise declining politely."
        )
    )
    return {
        "rules_version": RULES_VERSION,
        "mode": MODE,
        "facts": [{"label": t.label, "value": t.value} for t in oc.terms],
        "goals": goals,
        "request": request,
        "counteroffer": {"text": oc.counter.text, "arithmetic": counter_sums},
        "facts_used": [{"label": t.label, "value": t.value} for t in used.values()],
        "unresolved": unknown,
        "claims": claims,
        "pressure": bool(pressure),
        "outcome": outcome,
        "criteria": criteria,
        "improvement": improvement,
        "phases_reached": [PHASE_TITLES[p] for p in PHASE_TITLES if any(t["phase"] == p for t in turns)],
        "method": METHOD,
        "disclaimer": DISCLAIMER,
        "no_tax": NO_TAX,
    }
