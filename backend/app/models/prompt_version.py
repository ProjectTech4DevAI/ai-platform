from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Relationship

from app.core.util import now

if TYPE_CHECKING:
    from app.models.prompt import Prompt


class PromptVersionBase(SQLModel):
    instruction: str = Field(nullable=False, min_length=1)
    commit_message: str | None = Field(default=None, max_length=512)


class PromptVersion(PromptVersionBase, table=True):
    __tablename__ = "prompt_version"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    prompt_id: UUID = Field(foreign_key="prompt.id", nullable=False)
    version: int = Field(nullable=False)

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: datetime | None = Field(default=None)

    prompt: "Prompt" = Relationship(
        back_populates="versions",
        sa_relationship_kwargs={"foreign_keys": "[PromptVersion.prompt_id]"},
    )


class PromptVersionPublic(PromptVersionBase):
    id: UUID
    prompt_id: UUID
    version: int
    inserted_at: datetime
    updated_at: datetime


class PromptVersionCreate(PromptVersionBase):
    pass
