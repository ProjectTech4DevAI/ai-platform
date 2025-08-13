from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, ForeignKey
from sqlmodel import SQLModel, Field, Relationship

from app.core.util import now
from app.models.prompt_version import (
    PromptVersion,
    PromptVersionCreate,
    PromptVersionPublic,
)


class PromptBase(SQLModel):
    name: str = Field(index=True, nullable=False, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=500)


class Prompt(PromptBase, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    active_version: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(
            ForeignKey(
                "prompt_version.id",
                use_alter=True,
                deferrable=True,
                initially="DEFERRED",
            ),
            nullable=False,
        ),
    )
    project_id: int = Field(foreign_key="project.id")
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = None

    versions: list["PromptVersion"] = Relationship(
        back_populates="prompt",
        sa_relationship_kwargs={"foreign_keys": "[PromptVersion.prompt_id]"},
    )


class PromptPublic(PromptBase):
    id: UUID
    active_version: UUID
    project_id: int
    inserted_at: datetime
    updated_at: datetime


class PromptWithVersion(PromptPublic):
    version: PromptVersionPublic


class PromptWithVersions(PromptPublic):
    versions: list[PromptVersionPublic]


class PromptCreate(PromptBase, PromptVersionCreate):
    pass


class PromptUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    active_version: UUID | None = Field(default=None)

    class Config:
        from_attributes = True
