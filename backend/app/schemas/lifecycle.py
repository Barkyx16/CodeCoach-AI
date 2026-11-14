"""What an archive or a delete will do, worked out before it's done (docs/LIFECYCLE.md)."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, OptionalKey

EffectKind = Literal["archived", "deleted", "unlinked", "kept", "unavailable"]
LifecycleAction = Literal["delete_application", "archive_note"]


class Effect(APIModel):
    effect: EffectKind = Field(
        description="archived (reversible), deleted, unlinked (the other record stays), kept, or made unavailable"
    )
    kind: str = Field(description="What it is, in the words the app uses: an event, a kit, a schedule entry…")
    title: str
    id: str | None = Field(
        default=None, description="The record's id (yours); part of what the fingerprint covers"
    )
    note: str | None = Field(default=None, description="One line on what this means, when it isn't obvious")


class Impact(APIModel):
    action: LifecycleAction
    target_id: str
    title: str
    summary: str = Field(
        description='The action and its reach in words: "Delete this application, its 3 events and 1 kit"'
    )
    effects: list[Effect] = Field(description="Every one of your records it touches, by title and kind")
    notes: list[str] = Field(
        default_factory=list, description="What it can't do, e.g. recall a delivered email"
    )
    fingerprint: str = Field(description="Send it back to carry out exactly this; a changed scope is refused")


class LifecycleIn(APIModel):
    expected_fingerprint: str = Field(
        min_length=16,
        max_length=64,
        description="The preview's fingerprint. If the scope changed since, nothing is done: 409 impact_changed "
        "with the new preview (details.current).",
    )
    client_request_id: OptionalKey = None


class LifecycleOutcome(Impact):
    done_at: datetime
    replayed: bool = Field(
        default=False,
        description="True when this repeats an earlier request whose reply was lost: nothing was done again",
    )
    message: str
