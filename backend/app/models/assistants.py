from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel, Column, String
from sqlalchemy.dialects.postgresql import ARRAY
from pydantic import BaseModel, Field as PydanticField, field_validator


from app.core.util import now

ALLOWED_OPENAI_MODELS = {"gpt-3.5-turbo", "gpt-4", "gpt-4o"}


class AssistantBase(SQLModel):
    assistant_id: str = Field(index=True, unique=True)
    name: str
    instructions: str
    model: str
    vector_store_ids: List[str] = Field(
        default_factory=list, sa_column=Column(ARRAY(String))
    )
    temperature: float = 0.1
    max_num_results: int = 20
    project_id: int = Field(foreign_key="project.id")
    organization_id: int = Field(foreign_key="organization.id")


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
    name: str = PydanticField(description="Name of the assistant")
    instructions: str = PydanticField(description="Instructions for the assistant")
    model: str = PydanticField(
        default="gpt-4o", description="Model name for the assistant"
    )
    vector_store_ids: List[str] = PydanticField(
        default_factory=list,
        description="List of Vector Store IDs that exist in OpenAI.",
    )
    temperature: Optional[float] = PydanticField(
        default=0.1, ge=0, le=2, description="Sampling temperature between 0 and 2"
    )
    max_num_results: Optional[int] = PydanticField(
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
    name: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    vector_store_ids_add: Optional[List[str]] = None
    vector_store_ids_remove: Optional[List[str]] = None
    temperature: Optional[float] = PydanticField(
        default=None, ge=0, le=2, description="Sampling temperature between 0 and 2"
    )
    max_num_results: Optional[int] = PydanticField(
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
