from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LibraryValidationError(ValueError):
    pass


class LibraryItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: str
    title: str | None
    tags: tuple[str, ...]
    status: str
    archived: bool
    version: str
    created_at: datetime
    updated_at: datetime


class LibraryPage(BaseModel):
    items: tuple[LibraryItem, ...]
    total: int
    page: int
    page_size: int


class LibraryPatch(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    expected_version: str = Field(pattern=r'^[0-9a-f]{64}$')
    title: str | None = Field(default=None, max_length=120)
    tags: tuple[str, ...] | None = Field(default=None, max_length=100)
    archived: bool | None = None

    @model_validator(mode='after')
    def editable(self):
        if not self.model_fields_set & {'title', 'tags', 'archived'}:
            raise LibraryValidationError('at least one editable field is required')
        if self.tags is not None and any(not tag.strip() or len(tag) > 80 or any(ord(c) < 32 for c in tag) for tag in self.tags):
            raise LibraryValidationError('tag must be visible text with at most 80 characters')
        return self
