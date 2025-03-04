from datetime import UTC, datetime
from sqlalchemy import DateTime

from sqlmodel import SQLModel, Field, Relationship


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"

    id: int | None = Field(default=None, primary_key=True)
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
    projects: list["Project"] = Relationship(
        back_populates="organization",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"}
    )
    credentials: list["Credentials"] = Relationship(
        back_populates="organization",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"}
    )
