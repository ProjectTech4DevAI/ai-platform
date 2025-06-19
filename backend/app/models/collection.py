from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now
from .user import User
from .organization import Organization
from .project import Project
from enum import Enum


class Collection(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    owner_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )

    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        ondelete="CASCADE",
    )

    project_id: int = Field(
        foreign_key="project.id",
        nullable=True,
        ondelete="SET NULL",
    )

    llm_service_id: Optional[str] = Field(default=None, nullable=True)
    llm_service_name: Optional[str] = Field(default=None, nullable=True)

    status: Optional[str] = None

    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    deleted_at: Optional[datetime] = None

    owner: User = Relationship(back_populates="collections")
    organization: Organization = Relationship(back_populates="collections")
    project: Project = Relationship(back_populates="collections")
