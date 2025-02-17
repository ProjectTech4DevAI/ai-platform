from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..core.schemas import PersistentDeletion, TimestampSchema


class PromptBase(BaseModel):
    title: Annotated[str, Field(min_length=2, max_length=255, examples=["My prompt title"])]


class Prompt(TimestampSchema, PromptBase, PersistentDeletion):
    project_id: int
    organization_id: int
    active_version: Annotated[str, Field(max_length=50, examples=["v1"])]
    is_suggested: Annotated[bool, Field(default=False)]


class PromptRead(BaseModel):
    id: int
    title: Annotated[str, Field(min_length=2, max_length=255, examples=["My prompt title"])]
    active_version: Annotated[str, Field(max_length=50, examples=["v1"])]
    template: Annotated[str, Field(min_length=1, examples=["This is a sample prompt template."])]
    created_at: datetime
    updated_at: Optional[datetime]


class PromptCreate(PromptBase):
    model_config = ConfigDict(extra="forbid")

    active_version: Annotated[str, Field(max_length=50, examples=["initial version"])]
    template: Annotated[str, Field(min_length=1, examples=["This is a sample prompt template."])]


class PromptCreateInternal(PromptBase):
    active_version: Annotated[str, Field(max_length=50, examples=["initial version"])]
    project_id: int
    organization_id: int
    is_suggested: Annotated[bool, Field(default=False)]


class PromptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[Optional[str], Field(min_length=2, max_length=255, default=None)]
    template: Annotated[Optional[str], Field(min_length=1, default=None)]
    active_version: Annotated[Optional[str], Field(max_length=50, default=None)]


class PromptUpdateInternal(PromptUpdate):
    updated_at: datetime


class PromptDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_deleted: bool
    deleted_at: datetime
