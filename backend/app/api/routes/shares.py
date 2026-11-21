"""Sharing an answer for feedback: the owner's controls and the reviewer's (link holder's) side."""

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_user
from app.errors import RateLimitedError
from app.models import User
from app.schemas.common import error_responses
from app.schemas.shares import (
    FeedbackIn,
    FeedbackReceipt,
    RecipientView,
    ShareCreate,
    ShareCreated,
    ShareDetail,
    SharePreview,
    ShareSelection,
    ShareSummary,
    TokenIn,
    UsefulIn,
)
from app.services.rate_limit import client_key
from app.services.shares import Shares

me_router = APIRouter(prefix="/api/v1/me/shares", tags=["sharing"])
public_router = APIRouter(prefix="/api/v1/shared", tags=["sharing"])


def private_response(response: Response) -> None:
    """Shared content and share settings must never be cached, indexed or leak a Referer."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"


def _throttle(request: Request, limiter_name: str, key: str, message: str) -> None:
    allowed, retry_after = getattr(request.app.state, limiter_name).hit(key)
    if not allowed:
        raise RateLimitedError.wait(message, retry_after)


def _ip(request: Request) -> str:
    return client_key(request)


# ---------------------------------------------------------------------------- owner


@me_router.post(
    "/preview",
    response_model=SharePreview,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="See exactly what a reviewer would see, without creating a link",
    dependencies=[Depends(private_response)],
)
def preview(
    body: ShareSelection, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SharePreview:
    return Shares(db).preview(user, body)


@me_router.post(
    "",
    response_model=ShareCreated,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 409, 422, 429),
    summary="Create an unlisted link to a snapshot of your selection (the link is returned once)",
    dependencies=[Depends(private_response)],
)
def create(
    body: ShareCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareCreated:
    _throttle(
        request,
        "share_create_limiter",
        f"share-create:{user.id}",
        "You've created a lot of links. Try again later.",
    )
    return Shares(db).create(user, body)


@me_router.get(
    "",
    response_model=list[ShareSummary],
    responses=error_responses(401, 422),
    summary="Your shared answers, newest first",
    dependencies=[Depends(private_response)],
)
def mine(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    answer_id: str | None = Query(default=None, max_length=36, description="Only shares of this answer"),
) -> list[ShareSummary]:
    service = Shares(db)
    return service.for_answer(user, answer_id) if answer_id else service.mine(user)


@me_router.get(
    "/{share_id}",
    response_model=ShareDetail,
    responses=error_responses(401, 404),
    summary="One share: the snapshot and the feedback received",
    dependencies=[Depends(private_response)],
)
def detail(
    share_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareDetail:
    return Shares(db).detail(user, share_id)


@me_router.post(
    "/{share_id}/close",
    response_model=ShareDetail,
    responses=error_responses(401, 404),
    summary="Stop taking feedback (the link still shows the snapshot)",
    dependencies=[Depends(private_response)],
)
def close(
    share_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareDetail:
    return Shares(db).close(user, share_id)


@me_router.post(
    "/{share_id}/reopen",
    response_model=ShareDetail,
    responses=error_responses(401, 404, 409),
    summary="Take feedback again on a closed share",
    dependencies=[Depends(private_response)],
)
def reopen(
    share_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareDetail:
    return Shares(db).reopen(user, share_id)


@me_router.post(
    "/{share_id}/revoke",
    response_model=ShareDetail,
    responses=error_responses(401, 404),
    summary="Turn the link off for good (you keep the snapshot and feedback until you delete them)",
    dependencies=[Depends(private_response)],
)
def revoke(
    share_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareDetail:
    return Shares(db).revoke(user, share_id)


@me_router.post(
    "/{share_id}/link",
    response_model=ShareCreated,
    responses=error_responses(401, 404, 409, 429),
    summary="Replace the link (the old one stops working); the new link is returned once",
    dependencies=[Depends(private_response)],
)
def new_link(
    share_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareCreated:
    _throttle(
        request,
        "share_create_limiter",
        f"share-create:{user.id}",
        "You've created a lot of links. Try again later.",
    )
    return Shares(db).rotate(user, share_id)


@me_router.delete(
    "/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404),
    summary="Delete the share, its snapshot and all feedback on it",
)
def delete(share_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    Shares(db).delete(user, share_id)


@me_router.put(
    "/{share_id}/feedback/{feedback_id}/useful",
    response_model=ShareDetail,
    responses=error_responses(401, 404, 422),
    summary="Mark a reviewer's feedback as useful (or not)",
    dependencies=[Depends(private_response)],
)
def useful(
    share_id: str,
    feedback_id: str,
    body: UsefulIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareDetail:
    return Shares(db).set_useful(user, share_id, feedback_id, body.useful)


@me_router.delete(
    "/{share_id}/feedback/{feedback_id}",
    response_model=ShareDetail,
    responses=error_responses(401, 404),
    summary="Delete one piece of feedback (e.g. abusive or unwanted)",
    dependencies=[Depends(private_response)],
)
def delete_feedback(
    share_id: str, feedback_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareDetail:
    return Shares(db).delete_feedback(user, share_id, feedback_id)


# ---------------------------------------------------------------------------- link holders


@public_router.post(
    "/open",
    response_model=RecipientView,
    responses=error_responses(404, 410, 422, 429),
    summary="Open a shared snapshot with its link secret (sent in the body, never the URL)",
    dependencies=[Depends(private_response)],
)
def open_shared(
    body: TokenIn,
    request: Request,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> RecipientView:
    _throttle(
        request, "share_open_limiter", f"share-open:{_ip(request)}", "Too many requests. Wait a few minutes."
    )
    return Shares(db).open(body.token, viewer)


@public_router.post(
    "/feedback",
    response_model=FeedbackReceipt,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 404, 409, 410, 422, 429),
    summary="Leave structured feedback on a shared snapshot (retries with the same request id are ignored)",
    dependencies=[Depends(private_response)],
)
def leave_feedback(
    body: FeedbackIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> FeedbackReceipt:
    _throttle(
        request,
        "share_feedback_limiter",
        f"share-feedback:{_ip(request)}",
        "Too much feedback from here. Try again later.",
    )
    receipt = Shares(db).submit(body, viewer)
    if receipt.duplicate:
        response.status_code = status.HTTP_200_OK
    return receipt
