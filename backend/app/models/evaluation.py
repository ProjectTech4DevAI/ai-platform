from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Text, JSON
from sqlmodel import Field as SQLField, Relationship, SQLModel

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


class EvaluationRunBase(SQLModel):
    """Base model for evaluation runs."""

    # Input fields (provided by user)
    run_name: str = SQLField(index=True, description="Name of the evaluation run")
    dataset_name: str = SQLField(description="Name of the Langfuse dataset")
    config: dict = SQLField(
        default={},
        sa_column=Column(JSON, nullable=False),
        description="Evaluation configuration (LLM settings, instructions, vector stores)",
    )

    # Output/Status fields (updated by system during processing)
    status: str = SQLField(
        default="pending",
        description="Overall evaluation status: pending, processing, completed, failed",
    )
    batch_status: Optional[str] = SQLField(
        default=None,
        description="OpenAI Batch API status: validating, in_progress, finalizing, completed, failed, expired, cancelling, cancelled (for polling)",
    )
    batch_id: Optional[str] = SQLField(
        default=None, description="OpenAI Batch API batch ID (set during processing)"
    )
    batch_file_id: Optional[str] = SQLField(
        default=None,
        description="OpenAI file ID for batch input (set during processing)",
    )
    batch_output_file_id: Optional[str] = SQLField(
        default=None,
        description="OpenAI file ID for batch output (set after completion)",
    )
    s3_url: Optional[str] = SQLField(
        default=None, description="S3 URL of OpenAI output file for future reference"
    )
    total_items: int = SQLField(
        default=0, description="Total number of items evaluated (set during processing)"
    )
    score: Optional[dict] = SQLField(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Evaluation scores (e.g., correctness, cosine_similarity, etc.) (set after completion)",
    )
    error_message: Optional[str] = SQLField(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Error message if failed",
    )
    organization_id: int = SQLField(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    project_id: int = SQLField(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )


class EvaluationRun(EvaluationRunBase, table=True):
    """Database table for evaluation runs."""

    __tablename__ = "evaluation_run"

    id: int = SQLField(default=None, primary_key=True)
    inserted_at: datetime = SQLField(default_factory=now, nullable=False)
    updated_at: datetime = SQLField(default_factory=now, nullable=False)

    # Relationships
    project: "Project" = Relationship(back_populates="evaluation_runs")
    organization: "Organization" = Relationship(back_populates="evaluation_runs")


class EvaluationRunCreate(SQLModel):
    """Model for creating an evaluation run."""

    run_name: str = Field(description="Name of the evaluation run", min_length=3)
    dataset_name: str = Field(description="Name of the Langfuse dataset", min_length=1)
    config: dict = Field(
        description="Evaluation configuration (flexible dict with llm, instructions, vector_store_ids, etc.)"
    )


class EvaluationRunPublic(EvaluationRunBase):
    """Public model for evaluation runs."""

    id: int
    inserted_at: datetime
    updated_at: datetime
