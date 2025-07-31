from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON

from app.core.util import now


class FineTuningJobBase(SQLModel):
    base_model: str = Field(
        default="gpt-4.1-nano-2025-04-14", description="Base model for fine-tuning"
    )
    split_ratio: float = Field(nullable=False)
    document_id: UUID = Field(foreign_key="document.id", nullable=False)
    training_file_id: Optional[str] = Field(default=None)
    testing_file_id: Optional[str] = Field(default=None)


class FineTuningJobCreate(SQLModel):
    base_model: str = Field(
        default="gpt-4.1-nano-2025-04-14", description="Base model for fine-tuning"
    )
    split_ratio: list[float]
    document_id: UUID


class Fine_Tuning(FineTuningJobBase, table=True):
    """Database model for tracking fine-tuning jobs."""

    id: int = Field(primary_key=True)
    openai_job_id: str | None = Field(
        default=None, description="Fine tuning Job ID returned by OpenAI"
    )
    status: str = Field(default="pending", description="Status of the fine-tuning job")
    fine_tuned_model: str | None = Field(
        default=None, description="Final fine tuned model name from OpenAI"
    )
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    is_deleted: bool = Field(default=False, nullable=False)

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    deleted_at: datetime | None = Field(default=None, nullable=True)

    project: "Project" = Relationship(back_populates="fine_tuning")
    organization: "Organization" = Relationship(back_populates="fine_tuning")


class FineTuningJobPublic(SQLModel):
    """Public response model with job status and metadata."""

    id: int
    split_ratio: float
    base_model: str
    document_id: UUID
    openai_job_id: str | None = None
    status: str
    fine_tuned_model: str | None = None
    training_file_id: str | None = None
    testing_file_id: str | None = None

    inserted_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
