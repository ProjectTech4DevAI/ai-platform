from datetime import UTC, datetime
from sqlalchemy import DateTime

from sqlmodel import SQLModel, Field, Relationship


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", index=True)
    name: str = Field(unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True)
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )

    # Relationships
    organization: "Organization" = Relationship(
        back_populates="projects",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    credentials: list["Credentials"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"}
    )
