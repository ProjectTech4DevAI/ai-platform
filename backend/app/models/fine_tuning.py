from typing import Optional
from uuid import UUID
from enum import Enum
from datetime import datetime

from sqlalchemy import Column, Text
from pydantic import field_validator
from sqlmodel import SQLModel, Field, Relationship

from app.core.util import now


class FineTuningStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class FineTuningJobBase(SQLModel):
    base_model: str = Field(nullable=False, description="Base model for fine-tuning")
    split_ratio: float = Field(nullable=False)
    document_id: UUID = Field(foreign_key="document.id", nullable=False)
    training_file_id: Optional[str] = Field(default=None)
    system_prompt: str = Field(sa_column=Column(Text, nullable=False))


class FineTuningJobCreate(SQLModel):
    document_id: UUID
    base_model: str
    split_ratio: list[float]
    system_prompt: str

    @field_validator("split_ratio")
    @classmethod
    def check_ratios(cls, v):
        if not v:
            raise ValueError("split_ratio cannot be empty")
        for ratio in v:
            if not (0 < ratio < 1):
                raise ValueError(
                    f"Invalid split_ratio: {ratio}. Must be between 0 and 1."
                )
        return v

    @field_validator("system_prompt")
    @classmethod
    def check_prompt(cls, v):
        if not v.strip():
            raise ValueError("system_prompt must be a non-empty string")
        return v.strip()


class Fine_Tuning(FineTuningJobBase, table=True):
    """Database model for tracking fine-tuning jobs."""

    id: int = Field(primary_key=True)
    provider_job_id: str | None = Field(
        default=None, description="Fine tuning Job ID returned by OpenAI"
    )
    status: FineTuningStatus = (
        Field(default=FineTuningStatus.pending, description="Fine tuning status"),
    )
    fine_tuned_model: str | None = Field(
        default=None, description="Final fine tuned model name from OpenAI"
    )
    train_data_s3_url: str | None = Field(
        default=None, description="S3 url of the training data stored ins S3"
    )
    test_data_s3_url: str | None = Field(
        default=None, description="S3 url of the testing data stored ins S3"
    )
    error_message: str | None = Field(
        default=None, description="error message for when something failed"
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
    model_evaluation: "ModelEvaluation" = Relationship(back_populates="fine_tuning")


class FineTuningUpdate(SQLModel):
    training_file_id: Optional[str] = None
    train_data_s3_url: Optional[str] = None
    test_data_s3_url: Optional[str] = None
    split_ratio: Optional[float] = None
    provider_job_id: Optional[str] = None
    fine_tuned_model: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class FineTuningJobPublic(SQLModel):
    """Public response model with job status and metadata."""

    id: int
    split_ratio: float
    base_model: str
    document_id: UUID
    provider_job_id: str | None = None
    status: str
    error_message: str | None = None
    fine_tuned_model: str | None = None
    training_file_id: str | None = None
    train_data_s3_url: str | None = None
    test_data_s3_url: str | None = None

    inserted_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
