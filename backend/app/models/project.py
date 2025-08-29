from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.core.util import now


# Shared properties for a Project
class ProjectBase(SQLModel):
    name: str = Field(index=True, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


# Properties to receive via API on creation
class ProjectCreate(ProjectBase):
    organization_id: int


# Properties to receive via API on update, all are optional
class ProjectUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = Field(default=None)


# Database model for Project
class Project(ProjectBase, table=True):
    __table_args__ = (
        UniqueConstraint("name", "organization_id", name="uq_project_name_org_id"),
    )

    id: int = Field(default=None, primary_key=True)
    organization_id: int = Field(
        foreign_key="organization.id", index=True, nullable=False, ondelete="CASCADE"
    )
    storage_path: UUID = Field(default_factory=uuid4, nullable=False, unique=True)
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    users: list["ProjectUser"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    creds: list["Credential"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    assistants: list["Assistant"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    api_keys: list["APIKey"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    organization: Optional["Organization"] = Relationship(back_populates="project")
    collections: list["Collection"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    openai_conversations: list["OpenAIConversation"] = Relationship(
        back_populates="project", cascade_delete=True
    )


# Properties to return via API
class ProjectPublic(ProjectBase):
    id: int
    organization_id: int
    inserted_at: datetime
    updated_at: datetime


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int
