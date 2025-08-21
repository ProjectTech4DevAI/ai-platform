from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.core.util import now


class AssistantBase(SQLModel):
    __table_args__ = (
        UniqueConstraint("project_id", "assistant_id", name="uq_project_assistant_id"),
    )

    assistant_id: str = Field(index=True)
    name: str
    instructions: str = Field(sa_column=Column(Text, nullable=False))
    model: str
    vector_store_ids: List[str] = Field(
        default_factory=list, sa_column=Column(ARRAY(String))
    )
    temperature: float = 0.1
    max_num_results: int = 20
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )


class Assistant(AssistantBase, table=True):
    __tablename__ = "openai_assistant"

    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)

    # Relationships
    project: "Project" = Relationship(back_populates="assistants")
    organization: "Organization" = Relationship(back_populates="assistants")


class AssistantCreate(SQLModel):
    name: str = Field(description="Name of the assistant", min_length=3, max_length=50)
    instructions: str = Field(
        description="Instructions for the assistant", min_length=10
    )
    assistant_id: str | None = Field(
        default=None,
        description="Unique identifier for the assistant",
        min_length=3,
        max_length=50,
    )
    model: str = Field(
        default="gpt-4o",
        description="Model name for the assistant",
        min_length=1,
        max_length=50,
    )
    vector_store_ids: list[str] = Field(
        default_factory=list,
        description="List of Vector Store IDs that exist in OpenAI.",
    )
    temperature: float = Field(
        default=0.1, gt=0, le=2, description="Sampling temperature between 0 and 2"
    )
    max_num_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results (must be between 1 and 100)",
    )


class AssistantUpdate(SQLModel):
    name: str | None = Field(
        default=None, description="Name of the assistant", min_length=3, max_length=50
    )
    instructions: str | None = Field(
        default=None,
        description="Instructions for the assistant",
        min_length=10,
    )
    model: str | None = Field(
        default=None, description="Name of the model", min_length=1, max_length=50
    )
    vector_store_ids_add: list[str] | None = None
    vector_store_ids_remove: list[str] | None = None
    temperature: float | None = Field(
        default=None, gt=0, le=2, description="Sampling temperature between 0 and 2"
    )
    max_num_results: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of results (must be between 1 and 100)",
    )
