from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON

from app.core.util import now


class FineTuningJobBase(SQLModel):
    base_model: str
    split_ratio: List[float] = Field(sa_column=Column(JSON, nullable=False))

    document_id: UUID = Field(
        foreign_key="document.id",
        nullable=False,
        ondelete="CASCADE",
    )

    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )


class FineTuningJobCreate(FineTuningJobBase):
    """Create new fine-tuning job.
    These fields are required when initiating the job.
    """

    pass


class Fine_Tuning(FineTuningJobBase, table=True):
    """Database model for tracking fine-tuning jobs."""

    id: int = Field(primary_key=True)

    openai_job_id: Optional[str] = Field(
        default=None, description="Fine tuning Job ID returned by OpenAI"
    )
    status: str = Field(default=None, description="Status of the fine-tuning job")
    fine_tuned_model: Optional[str] = Field(
        default=None, description="Final fine tuned model name from OpenAI"
    )

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)

    project: "Project" = Relationship(back_populates="fine_tuning")
    organization: "Organization" = Relationship(back_populates="fine_tuning")
    model_evaluation: List["Model_Evaluation"] = Relationship(
        back_populates="fine_tuning"
    )


class FineTuningJobPublic(FineTuningJobBase):
    """Public response model with job status and metadata."""

    id: int
    openai_job_id: Optional[str] = None
    status: str
    fine_tuned_model: Optional[str] = None
    inserted_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
