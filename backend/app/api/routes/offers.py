"""Offer-conversation rehearsals: a fictional fact card and an authored counterpart. Nothing is sent."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import error_responses
from app.schemas.offers import (
    OfferCard,
    OfferCaseSummary,
    OfferPhaseIn,
    OfferRehearsalIn,
    OfferRehearsalOut,
    OfferRehearsalSummary,
    OfferTurnIn,
)
from app.services.offers import Offers

router = APIRouter(tags=["offer-rehearsals"])
PUBLIC = "/api/v1/offer-rehearsals/cases"
MINE = "/api/v1/me/offer-rehearsals"


@router.get(PUBLIC, response_model=list[OfferCaseSummary], summary="Fictional offer cases to rehearse")
def cases() -> list[OfferCaseSummary]:
    return Offers.cases()


@router.get(
    PUBLIC + "/{case_id}",
    response_model=OfferCard,
    responses=error_responses(404),
    summary="A fictional fact card",
)
def case(case_id: str) -> OfferCard:
    return Offers.case(case_id)


@router.post(
    MINE,
    response_model=OfferRehearsalOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404, 409, 422),
    summary="Start (or resume) a rehearsal; with parent_id, a different approach",
)
def start(
    body: OfferRehearsalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OfferRehearsalOut:
    return Offers(db, user).start(body)


@router.get(
    MINE,
    response_model=list[OfferRehearsalSummary],
    responses=error_responses(401),
    summary="Your rehearsals",
)
def mine(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[OfferRehearsalSummary]:
    return Offers(db, user).mine()


@router.get(
    MINE + "/{rehearsal_id}",
    response_model=OfferRehearsalOut,
    responses=error_responses(401, 404),
    summary="A rehearsal",
)
def one(
    rehearsal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OfferRehearsalOut:
    return Offers(db, user).get(rehearsal_id)


@router.post(
    MINE + "/{rehearsal_id}/turns",
    response_model=OfferRehearsalOut,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Say something; the counterpart answers from the card",
)
def turn(
    rehearsal_id: str,
    body: OfferTurnIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OfferRehearsalOut:
    return Offers(db, user).turn(rehearsal_id, body)


@router.post(
    MINE + "/{rehearsal_id}/phase",
    response_model=OfferRehearsalOut,
    responses=error_responses(401, 404, 409, 422),
    summary="Move on to the next part",
)
def advance(
    rehearsal_id: str,
    body: OfferPhaseIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OfferRehearsalOut:
    return Offers(db, user).advance(rehearsal_id, body)


@router.post(
    MINE + "/{rehearsal_id}/finish",
    response_model=OfferRehearsalOut,
    responses=error_responses(401, 404),
    summary="Stop and see the debrief (at any point)",
)
def finish(
    rehearsal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OfferRehearsalOut:
    return Offers(db, user).finish(rehearsal_id)
