from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

from app.core.util import now

if TYPE_CHECKING:
    from app.models.prompt import Prompt


class PromptVersionLabel(str, Enum):
    STAGING = "staging"
    PRODUCTION = "production"


class PromptVersionBase(SQLModel):
    instruction: str = Field(nullable=False, min_length=1)
    commit_message: str | None = Field(default=None, max_length=512)


class PromptVersion(PromptVersionBase, table=True):
    __tablename__ = "prompt_version"

    id: int | None = Field(default=None, primary_key=True)
    prompt_id: int = Field(foreign_key="prompt.id")

    version: int
    label: PromptVersionLabel = Field(
        default=PromptVersionLabel.STAGING, nullable=False
    )

    inserted_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None)

    prompt: "Prompt" = Relationship(back_populates="versions")


class PromptVersionPublic(PromptVersionBase):
    id: int
    prompt_id: int
    label: PromptVersionLabel
    version: int
    inserted_at: datetime
    updated_at: datetime


class PromptVersionCreate(PromptVersionBase):
    pass


class PromptVersionUpdate(SQLModel):
    label: PromptVersionLabel | None = None
