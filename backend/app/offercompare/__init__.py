"""A private offer comparison (Volume 10, prompt 9; docs/OFFER_COMPARISON.md).

The learner enters each offer's terms by hand; nothing is scraped, imported or inferred. Pay,
guaranteed one-off cash, conditional bonus and equity stay separate. `calc.derive` turns the
entered terms into figures that show their own formulas and assumptions: an annual figure only
when the conversion basis (payments, hours, weeks) has been entered, another currency only with a
dated rate the learner entered, and missing information stays unknown, never zero. Ratings of
nonfinancial factors are the learner's own; optional weights produce an ordering that explains
every contribution and is never called a recommendation.
"""

from __future__ import annotations

from typing import Any

EXAMPLE_TITLE = "Fictional example: two offers with gaps"


def example() -> dict[str, Any]:
    """A synthetic comparison with incomplete information, to try the workspace before entering real
    terms. Every name and number is made up."""
    return {
        "title": EXAMPLE_TITLE,
        "offers": [
            {
                "id": "a",
                "label": "Harbour Point Distribution (fictional)",
                "application_id": None,
                "source_note": "Fictional example: an hourly offer read out on a phone call.",
                "terms_as_of": "2026-11-02",
                "currency": "USD",
                "pay_amount": 21.5,
                "pay_period": "hour",
                "hours_per_week": 40,
                "weeks_per_year": None,
                "months_paid": None,
                "guaranteed_extra": None,
                "guaranteed_note": "Not mentioned yet: ask.",
                "bonus_amount": 1000,
                "bonus_note": "Quarterly safety bonus, if targets are met (conditional).",
                "equity_note": "",
                "benefits_note": "Health insurance after 60 days.",
            },
            {
                "id": "b",
                "label": "Northfield Logistics (fictional)",
                "application_id": None,
                "source_note": "Fictional example: the offer letter.",
                "terms_as_of": "2026-11-04",
                "currency": "GBP",
                "pay_amount": 31000,
                "pay_period": "year",
                "hours_per_week": 37.5,
                "weeks_per_year": None,
                "months_paid": None,
                "guaranteed_extra": 0,
                "guaranteed_note": "No signing bonus.",
                "bonus_amount": None,
                "bonus_note": "Bonus scheme not described in the letter (unknown).",
                "equity_note": "Share options mentioned, no number of shares or price given.",
                "benefits_note": "25 days' leave plus public holidays.",
            },
        ],
        "factors": [
            {
                "id": "schedule",
                "label": "Schedule",
                "weight": 3,
                "ratings": {
                    "a": {"state": "rated", "value": 4, "note": "Four long days, three off."},
                    "b": {"state": "rated", "value": 3, "note": "Office three days a week."},
                },
            },
            {
                "id": "commute",
                "label": "Commute",
                "weight": 2,
                "ratings": {
                    "a": {"state": "rated", "value": 2, "note": "About 50 minutes each way."},
                    "b": {"state": "unknown", "value": None, "note": "Haven't tried the route yet."},
                },
            },
            {
                "id": "learning",
                "label": "Learning opportunities",
                "weight": 4,
                "ratings": {
                    "a": {"state": "rated", "value": 3, "note": ""},
                    "b": {"state": "rated", "value": 4, "note": "Certification support mentioned."},
                },
            },
        ],
        "conversions": [],
        "weights_on": False,
        "show_in": None,
    }
