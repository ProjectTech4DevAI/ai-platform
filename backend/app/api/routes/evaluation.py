import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlmodel import Session

from app.api.deps import get_current_user_org, get_db
from app.crud.evaluation import run_evaluation, upload_dataset_to_langfuse
from app.models import UserOrganization
from app.models.evaluation import Experiment, DatasetUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluation"])


@router.post("/dataset/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(
        ..., description="CSV file with 'question' and 'answer' columns"
    ),
    dataset_name: str = Form(..., description="Name for the dataset in Langfuse"),
    duplication_factor: int = Form(
        default=5, description="Number of times to duplicate each item"
    ),
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
) -> DatasetUploadResponse:
    """
    Upload a CSV file containing Q&A pairs to Langfuse as a dataset.
    Each question will be duplicated N times (default 5) to test LLM flakiness.

    CSV Format:
    - Must contain 'question' and 'answer' columns
    - Can have additional columns (will be ignored)

    Example CSV:
    ```
    question,answer
    "What is the capital of France?","Paris"
    "What is 2+2?","4"
    ```
    """
    logger.info(
        f"Uploading dataset: {dataset_name} with duplication factor: {duplication_factor}"
    )

    # Read CSV content
    content = await file.read()

    success, data, error = await upload_dataset_to_langfuse(
        csv_content=content,
        dataset_name=dataset_name,
        duplication_factor=duplication_factor,
        _session=_session,
        _current_user=_current_user,
    )

    if not success or data is None:
        raise ValueError(error or "Failed to upload dataset")

    logger.info(
        f"Successfully uploaded dataset: {dataset_name} with {data.total_items} items "
        f"({data.original_items} original items × {duplication_factor})"
    )

    return data


@router.post("/evaluate", response_model=Experiment)
async def evaluate_threads(
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
) -> Experiment:
    """
    Endpoint to run Langfuse evaluations using LLM-as-a-judge.
    Read more here: https://langfuse.com/changelog/2024-11-19-llm-as-a-judge-for-datasets
    """
    logger.info(
        f"Starting evaluation for experiment: {experiment_name}, dataset: {dataset_name}, assistant: {assistant_id}"
    )

    success, data, error = await run_evaluation(
        experiment_name=experiment_name,
        assistant_id=assistant_id,
        dataset_name=dataset_name,
        _session=_session,
        _current_user=_current_user,
    )

    if not success or data is None:
        raise ValueError(error or "Failed to run evaluation")

    return data
