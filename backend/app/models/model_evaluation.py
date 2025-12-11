from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import field_validator
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now
from app.models.project import Project


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

    @field_validator("fine_tuning_ids")
    @classmethod
    def dedupe_ids(cls, v: list[int]) -> list[int]:
        return list(dict.fromkeys(v))


class ModelEvaluation(ModelEvaluationBase, table=True):
    """Database model for keeping a record of model evaluation."""

    __tablename__ = "model_evaluation"

    id: int = Field(
        primary_key=True,
        sa_column_kwargs={"comment": "Unique identifier for the evaluation"},
    )
    fine_tuned_model: str = Field(
        sa_column_kwargs={"comment": "Name of the fine-tuned model being evaluated"},
    )
    test_data_s3_object: str = Field(
        sa_column_kwargs={"comment": "S3 URI of the testing data"},
    )
    base_model: str = Field(
        nullable=False,
        sa_column_kwargs={"comment": "Base model used for fine-tuning"},
    )
    split_ratio: float = Field(
        nullable=False,
        sa_column_kwargs={"comment": "Train/test split ratio used"},
    )
    system_prompt: str = Field(
        sa_column=Column(
            Text, nullable=False, comment="System prompt used during evaluation"
        )
    )
    score: dict[str, float] | None = Field(
        sa_column=Column(
            JSON, nullable=True, comment="Evaluation scores per metric (e.g., MCC)"
        ),
    )
    prediction_data_s3_object: str | None = Field(
        default=None,
        sa_column_kwargs={"comment": "S3 URL where the prediction data is stored"},
    )
    status: ModelEvaluationStatus = Field(
        default=ModelEvaluationStatus.pending,
        sa_column_kwargs={"comment": "Current status of the evaluation"},
    )
    error_message: str | None = Field(
        default=None,
        sa_column_kwargs={"comment": "Error message if evaluation failed"},
    )
    is_deleted: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={"comment": "Soft delete flag"},
    )

    # Foreign keys
    fine_tuning_id: int = Field(
        foreign_key="fine_tuning.id",
        nullable=False,
        ondelete="CASCADE",
        sa_column_kwargs={"comment": "Reference to the fine-tuning job"},
    )
    document_id: UUID = Field(
        foreign_key="document.id",
        nullable=False,
        sa_column_kwargs={"comment": "Reference to the evaluation document"},
    )
    project_id: int = Field(
        foreign_key="project.id",
        nullable=False,
        ondelete="CASCADE",
        sa_column_kwargs={"comment": "Reference to the project"},
    )
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        ondelete="CASCADE",
        sa_column_kwargs={"comment": "Reference to the organization"},
    )

    # Timestamps
    inserted_at: datetime = Field(
        default_factory=now,
        nullable=False,
        sa_column_kwargs={"comment": "Timestamp when the evaluation was created"},
    )
    updated_at: datetime = Field(
        default_factory=now,
        nullable=False,
        sa_column_kwargs={"comment": "Timestamp when the evaluation was last updated"},
    )
    deleted_at: datetime | None = Field(
        default=None,
        nullable=True,
        sa_column_kwargs={"comment": "Timestamp when the evaluation was deleted"},
    )

    # Relationships
    project: Project = Relationship()
    fine_tuning: "Fine_Tuning" = Relationship(back_populates="model_evaluation")


class ModelEvaluationUpdate(SQLModel):
    score: dict[str, float] | None = None
    status: ModelEvaluationStatus | None = None
    error_message: str | None = None
    prediction_data_s3_object: str | None = None


class ModelEvaluationPublic(ModelEvaluationBase):
    """Public response model for evaluation result."""

    id: int
    document_id: UUID
    fine_tuned_model: str
    split_ratio: float
    base_model: str
    prediction_data_file_url: str | None = None
    score: dict[str, float] | None = None
    status: ModelEvaluationStatus

    inserted_at: datetime
    updated_at: datetime
