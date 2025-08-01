from sqlmodel import SQLModel, Field
from datetime import datetime
from app.core.util import now


class PromptBase(SQLModel):
    name: str = Field(index=True, nullable=False, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1,max_length=500)


class Prompt(PromptBase, table=True):
    id: int = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = None


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
