import uuid
from datetime import UTC, datetime

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from pydantic import EmailStr


class Credentials(SQLModel, table=True):
    __tablename__ = "credentials"

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", index=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    secrets: dict | None = Field(default=None, sa_type=JSON)
    email: str | None = Field(default=None, max_length=255, sa_type=String)
    token: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column_kwargs={"unique": True}
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True)
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )

    # Relationships
    organization: "Organization" = Relationship(back_populates="credentials", sa_relationship_kwargs={"lazy": "selectin"})
    project: "Project" = Relationship(back_populates="credentials", sa_relationship_kwargs={"lazy": "selectin"})
