"""Your practice packet: chosen material assembled for an exact preview (docs/PACKET.md)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.errors import RateLimitedError
from app.models import User
from app.schemas.common import error_responses
from app.schemas.packet import PacketIn, PacketKitChoice, PacketOut, PacketReflectionList
from app.services.packet import Packets

router = APIRouter(tags=["packet"])


@router.post(
    "/api/v1/me/packet/preview",
    response_model=PacketOut,
    responses=error_responses(401, 422, 429),
    summary="Assemble the questions, notes, stories, accepted improvements and kit you chose, in your order, "
    "for a preview "
    "(nothing is stored, sent or shared; the file is made on your device from this preview)",
)
def preview_packet(
    body: PacketIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PacketOut:
    allowed, retry_after = request.app.state.packet_limiter.hit(f"packet:{user.id}")
    if not allowed:
        raise RateLimitedError.wait(
            "That's a lot of packets in a minute. Try again in a moment.", retry_after
        )
    return Packets(db, user).preview(body)


@router.get(
    "/api/v1/me/packet/kits",
    response_model=list[PacketKitChoice],
    responses=error_responses(401),
    summary="Your saved interview-day kits you can put in a packet (one per packet), the most recent first",
)
def packet_kits(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PacketKitChoice]:
    return Packets(db, user).kits()


@router.get(
    "/api/v1/me/packet/reflections",
    response_model=PacketReflectionList,
    responses=error_responses(401),
    summary="Your real-interview reflections you can put in a packet, the most recent interview first, with only "
    "whether each has private details",
)
def packet_reflections(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PacketReflectionList:
    return Packets(db, user).reflections()
