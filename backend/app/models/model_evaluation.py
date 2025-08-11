from typing import Optional
from uuid import UUID
from enum import Enum
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSON

from app.core.util import now


class ModelEvaluationStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ModelEvaluationBase(SQLModel):
    fine_tuning_id: int = Field(
        foreign_key="fine_tuning.id",
        nullable=False,
        ondelete="CASCADE",
    )


class ModelEvaluationCreate(SQLModel):
    fine_tuning_ids: list[int]


class Model_Evaluation(ModelEvaluationBase, table=True):
    """Database model for keeping a record of model evaluation"""

    id: int = Field(primary_key=True)

    document_id: UUID = Field(
        foreign_key="document.id",
        nullable=False,
    )
    model_name: str = Field(description="fine tuned model name from OpenAI")
    testing_file_id: str = Field(
        description="File ID of the testing file uploaded to OpenAI"
    )
    base_model: str = Field(nullable=False, description="Base model for fine-tuning")
    split_ratio: float = Field(
        nullable=False, description="the ratio the dataset was divided in"
    )
    system_prompt: str = Field(sa_column=Column(Text, nullable=False))
    metric: list[str] = Field(
        sa_column=Column(JSON, nullable=False),
        description="List of metrics used for evaluation (e.g., ['mcc', 'accuracy'])",
    )
    score: Optional[dict[str, float]] = Field(
        sa_column=Column(JSON, nullable=True),
        description="Evaluation scores per metric (e.g., {'mcc': 0.85})",
    )
    status: ModelEvaluationStatus = (
        Field(default=ModelEvaluationStatus.pending, description="Evaluation status"),
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

    project: "Project" = Relationship(back_populates="model_evaluation")
    fine_tuning: "Fine_Tuning" = Relationship(back_populates="model_evaluation")


class ModelEvaluationUpdate(SQLModel):
    metric: Optional[list[str]] = None
    score: Optional[dict[str, float]] = None
    status: Optional[ModelEvaluationStatus] = None
    error_message: Optional[str] = None


class ModelEvaluationPublic(ModelEvaluationBase):
    """Public response model for evaluation result."""

    id: int
    document_id: UUID
    model_name: str
    split_ratio: float
    base_model: str
    score: dict[str, float] | None = None
    status: ModelEvaluationStatus
    is_best_model: bool | None = None
    inserted_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
