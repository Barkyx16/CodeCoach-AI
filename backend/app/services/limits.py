"""The limits forms state, served so each form says the number the server enforces (Volume 17,
prompt 7; docs/API.md, "Limits").

Each served limit is read from where the server enforces it: a module constant the service checks,
or the `max_length` of the request field that refuses past it. Each has a stable name and says what
it counts in the words the form and the server's refusal use. Nothing here changes a limit or how
the server refuses past one: the existing codes and words stay. Limits only the client enforces (a
draft's size, the retry ceiling) aren't here; they stay in the client, marked as its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from annotated_types import MaxLen
from pydantic import BaseModel

from app.schemas.applications import ApplicationFields
from app.schemas.careers import AnswerRequest
from app.schemas.content import ReportIn
from app.schemas.explore import CollectionBatchIn
from app.schemas.packet import PACKET_KITS, PacketIn
from app.schemas.roadmap import GoalsIn
from app.schemas.roles import TargetIn
from app.schemas.shares import FeedbackIn
from app.services.explore import MAX_COLLECTIONS, MAX_ITEMS
from app.services.restore import MAX_BYTES
from app.whiteboard.diagram import WhiteboardDiagram


def max_length(model: type[BaseModel], field: str) -> int:
    """The `max_length` a request field refuses past (a string's characters or a list's entries)."""
    for meta in model.model_fields[field].metadata:
        if isinstance(meta, MaxLen):
            return meta.max_length
    raise LookupError(f"{model.__name__}.{field} has no max_length")


@dataclass(frozen=True)
class Served:
    name: str
    value: int
    counts: str  # what it counts, in the words the form and the refusal use
    where: str  # where the server enforces it


def served() -> tuple[Served, ...]:
    return (
        Served("collections_per_account", MAX_COLLECTIONS, "collections", "explore.MAX_COLLECTIONS"),
        Served("items_per_collection", MAX_ITEMS, "items", "explore.MAX_ITEMS"),
        Served("items_per_batch", max_length(CollectionBatchIn, "add"), "at a time", "CollectionBatchIn"),
        Served(
            "stories_per_application",
            max_length(ApplicationFields, "story_ids"),
            "stories",
            "ApplicationFields.story_ids",
        ),
        Served(
            "target_description_chars",
            max_length(TargetIn, "description"),
            "characters",
            "TargetIn.description",
        ),
        Served("report_details_chars", max_length(ReportIn, "details"), "characters", "ReportIn.details"),
        Served("report_excerpt_chars", max_length(ReportIn, "excerpt"), "characters", "ReportIn.excerpt"),
        Served("backup_file_bytes", MAX_BYTES, "bytes", "restore.MAX_BYTES"),
        Served("packet_items", max_length(PacketIn, "items"), "items", "PacketIn.items"),
        Served("packet_kits", PACKET_KITS, "interview's kit", "packet.PACKET_KITS"),
        Served("goal_focus_areas", max_length(GoalsIn, "focus_areas"), "skills", "GoalsIn.focus_areas"),
        Served("answer_chars", max_length(AnswerRequest, "answer"), "characters", "AnswerRequest.answer"),
        Served("share_feedback_field_chars", max_length(FeedbackIn, "clear"), "characters", "FeedbackIn"),
        Served(
            "share_feedback_comments", max_length(FeedbackIn, "comments"), "comments", "FeedbackIn.comments"
        ),
        Served(
            "whiteboard_components",
            max_length(WhiteboardDiagram, "nodes"),
            "components",
            "WhiteboardDiagram.nodes",
        ),
        Served(
            "whiteboard_connections",
            max_length(WhiteboardDiagram, "edges"),
            "connections",
            "WhiteboardDiagram.edges",
        ),
    )
