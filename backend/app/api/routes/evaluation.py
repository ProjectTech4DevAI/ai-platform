import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlmodel import Session, select

from app.api.deps import get_current_user_org, get_db
from app.core.util import configure_langfuse, configure_openai, now
from app.crud.credentials import get_provider_credential
from app.crud.evaluation import upload_dataset_to_langfuse
from app.crud.evaluation_batch import start_evaluation_batch
from app.crud.evaluation_processing import poll_all_pending_evaluations
from app.models import UserOrganization, EvaluationRun
from app.models.evaluation import (
    DatasetUploadResponse,
    EvaluationRunCreate,
    EvaluationRunPublic,
)

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
    Upload a CSV file containing Golden Q&A pairs to Langfuse as a dataset.
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


@router.post("/evaluate", response_model=EvaluationRunPublic)
async def evaluate_threads(
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
) -> EvaluationRunPublic:
    """
    Start an evaluation using OpenAI Batch API.

    This endpoint:
    1. Creates an EvaluationRun record in the database
    2. Fetches dataset items from Langfuse
    3. Builds JSONL for OpenAI Batch API (using assistant config)
    4. Uploads to OpenAI and creates batch job
    5. Returns the evaluation run details with batch_id

    The batch will be processed asynchronously by Celery Beat (every 60s).
    Use GET /evaluate/batch/{run_id}/status to check progress.

    Args:
        experiment_name: Name for this evaluation run
        assistant_id: ID of the assistant (used to get config)
        dataset_name: Name of the Langfuse dataset

    Returns:
        EvaluationRunPublic with batch details and status
    """
    logger.info(
        f"Starting evaluation: experiment={experiment_name}, "
        f"dataset={dataset_name}, assistant={assistant_id}, "
        f"org_id={_current_user.organization_id}"
    )

    # Get credentials
    openai_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
    )
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
    )

    if not openai_credentials or not langfuse_credentials:
        raise ValueError("OpenAI or Langfuse credentials not configured")

    # Configure clients
    openai_client, openai_success = configure_openai(openai_credentials)
    langfuse, langfuse_success = configure_langfuse(langfuse_credentials)

    if not openai_success or not langfuse_success:
        raise ValueError("Failed to configure API clients")

    # Build config from assistant_id
    # For now, use simple config - you can enhance this to fetch assistant settings
    config = {
        "assistant_id": assistant_id,
        "llm": {"model": "gpt-4o", "temperature": 0.2},
        "instructions": "You are a helpful assistant",
        "vector_store_ids": [],
    }

    # Create EvaluationRun record
    eval_run = EvaluationRun(
        run_name=experiment_name,
        dataset_name=dataset_name,
        config=config,
        status="pending",
        organization_id=_current_user.organization_id,
        project_id=_current_user.project_id,
        inserted_at=now(),
        updated_at=now(),
    )

    _session.add(eval_run)
    _session.commit()
    _session.refresh(eval_run)

    logger.info(f"Created EvaluationRun record: id={eval_run.id}")

    # Start the batch evaluation
    try:
        eval_run = start_evaluation_batch(
            langfuse=langfuse,
            openai_client=openai_client,
            session=_session,
            eval_run=eval_run,
            config=config,
        )

        logger.info(
            f"Evaluation started successfully: "
            f"batch_id={eval_run.batch_id}, total_items={eval_run.total_items}"
        )

        return eval_run

    except Exception as e:
        logger.error(
            f"Failed to start evaluation for run {eval_run.id}: {e}",
            exc_info=True,
        )
        # Error is already handled in start_evaluation_batch
        _session.refresh(eval_run)
        return eval_run


@router.post("/evaluate/batch", response_model=EvaluationRunPublic)
async def start_batch_evaluation(
    eval_run_data: EvaluationRunCreate,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
) -> EvaluationRunPublic:
    """
    Start a batch evaluation using OpenAI Batch API.

    This endpoint:
    1. Creates an EvaluationRun record in the database
    2. Fetches dataset items from Langfuse
    3. Builds JSONL for OpenAI Batch API
    4. Uploads to OpenAI and creates batch job
    5. Returns the evaluation run details with batch_id

    The batch will be processed asynchronously. Use:
    - GET /evaluate/batch/{run_id}/status to check status
    - POST /evaluate/batch/poll to manually trigger polling

    Args:
        eval_run_data: EvaluationRunCreate with run_name, dataset_name, and config

    Returns:
        EvaluationRunPublic with batch details
    """
    logger.info(
        f"Starting batch evaluation: run_name={eval_run_data.run_name}, "
        f"dataset={eval_run_data.dataset_name}, "
        f"org_id={_current_user.organization_id}"
    )

    # Get credentials
    openai_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
    )
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
    )

    if not openai_credentials or not langfuse_credentials:
        raise ValueError("OpenAI or Langfuse credentials not configured")

    # Configure clients
    openai_client, openai_success = configure_openai(openai_credentials)
    langfuse, langfuse_success = configure_langfuse(langfuse_credentials)

    if not openai_success or not langfuse_success:
        raise ValueError("Failed to configure API clients")

    # Create EvaluationRun record
    eval_run = EvaluationRun(
        run_name=eval_run_data.run_name,
        dataset_name=eval_run_data.dataset_name,
        config=eval_run_data.config,
        status="pending",
        organization_id=_current_user.organization_id,
        project_id=_current_user.project_id,
        inserted_at=now(),
        updated_at=now(),
    )

    _session.add(eval_run)
    _session.commit()
    _session.refresh(eval_run)

    logger.info(f"Created EvaluationRun record: id={eval_run.id}")

    # Start the batch evaluation
    try:
        eval_run = start_evaluation_batch(
            langfuse=langfuse,
            openai_client=openai_client,
            session=_session,
            eval_run=eval_run,
            config=eval_run_data.config,
        )

        logger.info(
            f"Batch evaluation started successfully: "
            f"batch_id={eval_run.batch_id}, total_items={eval_run.total_items}"
        )

        return eval_run

    except Exception as e:
        logger.error(
            f"Failed to start batch evaluation for run {eval_run.id}: {e}",
            exc_info=True,
        )
        # The error is already handled in start_evaluation_batch
        # Just refresh and return the failed run
        _session.refresh(eval_run)
        return eval_run


@router.post("/evaluate/batch/poll")
async def poll_evaluation_batches(
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
) -> dict:
    """
    Manually trigger polling for all pending evaluations in the current organization.

    This endpoint is useful for:
    - Testing the evaluation flow
    - Immediately checking status instead of waiting for Celery beat
    - Debugging evaluation issues

    Returns:
        Summary of polling results including processed, failed, and still processing counts
    """
    logger.info(
        f"Manual polling triggered for org_id={_current_user.organization_id} "
        f"by user_id={_current_user.user_id}"
    )

    summary = await poll_all_pending_evaluations(
        session=_session, org_id=_current_user.organization_id
    )

    logger.info(
        f"Manual polling completed for org_id={_current_user.organization_id}: "
        f"{summary.get('total', 0)} evaluations checked, "
        f"{summary.get('processed', 0)} processed, "
        f"{summary.get('failed', 0)} failed"
    )

    return summary


@router.get("/evaluate/batch/{run_id}/status", response_model=EvaluationRunPublic)
async def get_evaluation_run_status(
    run_id: int,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
) -> EvaluationRunPublic:
    """
    Get the current status of a specific evaluation run.

    Args:
        run_id: ID of the evaluation run

    Returns:
        EvaluationRunPublic with current status, batch_status, and results if completed
    """
    logger.info(
        f"Fetching status for evaluation run {run_id} "
        f"(org_id={_current_user.organization_id})"
    )

    # Query the evaluation run
    statement = (
        select(EvaluationRun)
        .where(EvaluationRun.id == run_id)
        .where(EvaluationRun.organization_id == _current_user.organization_id)
    )

    eval_run = _session.exec(statement).first()

    if not eval_run:
        raise ValueError(
            f"Evaluation run {run_id} not found or not accessible to this organization"
        )

    logger.info(
        f"Found evaluation run {run_id}: status={eval_run.status}, "
        f"batch_status={eval_run.batch_status}"
    )

    return eval_run


@router.get("/evaluate/batch/list", response_model=list[EvaluationRunPublic])
async def list_evaluation_runs(
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
    limit: int = 50,
    offset: int = 0,
) -> list[EvaluationRunPublic]:
    """
    List all evaluation runs for the current organization.

    Args:
        limit: Maximum number of runs to return (default 50)
        offset: Number of runs to skip (for pagination)

    Returns:
        List of EvaluationRunPublic objects, ordered by most recent first
    """
    logger.info(
        f"Listing evaluation runs for org_id={_current_user.organization_id} "
        f"(limit={limit}, offset={offset})"
    )

    statement = (
        select(EvaluationRun)
        .where(EvaluationRun.organization_id == _current_user.organization_id)
        .order_by(EvaluationRun.inserted_at.desc())
        .limit(limit)
        .offset(offset)
    )

    runs = _session.exec(statement).all()

    logger.info(f"Found {len(runs)} evaluation runs")

    return list(runs)
