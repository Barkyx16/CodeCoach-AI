"""Offer-conversation rehearsals: fictional fact cards, rehearsals, turns and the debrief."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.interview import AnswerSource

OfferPhase = Literal["clarify", "request", "respond"]


class OfferCaseSummary(APIModel):
    id: str
    title: str
    role: str
    employer: str


class OfferTermOut(APIModel):
    id: str
    label: str
    value: str | None = Field(description="As the card states it; null: the offer doesn't say (unknown)")


class OfferPhaseOut(APIModel):
    id: OfferPhase
    title: str


class OfferCard(APIModel):
    """A fictional fact card: everything here is made up and labelled so."""

    id: str
    version: int
    title: str
    role: str
    employer: str
    counterpart: str
    currency: str | None
    terms: list[OfferTermOut]
    phases: list[OfferPhaseOut]
    review_status: str


class OfferRehearsalIn(APIModel):
    case_id: str = Field(max_length=64)
    goals: list[str] = Field(
        default_factory=list, max_length=3, description="What you want from the conversation, in your words"
    )
    parent_id: str | None = Field(
        default=None, max_length=36, description="A different approach to this rehearsal"
    )


class OfferTurnIn(APIModel):
    text: str = Field(max_length=2000)
    source: AnswerSource = "typed"
    after_seq: int = Field(ge=0, description="The last turn you saw; a newer one means another tab moved on")
    client_request_id: str | None = Field(default=None, max_length=64)


class OfferPhaseIn(APIModel):
    from_phase: OfferPhase


class OfferTurnOut(APIModel):
    seq: int
    speaker: Literal["learner", "counterpart"]
    phase: OfferPhase
    text: str
    source: AnswerSource | None = None
    at: datetime


class OfferRehearsalOut(APIModel):
    id: str
    case_id: str
    case_version: int
    current_version: int | None = Field(
        description="The card's version now; differs when it was edited since"
    )
    card: OfferCard = Field(description="The card as it was when this rehearsal started")
    goals: list[str]
    status: Literal["in_progress", "completed"]
    phase: OfferPhase
    turns: list[OfferTurnOut]
    turns_left_in_phase: int
    parent_id: str | None
    mode: str = Field(description="Which counterpart ran: authored responses, never AI here")
    debrief: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class OfferRehearsalSummary(APIModel):
    id: str
    case_id: str
    title: str
    status: Literal["in_progress", "completed"]
    outcome: str | None
    parent_id: str | None
    created_at: datetime
    completed_at: datetime | None
