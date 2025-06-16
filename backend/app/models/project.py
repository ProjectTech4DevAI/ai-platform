from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, Relationship, SQLModel

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
    id: int = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organization.id", index=True)
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    users: list["ProjectUser"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    creds: list["Credential"] = Relationship(
        back_populates="project", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    api_keys: list["APIKey"] = Relationship(
        back_populates="project", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    organization: Optional["Organization"] = Relationship(back_populates="project")


# Properties to return via API
class ProjectPublic(ProjectBase):
    id: int
    organization_id: int
    inserted_at: datetime
    updated_at: datetime


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int
