"""Reviewed follow-up problems (Volume 14, prompt 10; docs/FOLLOW_UPS.md, "Coding problems")."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models import SubmissionStatus
from app.schemas.common import APIModel


class ProblemFollowUpOffer(APIModel):
    slug: str
    title: str
    difficulty: str
    shares: str = Field(description="The idea the two problems share (reviewed content)")
    difference: str = Field(description="How this one differs")
    exposure: str = Field(description='"Not previously attempted in this app": only then is it offered')
    from_submission_id: str = Field(description="Your passed submission it would follow up")


class ProblemFollowUpDone(APIModel):
    """A follow-up you submitted, with its own verdict: never combined with the first problem's."""

    submission_id: str
    slug: str
    title: str
    status: SubmissionStatus
    passed_count: int | None
    total_count: int | None
    created_at: datetime
    follows_up_submission_id: str


class ProblemFollowUpsOut(APIModel):
    status: Literal["none", "not_yet", "offered", "done"] = Field(
        description="none: no reviewed related problem; not_yet: until a judged submission of this one passes; "
        "offered; done: each was attempted or dismissed"
    )
    message: str
    offers: list[ProblemFollowUpOffer]
    answered: list[ProblemFollowUpDone] = Field(
        description="Follow-ups you submitted from this problem, each with its own verdict, not combined"
    )


class FollowUpOf(APIModel):
    """On a follow-up's own page: the different problem it followed, and that it isn't compared."""

    submission_id: str
    problem_slug: str
    problem_title: str
    status: SubmissionStatus
    text: str
