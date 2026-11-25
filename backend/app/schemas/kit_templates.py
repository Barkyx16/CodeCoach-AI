"""Personal kit templates (Volume 11, prompt 7; docs/TEMPLATES.md): checklist items and questions to
ask, kept as a snapshot to start another interview's kit from. Plain text only: there are no
placeholders, and nothing in a template is ever evaluated, fetched or filled in."""

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.common import APIModel, OptionalKey, SaveReplay, save_replay_field, update_key_field
from app.schemas.kits import QuestionGroup

MAX_TEMPLATE_ITEMS = 40  # each list, the same as a kit's


class TemplateChecklistItem(APIModel):
    text: str = Field(min_length=1, max_length=200)


class TemplateQuestion(APIModel):
    text: str = Field(min_length=1, max_length=300)
    group: QuestionGroup = "other"


class _Content(APIModel):
    checklist: list[TemplateChecklistItem] = Field(default_factory=list, max_length=MAX_TEMPLATE_ITEMS)
    questions: list[TemplateQuestion] = Field(default_factory=list, max_length=MAX_TEMPLATE_ITEMS)


class KitTemplateCreate(_Content):
    name: str = Field(min_length=1, max_length=80)
    client_request_id: OptionalKey = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="One key per new template: sending the same create again (its reply was lost) "
        "returns the template it made",
    )

    @model_validator(mode="after")
    def _something(self) -> "KitTemplateCreate":
        if not self.checklist and not self.questions:
            raise ValueError("A template needs at least one checklist item or question.")
        return self


class KitTemplateUpdate(APIModel):
    """Rename, or replace the items. Saved against the revision you loaded (409 stale_revision with
    the saved template in details.current if it changed since)."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    checklist: list[TemplateChecklistItem] | None = Field(default=None, max_length=MAX_TEMPLATE_ITEMS)
    questions: list[TemplateQuestion] | None = Field(default=None, max_length=MAX_TEMPLATE_ITEMS)
    expected_revision: int = Field(ge=1)
    client_request_id: OptionalKey = update_key_field()


class KitTemplateSummary(APIModel):
    id: str
    name: str
    checklist_count: int
    questions_count: int
    revision: int
    updated_at: datetime


class KitTemplateOut(APIModel):
    id: str
    name: str
    checklist: list[TemplateChecklistItem]
    questions: list[TemplateQuestion]
    revision: int
    save_replay: SaveReplay | None = save_replay_field()
    created_at: datetime
    updated_at: datetime
