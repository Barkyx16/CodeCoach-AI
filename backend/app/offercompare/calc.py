"""Inspectable figures for an offer comparison (docs/OFFER_COMPARISON.md).

Every derived value carries its formula, in words and units, and the assumptions behind it; a value
that needs something not entered is `None` with the reason. Supported conversions:

- pay per year: as entered;
- per month: × the number of monthly payments a year the learner entered (12, 13, 14…);
- per week: × the weeks paid a year the learner entered;
- per hour: × the hours a week × the weeks paid a year the learner entered;
- another currency: × a rate the learner entered, with its date, for exactly that pair (or its
  inverse). Never a market rate.

Not estimated, ever: tax, take-home pay, the value of equity or benefits, the chance a conditional
bonus pays out, future raises or returns. Guaranteed pay and a conditional bonus are never added
together. Weighted ordering: each contribution is the learner's weight × their rating; unknown and
not-comparable ratings aren't counted and are listed.
"""

from __future__ import annotations

from typing import Any


def amount(value: float, currency: str | None) -> str:
    text = f"{value:,.2f}".removesuffix(".00")
    return f"{text} {currency}" if currency else f"{text} (currency not entered)"


def _figure(
    value: float | None,
    currency: str | None,
    formula: str | None,
    assumptions: list[str],
    unknown: str | None,
) -> dict[str, Any]:
    return {
        "value": round(value, 2) if value is not None else None,
        "currency": currency,
        "formula": formula,
        "assumptions": assumptions,
        "unknown": unknown,
    }


def annual_pay(o: dict[str, Any]) -> dict[str, Any]:
    pay, period, cur = o.get("pay_amount"), o.get("pay_period"), o.get("currency")
    if pay is None:
        return _figure(None, cur, None, [], "No pay amount entered (unknown, not zero).")
    if period is None:
        return _figure(None, cur, None, [], "Pay period not entered, so it can't be put on a yearly basis.")
    if cur is None:
        return _figure(None, None, None, [], "Currency not entered, so the pay can't be compared.")
    if period == "year":
        return _figure(pay, cur, f"{amount(pay, cur)} a year, as entered", [], None)
    if period == "month":
        months = o.get("months_paid")
        if months is None:
            return _figure(
                None,
                cur,
                None,
                [],
                "Enter how many monthly payments a year (often 12; some contracts pay 13 or 14).",
            )
        v = pay * months
        return _figure(
            v,
            cur,
            f"{amount(pay, cur)} a month × {months:g} payments a year = {amount(v, cur)} a year",
            [f"{months:g} monthly payments a year (you entered this)"],
            None,
        )
    weeks = o.get("weeks_per_year")
    if period == "week":
        if weeks is None:
            return _figure(
                None, cur, None, [], "Enter the weeks paid a year to put weekly pay on a yearly basis."
            )
        v = pay * weeks
        return _figure(
            v,
            cur,
            f"{amount(pay, cur)} a week × {weeks:g} weeks = {amount(v, cur)} a year",
            [f"{weeks:g} paid weeks a year (you entered this)"],
            None,
        )
    hours = o.get("hours_per_week")
    missing = [name for name, x in (("hours a week", hours), ("weeks paid a year", weeks)) if x is None]
    if missing:
        return _figure(
            None, cur, None, [], f"Enter the {' and the '.join(missing)} to put hourly pay on a yearly basis."
        )
    assert hours is not None and weeks is not None
    v = pay * hours * weeks
    return _figure(
        v,
        cur,
        f"{amount(pay, cur)} an hour × {hours:g} hours a week × {weeks:g} weeks = {amount(v, cur)} a year",
        [f"{hours:g} hours a week and {weeks:g} paid weeks a year (you entered these); no overtime"],
        None,
    )


def _rate(conversions: list[dict[str, Any]], frm: str, to: str) -> tuple[float, str] | None:
    for c in conversions:
        if c["from_currency"] == frm and c["to_currency"] == to:
            return c["rate"], f"1 {frm} = {c['rate']:g} {to} (your rate for {c['as_of']})"
    for c in conversions:
        if c["from_currency"] == to and c["to_currency"] == frm:
            return 1 / c[
                "rate"
            ], f"1 {to} = {c['rate']:g} {frm} (your rate for {c['as_of']}), used the other way"
    return None


def convert(
    fig: dict[str, Any], show_in: str | None, conversions: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """The same figure in `show_in`, only with a rate the learner entered; None when not asked."""
    if not show_in or fig["value"] is None or fig["currency"] in (None, show_in):
        return None
    found = _rate(conversions, fig["currency"], show_in)
    if found is None:
        return _figure(
            None,
            show_in,
            None,
            [],
            f"No rate from {fig['currency']} to {show_in} entered, so it isn't converted.",
        )
    rate, why = found
    v = fig["value"] * rate
    return _figure(
        v,
        show_in,
        f"{amount(fig['value'], fig['currency'])} × {rate:.6g} = {amount(v, show_in)}",
        [why],
        None,
    )


def derive(doc: dict[str, Any]) -> dict[str, Any]:
    conversions = doc.get("conversions") or []
    show_in = doc.get("show_in")
    offers = []
    for o in doc.get("offers") or []:
        cur = o.get("currency")
        pay = annual_pay(o)
        extra = o.get("guaranteed_extra")
        if pay["value"] is None:
            first = _figure(
                None, cur, None, [], "Yearly pay is unknown, so guaranteed first-year cash is too."
            )
        elif extra is None:
            first = _figure(
                None,
                cur,
                None,
                [],
                "Guaranteed one-off cash (like a signing bonus) not entered: unknown, not zero. Enter 0 if there is none.",
            )
        else:
            v = pay["value"] + extra
            first = _figure(
                v,
                cur,
                f"{amount(pay['value'], cur)} yearly pay + {amount(extra, cur)} guaranteed one-off = {amount(v, cur)}",
                pay["assumptions"],
                None,
            )
        bonus = o.get("bonus_amount")
        offers.append(
            {
                "id": o["id"],
                "annual_pay": pay,
                "annual_pay_converted": convert(pay, show_in, conversions),
                "guaranteed_first_year": first,
                "guaranteed_first_year_converted": convert(first, show_in, conversions),
                "conditional_bonus": {
                    "value": bonus,
                    "currency": cur,
                    "text": (
                        f"Up to {amount(bonus, cur)}, conditional: not counted in guaranteed pay"
                        if bonus is not None
                        else "Not entered (unknown, not zero)"
                    ),
                },
                "equity": (
                    "Described, not valued: its worth depends on things this workspace can't know."
                    if (o.get("equity_note") or "").strip()
                    else "Not entered"
                ),
            }
        )
    currencies = sorted({o.get("currency") for o in doc.get("offers") or [] if o.get("currency")})
    return {
        "offers": offers,
        "mixed_currencies": len(currencies) > 1,
        "currency_note": (
            f"These offers are in {', '.join(currencies)}. They're shown in their own currencies"
            + (
                f", and in {show_in} only where you entered a dated rate."
                if show_in
                else "; add a dated rate to see one currency."
            )
            if len(currencies) > 1
            else None
        ),
        "weighted": _weighted(doc) if doc.get("weights_on") else None,
        "not_estimated": "Tax, take-home pay, the value of equity or benefits, whether a bonus pays out, and future raises aren't estimated.",
    }


def _weighted(doc: dict[str, Any]) -> dict[str, Any]:
    offers = doc.get("offers") or []
    labels = {o["id"]: o["label"] for o in offers}
    rows = []
    for o in offers:
        contributions, not_counted = [], []
        for f in doc.get("factors") or []:
            weight = f.get("weight")
            r = (f.get("ratings") or {}).get(o["id"]) or {"state": "unknown", "value": None}
            if not weight:
                not_counted.append({"factor": f["label"], "reason": "no weight (or weight 0)"})
            elif r["state"] == "not_comparable":
                not_counted.append({"factor": f["label"], "reason": "not comparable"})
            elif r["state"] != "rated" or r.get("value") is None:
                not_counted.append({"factor": f["label"], "reason": "unknown"})
            else:
                contributions.append(
                    {
                        "factor": f["label"],
                        "weight": weight,
                        "rating": r["value"],
                        "points": weight * r["value"],
                        "formula": f"weight {weight} × your rating {r['value']} = {weight * r['value']}",
                    }
                )
        rows.append(
            {
                "id": o["id"],
                "label": labels[o["id"]],
                "total": sum(c["points"] for c in contributions),
                "counted": len(contributions),
                "contributions": contributions,
                "not_counted": not_counted,
            }
        )
    order = sorted(rows, key=lambda r: -r["total"])
    uneven = len({r["counted"] for r in rows}) > 1
    return {
        "rows": rows,
        "order": [r["id"] for r in order],
        "explanation": "Each point is your weight × your rating (1 to 5). Unknown and not-comparable ratings aren't "
        "counted, and pay isn't part of it unless you add it as a factor and rate it yourself.",
        "uneven": (
            "The offers have different numbers of rated factors, so the totals aren't like for like."
            if uneven
            else None
        ),
        "label": "Your weighted ordering: it reflects only your weights and ratings, not a recommendation or an "
        "objectively best offer.",
    }
