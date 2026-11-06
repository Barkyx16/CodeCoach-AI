"""Restoring your own data from a backup file."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class RestoreSkip(APIModel):
    reason: str
    count: int


class RestoreCategory(APIModel):
    key: Literal["notes", "stories", "bookmarks", "applications"]
    label: str
    found: int = Field(description="Records of this kind in the file")
    new: int = Field(description="Would be added")
    duplicates: int = Field(description="Already in your account (or twice in the file): skipped")
    skipped: list[RestoreSkip]
    samples: list[str] = Field(description="A few titles, so you can recognise them")


class RestoreUnsupported(APIModel):
    key: str
    count: int
    reason: str


class RestoreBatch(APIModel):
    id: str
    status: Literal["applied", "failed", "removed"]
    categories: list[str]
    counts: dict
    removal: dict | None = Field(description="After removal: removed, kept_edited, already_gone")
    created_at: datetime
    removed_at: datetime | None


class RestorePreview(APIModel):
    export_version: int
    exported_at: str | None
    file_sha256: str
    from_other_account: bool = Field(
        description="The file names a different account; only its content can come into yours"
    )
    categories: list[RestoreCategory]
    not_restored: list[RestoreUnsupported]
    ignored_fields: int = Field(description="Unknown fields inside records, ignored")
    previous: list[RestoreBatch] = Field(description="Earlier restores of this same file")
