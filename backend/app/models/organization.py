from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy.orm import relationship

from app.core.util import now

if TYPE_CHECKING:
    from .credentials import Credential
    from .project import Project
    from .api_key import APIKey
    from .assistants import Assistant


# Shared properties for an Organization
class OrganizationBase(SQLModel):
    name: str = Field(unique=True, index=True, max_length=255)
    is_active: bool = True


# Properties to receive via API on creation
class OrganizationCreate(OrganizationBase):
    pass


# Properties to receive via API on update, all are optional
class OrganizationUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = Field(default=None)


# Database model for Organization
class Organization(OrganizationBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    # Relationship back to Creds
    api_keys: list["APIKey"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    creds: list["Credential"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    project: list["Project"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    assistants: list["Assistant"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete"}
    )


# Properties to return via API
class OrganizationPublic(OrganizationBase):
    id: int
    inserted_at: datetime
    updated_at: datetime


class OrganizationsPublic(SQLModel):
    data: list[OrganizationPublic]
    count: int
