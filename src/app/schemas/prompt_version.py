from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..core.schemas import PersistentDeletion, TimestampSchema


class PromptVersionBase(BaseModel):
    version: Annotated[str, Field(min_length=1, max_length=50, examples=["v1", "v2"])]
    template: Annotated[str, Field(min_length=1, examples=["This is a sample prompt template."])]


class PromptVersion(TimestampSchema, PromptVersionBase, PersistentDeletion):
    prompt_id: int


class PromptVersionRead(BaseModel):
    id: int
    template: Annotated[str, Field(min_length=1, examples=["This is a sample prompt template."])]
    version: Annotated[str, Field(min_length=1, max_length=50, examples=["v1", "v2"])]
    created_at: datetime
    is_deleted: bool


class PromptVersionCreate(PromptVersionBase):
    model_config = ConfigDict(extra="forbid")


class PromptVersionCreateInternal(PromptVersionCreate):
    prompt_id: int


class PromptVersionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[Optional[str], Field(min_length=1, max_length=50, default=None)]
    template: Annotated[Optional[str], Field(min_length=1, default=None)]


class PromptVersionUpdateInternal(PromptVersionUpdate):
    updated_at: datetime


class PromptVersionDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_deleted: bool
    deleted_at: datetime
