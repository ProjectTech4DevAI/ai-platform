from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

from app.core.util import now

if TYPE_CHECKING:
    from app.models.prompt_version import PromptVersion


class PromptBase(SQLModel):
    name: str = Field(index=True, nullable=False, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=500)


class Prompt(PromptBase, table=True):
    id: int = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = None

    versions: list["PromptVersion"] = Relationship(back_populates="prompt")


class PromptPublic(PromptBase):
    id: int
    project_id: int
    inserted_at: datetime
    updated_at: datetime


class PromptCreate(PromptBase):
    pass


class PromptUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=500)

    class Config:
        from_attributes = True
