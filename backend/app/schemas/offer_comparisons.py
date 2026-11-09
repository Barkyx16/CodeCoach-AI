"""A private offer comparison: terms entered by hand, the learner's own priorities, inspectable figures."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey, SaveReplay, save_replay_field, update_key_field

PayPeriod = Literal["year", "month", "week", "hour"]
_ID = r"^[a-z0-9-]{1,16}$"
_CURRENCY = r"^[A-Z]{3}$"
_MONEY = 100_000_000


class OfferTerms(APIModel):
    """One offer, as the learner enters it. Every field can be left unknown; unknown isn't zero."""

    id: str = Field(pattern=_ID)
    label: str = Field(min_length=1, max_length=80)
    application_id: str | None = Field(
        default=None, max_length=36, description="One of your applications, if linked"
    )
    source_note: str = Field(default="", max_length=300, description="Where these terms came from")
    terms_as_of: date | None = Field(default=None, description="The date of the terms entered")
    currency: str | None = Field(default=None, pattern=_CURRENCY)
    pay_amount: float | None = Field(default=None, ge=0, le=_MONEY)
    pay_period: PayPeriod | None = None
    months_paid: float | None = Field(default=None, gt=0, le=14, description="Monthly pay: payments a year")
    hours_per_week: float | None = Field(default=None, gt=0, le=100)
    weeks_per_year: float | None = Field(
        default=None, gt=0, le=53, description="Weekly or hourly pay: weeks paid a year"
    )
    guaranteed_extra: float | None = Field(
        default=None, ge=0, le=_MONEY, description="Guaranteed one-off cash; 0 if none"
    )
    guaranteed_note: str = Field(default="", max_length=200)
    bonus_amount: float | None = Field(
        default=None, ge=0, le=_MONEY, description="Conditional bonus, never guaranteed"
    )
    bonus_note: str = Field(default="", max_length=200)
    equity_note: str = Field(default="", max_length=300, description="Described only; never valued")
    benefits_note: str = Field(default="", max_length=300)


class Rating(APIModel):
    state: Literal["rated", "unknown", "not_comparable"] = "unknown"
    value: int | None = Field(default=None, ge=1, le=5, description="Your rating, 1 to 5, when rated")
    note: str = Field(default="", max_length=200)


class Factor(APIModel):
    id: str = Field(pattern=_ID)
    label: str = Field(min_length=1, max_length=60)
    weight: int | None = Field(
        default=None, ge=0, le=5, description="Optional; used only when weights are on"
    )
    ratings: dict[str, Rating] = Field(default_factory=dict, description="By offer id")


class Conversion(APIModel):
    from_currency: str = Field(pattern=_CURRENCY)
    to_currency: str = Field(pattern=_CURRENCY)
    rate: float = Field(gt=0, le=1_000_000)
    as_of: date
    note: str = Field(default="", max_length=200)


class ComparisonDoc(APIModel):
    title: str = Field(min_length=1, max_length=80)
    offers: list[OfferTerms] = Field(default_factory=list, max_length=3)
    factors: list[Factor] = Field(default_factory=list, max_length=12)
    conversions: list[Conversion] = Field(default_factory=list, max_length=6)
    weights_on: bool = False
    show_in: str | None = Field(
        default=None, pattern=_CURRENCY, description="Show converted figures in this currency"
    )


class OfferComparisonCreate(APIModel):
    title: str = Field(default="My offers", min_length=1, max_length=80)
    example: bool = Field(default=False, description="Start from a fictional example with gaps")


class OfferComparisonSave(APIModel):
    doc: ComparisonDoc
    expected_revision: int = Field(ge=1)
    client_request_id: OptionalKey = update_key_field()


class OfferComparisonOut(APIModel):
    save_replay: SaveReplay | None = save_replay_field()
    id: str
    revision: int
    doc: ComparisonDoc
    derived: dict[str, Any] = Field(
        description="Figures with formulas and assumptions; see docs/OFFER_COMPARISON.md"
    )
    applications: dict[str, str] = Field(
        description="Linked application ids → 'role at employer' (yours only)"
    )
    created_at: datetime
    updated_at: datetime


class OfferComparisonSummary(APIModel):
    id: str
    title: str
    offers: int
    updated_at: datetime


class DerivedOut(APIModel):
    derived: dict[str, Any]
