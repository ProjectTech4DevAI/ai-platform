from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field as PydanticField, field_validator
from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship, SQLModel

from app.core.config import settings
from app.core.util import now

ALLOWED_OPENAI_MODELS = settings.ALLOWED_OPENAI_MODELS


class AssistantBase(SQLModel):
    assistant_id: str = Field(index=True, unique=True)
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


class AssistantCreate(BaseModel):
    name: str = PydanticField(description="Name of the assistant", min_length=1)
    instructions: str = PydanticField(
        description="Instructions for the assistant", min_length=1
    )
    model: str = PydanticField(
        default="gpt-4o", description="Model name for the assistant"
    )
    vector_store_ids: list[str] = PydanticField(
        default_factory=list,
        description="List of Vector Store IDs that exist in OpenAI.",
    )
    temperature: float | None = PydanticField(
        default=0.1, ge=0, le=2, description="Sampling temperature between 0 and 2"
    )
    max_num_results: int | None = PydanticField(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results (must be between 1 and 100)",
    )

    @field_validator("model")
    def validate_openai_model(cls, v):
        if v not in ALLOWED_OPENAI_MODELS:
            raise ValueError(
                f"Model '{v}' is not a supported OpenAI model. Choose from: {', '.join(ALLOWED_OPENAI_MODELS)}"
            )
        return v


class AssistantUpdate(BaseModel):
    name: str | None = None
    instructions: str | None = None
    model: str | None = None
    vector_store_ids_add: list[str] | None = None
    vector_store_ids_remove: list[str] | None = None
    temperature: float | None = PydanticField(
        default=None, ge=0, le=2, description="Sampling temperature between 0 and 2"
    )
    max_num_results: int | None = PydanticField(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of results (must be between 1 and 100)",
    )

    @field_validator("model")
    def validate_openai_model(cls, v):
        if v not in ALLOWED_OPENAI_MODELS:
            raise ValueError(
                f"Model '{v}' is not a supported OpenAI model. Choose from: {', '.join(ALLOWED_OPENAI_MODELS)}"
            )
        return v
