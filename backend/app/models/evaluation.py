from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, Text
from sqlmodel import Field as SQLField
from sqlmodel import Relationship, SQLModel

from app.core.util import now


class DatasetItem(BaseModel):
    """Model for a single dataset item (Q&A pair)."""

    question: str = Field(..., description="The question/input")
    answer: str = Field(..., description="The expected answer/output")


class DatasetUploadResponse(BaseModel):
    """Response model for dataset upload."""

    dataset_name: str = Field(..., description="Name of the created dataset")
    total_items: int = Field(
        ..., description="Total number of items uploaded (after duplication)"
    )
    original_items: int = Field(
        ..., description="Number of original items before duplication"
    )
    duplication_factor: int = Field(
        default=5, description="Number of times each item was duplicated"
    )
    langfuse_dataset_id: str | None = Field(
        None, description="Langfuse dataset ID if available"
    )


class EvaluationResult(BaseModel):
    """Model for a single evaluation result."""

    input: str = Field(..., description="The input question/prompt used for evaluation")
    output: str = Field(..., description="The actual output from the assistant")
    expected: str = Field(..., description="The expected output from the dataset")
    thread_id: str | None = Field(None, description="ID of the OpenAI")


class Experiment(BaseModel):
    """Model for the complete experiment evaluation response."""

    experiment_name: str = Field(..., description="Name of the experiment")
    dataset_name: str = Field(
        ..., description="Name of the dataset used for evaluation"
    )
    results: list[EvaluationResult] = Field(
        ..., description="List of evaluation results"
    )
    total_items: int = Field(..., description="Total number of items evaluated")
    note: str = Field(..., description="Additional notes about the evaluation process")


# Database Models


class EvaluationRun(SQLModel, table=True):
    """Database table for evaluation runs."""

    __tablename__ = "evaluation_run"

    id: int = SQLField(default=None, primary_key=True)

    # Input fields (provided by user)
    run_name: str = SQLField(index=True, description="Name of the evaluation run")
    dataset_name: str = SQLField(description="Name of the Langfuse dataset")

    # Config field - dict requires sa_column
    config: dict[str, Any] = SQLField(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Evaluation configuration",
    )

    # Batch job references
    batch_job_id: int | None = SQLField(
        default=None,
        foreign_key="batch_job.id",
        description="Reference to the batch_job that processes this evaluation (responses)",
    )
    embedding_batch_job_id: int | None = SQLField(
        default=None,
        foreign_key="batch_job.id",
        description="Reference to the batch_job for embedding-based similarity scoring",
    )

    # Output/Status fields (updated by system during processing)
    status: str = SQLField(
        default="pending",
        description="Overall evaluation status: pending, processing, completed, failed",
    )
    s3_url: str | None = SQLField(
        default=None,
        description="S3 URL of processed evaluation results for future reference",
    )
    total_items: int = SQLField(
        default=0, description="Total number of items evaluated (set during processing)"
    )

    # Score field - dict requires sa_column
    score: dict[str, Any] | None = SQLField(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Evaluation scores (e.g., correctness, cosine_similarity, etc.)",
    )

    # Langfuse trace IDs mapping (item_id -> trace_id)
    langfuse_trace_ids: dict[str, str] | None = SQLField(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Mapping of item_id to Langfuse trace_id for updating traces with scores",
    )

    # Error message field
    error_message: str | None = SQLField(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Error message if failed",
    )

    # Foreign keys
    organization_id: int = SQLField(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    project_id: int = SQLField(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )

    # Timestamps
    inserted_at: datetime = SQLField(default_factory=now, nullable=False)
    updated_at: datetime = SQLField(default_factory=now, nullable=False)

    # Relationships
    project: "Project" = Relationship(back_populates="evaluation_runs")
    organization: "Organization" = Relationship(back_populates="evaluation_runs")
    batch_job: Optional["BatchJob"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[EvaluationRun.batch_job_id]"}
    )  # noqa: F821
    embedding_batch_job: Optional["BatchJob"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[EvaluationRun.embedding_batch_job_id]"
        }
    )  # noqa: F821


class EvaluationRunCreate(SQLModel):
    """Model for creating an evaluation run."""

    run_name: str = Field(description="Name of the evaluation run", min_length=3)
    dataset_name: str = Field(description="Name of the Langfuse dataset", min_length=1)
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluation configuration (flexible dict with llm, instructions, vector_store_ids, etc.)",
    )


class EvaluationRunPublic(SQLModel):
    """Public model for evaluation runs."""

    id: int
    run_name: str
    dataset_name: str
    config: dict[str, Any]
    batch_job_id: int | None
    embedding_batch_job_id: int | None
    status: str
    s3_url: str | None
    total_items: int
    score: dict[str, Any] | None
    langfuse_trace_ids: dict[str, str] | None
    error_message: str | None
    organization_id: int
    project_id: int
    inserted_at: datetime
    updated_at: datetime
