from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ..core.schemas import PersistentDeletion, TimestampSchema


class TagBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=20, examples=["Important", "Bug", "Feature"])]
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$", examples=["#FF5733"])]  # Hex color format


class Tag(TimestampSchema, TagBase, PersistentDeletion):
    project_id: int
    organization_id: int


class TagRead(BaseModel):
    id: int
    name: Annotated[str, Field(min_length=1, max_length=20, examples=["Important", "Bug", "Feature"])]
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$", examples=["#FF5733"])]
    project_id: int
    organization_id: int
    created_at: datetime


class TagCreate(TagBase):
    model_config = ConfigDict(extra="forbid")


class TagCreateInternal(TagCreate):
    project_id: int
    organization_id: int


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=1, max_length=20, examples=["UpdatedTag"], default=None)]
    color: Annotated[str | None, Field(pattern=r"^#[0-9A-Fa-f]{6}$", examples=["#123ABC"], default=None)]


class TagUpdateInternal(TagUpdate):
    updated_at: datetime


class TagDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_deleted: bool
    deleted_at: datetime
