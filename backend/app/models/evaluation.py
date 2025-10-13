from pydantic import BaseModel, Field


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
    match: bool = Field(
        ..., description="Whether the output matches the expected result"
    )
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
    matches: int = Field(..., description="Number of successful matches")
    note: str = Field(..., description="Additional notes about the evaluation process")
