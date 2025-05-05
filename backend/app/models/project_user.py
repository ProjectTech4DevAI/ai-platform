import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

from app.core.util import now

# Shared properties
class ProjectUserBase(SQLModel):
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    is_admin: bool = Field(
        default=False, nullable=False
    )  # Determines if user is an admin of the project


class ProjectUserPublic(ProjectUserBase):
    id: int
    inserted_at: datetime
    updated_at: datetime


# Database model, database table inferred from class name
class ProjectUser(ProjectUserBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    # Relationships
    project: "Project" = Relationship(back_populates="users")
    user: "User" = Relationship(back_populates="projects")


# Properties to return as a list
class ProjectUsersPublic(SQLModel):
    data: List[ProjectUserPublic]
    count: int
