"""What a dispute leaves on things derived from disputed feedback (docs/DISPUTES.md)."""

from pydantic import Field

from app.schemas.common import APIModel


class DisputeNote(APIModel):
    """Something derived from feedback the learner disputed. It stays; the learner decides."""

    text: str = Field(description="e.g. 'Based on feedback you disputed on 3 November: “Gives a result”.'")
    href: str = Field(description="The answer whose feedback was disputed")
    answer_id: str
    criterion: str
