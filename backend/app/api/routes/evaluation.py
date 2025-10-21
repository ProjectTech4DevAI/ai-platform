import logging

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile
from sqlmodel import Session, select

from app.api.deps import get_current_user_org_project, get_db
from app.core.util import configure_langfuse, configure_openai, now
from app.crud.assistants import get_assistant_by_id
from app.crud.credentials import get_provider_credential
from app.crud.evaluation import upload_dataset_to_langfuse
from app.crud.evaluation_batch import start_evaluation_batch
from app.crud.evaluation_processing import poll_all_pending_evaluations
from app.models import EvaluationRun, UserProjectOrg
from app.models.evaluation import (
    DatasetUploadResponse,
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
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
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
    dataset_name: str = Body(..., description="Name of the Langfuse dataset"),
    experiment_name: str = Body(
        ..., description="Name for this evaluation experiment/run"
    ),
    config: dict = Body(..., description="Evaluation configuration"),
    _session: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
) -> EvaluationRunPublic:
    """
    Start an evaluation using OpenAI Batch API.

    This endpoint:
    1. Creates an EvaluationRun record in the database
    2. Fetches dataset items from Langfuse
    3. Builds JSONL for batch processing (using provided config)
    4. Creates a batch job via the generic batch infrastructure
    5. Returns the evaluation run details with batch_job_id

    The batch will be processed asynchronously by Celery Beat (every 60s).
    Use GET /evaluate/batch/{run_id}/status to check progress.

    Args:
        dataset_name: Name of the Langfuse dataset
        experiment_name: Name for this evaluation experiment/run
        config: Configuration dict with optional fields:
            - assistant_id (optional): If provided, fetch config from openai_assistant table
            - llm (optional): {"model": "gpt-4o", "temperature": 0.2}
            - instructions (optional): System instructions
            - vector_store_ids (optional): List of vector store IDs

    Example config:
    {
        "llm": {"model": "gpt-4o", "temperature": 0.2},
        "instructions": "You are a friendly assistant",
        "vector_store_ids": ["vs_abc123"],
        "assistant_id": "asst_xyz"  # Optional - fetches from DB if provided
    }

    Returns:
        EvaluationRunPublic with batch details and status
    """
    logger.info(
        f"Starting evaluation: experiment_name={experiment_name}, "
        f"dataset={dataset_name}, "
        f"org_id={_current_user.organization_id}, "
        f"config_keys={list(config.keys())}"
    )

    # Get credentials
    openai_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        project_id=_current_user.project_id,
        provider="openai",
    )
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        project_id=_current_user.project_id,
        provider="langfuse",
    )

    if not openai_credentials or not langfuse_credentials:
        raise ValueError("OpenAI or Langfuse credentials not configured")

    # Configure clients
    openai_client, openai_success = configure_openai(openai_credentials)
    langfuse, langfuse_success = configure_langfuse(langfuse_credentials)

    if not openai_success or not langfuse_success:
        raise ValueError("Failed to configure API clients")

    # Check if assistant_id is provided in config
    assistant_id = config.get("assistant_id")
    if assistant_id:
        # Fetch assistant details from database
        assistant = get_assistant_by_id(
            session=_session,
            assistant_id=assistant_id,
            project_id=_current_user.project_id,
        )

        if assistant:
            logger.info(
                f"Found assistant in DB: id={assistant.id}, "
                f"model={assistant.model}, instructions={assistant.instructions[:50]}..."
            )

            # Merge DB config with provided config (provided config takes precedence)
            db_config = {
                "assistant_id": assistant_id,
                "llm": {
                    "model": assistant.model,
                    "temperature": assistant.temperature,
                },
                "instructions": assistant.instructions,
                "vector_store_ids": assistant.vector_store_ids or [],
            }

            # Override with provided config values
            for key in ["llm", "instructions", "vector_store_ids"]:
                if key in config:
                    db_config[key] = config[key]

            config = db_config
            logger.info("Using merged config from DB and provided values")
        else:
            logger.warning(
                f"Assistant {assistant_id} not found in DB, using provided config"
            )
    else:
        logger.info("No assistant_id provided, using provided config directly")

    # Ensure config has required fields with defaults
    if "llm" not in config:
        config["llm"] = {"model": "gpt-4o", "temperature": 0.2}
    if "instructions" not in config:
        config["instructions"] = "You are a helpful assistant"
    if "vector_store_ids" not in config:
        config["vector_store_ids"] = []

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
            f"batch_job_id={eval_run.batch_job_id}, total_items={eval_run.total_items}"
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


@router.post("/evaluate/batch/poll")
async def poll_evaluation_batches(
    _session: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
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
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
) -> EvaluationRunPublic:
    """
    Get the current status of a specific evaluation run.

    Args:
        run_id: ID of the evaluation run

    Returns:
        EvaluationRunPublic with current status and results if completed
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
        f"batch_job_id={eval_run.batch_job_id}"
    )

    return eval_run


@router.get("/evaluate/batch/list", response_model=list[EvaluationRunPublic])
async def list_evaluation_runs(
    _session: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
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
