from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class BatchJob(SQLModel, table=True):
    """Batch job table for tracking async LLM batch operations."""

    __tablename__ = "batch_job"

    id: int | None = Field(default=None, primary_key=True)

    # Provider and job type
    provider: str = Field(description="LLM provider name (e.g., 'openai', 'anthropic')")
    job_type: str = Field(
        description="Type of batch job (e.g., 'evaluation', 'classification', 'embedding')"
    )

    # Batch configuration - stores all provider-specific config
    config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB()),
        description="Complete batch configuration including model, temperature, instructions, tools, etc.",
    )

    # Provider-specific batch tracking
    provider_batch_id: str | None = Field(
        default=None, description="Provider's batch job ID (e.g., OpenAI batch_id)"
    )
    provider_file_id: str | None = Field(
        default=None, description="Provider's input file ID"
    )
    provider_output_file_id: str | None = Field(
        default=None, description="Provider's output file ID"
    )

    # Provider status tracking
    provider_status: str | None = Field(
        default=None,
        description="Provider-specific status (e.g., OpenAI: validating, in_progress, finalizing, completed, failed, expired, cancelling, cancelled)",
    )

    # Raw results (before parent-specific processing)
    raw_output_url: str | None = Field(
        default=None, description="S3 URL of raw batch output file"
    )
    total_items: int = Field(
        default=0, description="Total number of items in the batch"
    )

    # Error handling
    error_message: str | None = Field(
        default=None, description="Error message if batch failed"
    )

    # Foreign keys
    organization_id: int = Field(foreign_key="organization.id")
    project_id: int = Field(foreign_key="project.id")

    # Timestamps
    inserted_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    organization: Optional["Organization"] = Relationship(  # noqa: F821
        back_populates="batch_jobs"
    )
    project: Optional["Project"] = Relationship(
        back_populates="batch_jobs"
    )  # noqa: F821


class BatchJobCreate(SQLModel):
    """Schema for creating a new batch job."""

    provider: str
    job_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    provider_batch_id: str | None = None
    provider_file_id: str | None = None
    provider_output_file_id: str | None = None
    provider_status: str | None = None
    raw_output_url: str | None = None
    total_items: int = 0
    error_message: str | None = None
    organization_id: int
    project_id: int


class BatchJobUpdate(SQLModel):
    """Schema for updating a batch job."""

    provider_batch_id: str | None = None
    provider_file_id: str | None = None
    provider_output_file_id: str | None = None
    provider_status: str | None = None
    raw_output_url: str | None = None
    total_items: int | None = None
    error_message: str | None = None


class BatchJobPublic(SQLModel):
    """Public schema for batch job responses."""

    id: int
    provider: str
    job_type: str
    config: dict[str, Any]
    provider_batch_id: str | None
    provider_file_id: str | None
    provider_output_file_id: str | None
    provider_status: str | None
    raw_output_url: str | None
    total_items: int
    error_message: str | None
    organization_id: int
    project_id: int
    inserted_at: datetime
    updated_at: datetime
