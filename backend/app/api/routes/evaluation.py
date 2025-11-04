import csv
import io
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

from app.api.deps import AuthContextDep, SessionDep
from app.core.cloud import get_cloud_storage
from app.core.util import configure_langfuse, configure_openai
from app.crud.assistants import get_assistant_by_id
from app.crud.credentials import get_provider_credential
from app.crud.evaluations import (
    create_evaluation_dataset,
    create_evaluation_run,
    get_dataset_by_id,
    get_evaluation_run_by_id,
    list_datasets,
    start_evaluation_batch,
    upload_csv_to_object_store,
    upload_dataset_to_langfuse_from_csv,
)
from app.crud.evaluations import list_evaluation_runs as list_evaluation_runs_crud
from app.crud.evaluations.dataset import delete_dataset as delete_dataset_crud
from app.models.evaluation import (
    DatasetUploadResponse,
    EvaluationRunPublic,
)

logger = logging.getLogger(__name__)

# File upload security constants
MAX_FILE_SIZE = 1024 * 1024  # 1 MB
ALLOWED_EXTENSIONS = {".csv"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",  # Some systems report CSV as text/plain
}

router = APIRouter(tags=["evaluation"])


def sanitize_dataset_name(name: str) -> str:
    """
    Sanitize dataset name for Langfuse compatibility.

    Langfuse has issues with spaces and special characters in dataset names.
    This function ensures the name can be both created and fetched.

    Rules:
    - Replace spaces with underscores
    - Replace hyphens with underscores
    - Keep only alphanumeric characters and underscores
    - Convert to lowercase for consistency
    - Remove leading/trailing underscores
    - Collapse multiple consecutive underscores into one

    Args:
        name: Original dataset name

    Returns:
        Sanitized dataset name safe for Langfuse

    Examples:
        "testing 0001" -> "testing_0001"
        "My Dataset!" -> "my_dataset"
        "Test--Data__Set" -> "test_data_set"
    """
    # Convert to lowercase
    sanitized = name.lower()

    # Replace spaces and hyphens with underscores
    sanitized = sanitized.replace(" ", "_").replace("-", "_")

    # Keep only alphanumeric characters and underscores
    sanitized = re.sub(r"[^a-z0-9_]", "", sanitized)

    # Collapse multiple underscores into one
    sanitized = re.sub(r"_+", "_", sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    # Ensure name is not empty
    if not sanitized:
        raise ValueError("Dataset name cannot be empty after sanitization")

    return sanitized


@router.post("/evaluations/datasets", response_model=DatasetUploadResponse)
async def upload_dataset(
    _session: SessionDep,
    auth_context: AuthContextDep,
    file: UploadFile = File(
        ..., description="CSV file with 'question' and 'answer' columns"
    ),
    dataset_name: str = Form(..., description="Name for the dataset"),
    description: str | None = Form(None, description="Optional dataset description"),
    duplication_factor: int = Form(
        default=5,
        ge=1,
        le=5,
        description="Number of times to duplicate each item (min: 1, max: 5)",
    ),
) -> DatasetUploadResponse:
    """
    Upload a CSV file containing Golden Q&A pairs.

    This endpoint:
    1. Sanitizes the dataset name (removes spaces, special characters)
    2. Validates and parses the CSV file
    3. Uploads CSV to object store (if credentials configured)
    4. Uploads dataset to Langfuse (for immediate use)
    5. Stores metadata in database

    Dataset Name:
    - Will be sanitized for Langfuse compatibility
    - Spaces replaced with underscores
    - Special characters removed
    - Converted to lowercase
    - Example: "My Dataset 01!" becomes "my_dataset_01"

    CSV Format:
    - Must contain 'question' and 'answer' columns
    - Can have additional columns (will be ignored)
    - Missing values in 'question' or 'answer' rows will be skipped

    Duplication Factor:
    - Minimum: 1 (no duplication)
    - Maximum: 5
    - Default: 5
    - Each item in the dataset will be duplicated this many times
    - Used to ensure statistical significance in evaluation results

    Example CSV:
    ```
    question,answer
    "What is the capital of France?","Paris"
    "What is 2+2?","4"
    ```

    Returns:
        DatasetUploadResponse with dataset_id, object_store_url, and Langfuse details
        (dataset_name in response will be the sanitized version)
    """
    # Sanitize dataset name for Langfuse compatibility
    original_name = dataset_name
    try:
        dataset_name = sanitize_dataset_name(dataset_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid dataset name: {str(e)}")

    if original_name != dataset_name:
        logger.info(f"Dataset name sanitized: '{original_name}' -> '{dataset_name}'")

    logger.info(
        f"Uploading dataset: {dataset_name} with duplication factor: "
        f"{duplication_factor}, org_id={auth_context.organization.id}, "
        f"project_id={auth_context.project.id}"
    )

    # Security validation: Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type. Only CSV files are allowed. Got: {file_ext}",
        )

    # Security validation: Check MIME type
    content_type = file.content_type
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid content type. Expected CSV, got: {content_type}",
        )

    # Security validation: Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024):.0f}MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=422, detail="Empty file uploaded")

    # Read CSV content
    csv_content = await file.read()

    # Step 1: Parse and validate CSV
    try:
        csv_text = csv_content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        csv_reader.fieldnames = [name.strip() for name in csv_reader.fieldnames]

        # Validate headers
        if (
            "question" not in csv_reader.fieldnames
            or "answer" not in csv_reader.fieldnames
        ):
            raise HTTPException(
                status_code=422,
                detail=f"CSV must contain 'question' and 'answer' columns. "
                f"Found columns: {csv_reader.fieldnames}",
            )

        # Count original items
        original_items = []
        for row in csv_reader:
            question = row.get("question", "").strip()
            answer = row.get("answer", "").strip()
            if question and answer:
                original_items.append({"question": question, "answer": answer})

        if not original_items:
            raise HTTPException(
                status_code=422, detail="No valid items found in CSV file"
            )

        original_items_count = len(original_items)
        total_items_count = original_items_count * duplication_factor

        logger.info(
            f"Parsed {original_items_count} items from CSV, "
            f"will create {total_items_count} total items with duplication"
        )

    except Exception as e:
        logger.error(f"Failed to parse CSV: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail=f"Invalid CSV file: {e}")

    # Step 2: Upload to object store (if credentials configured)
    object_store_url = None
    try:
        storage = get_cloud_storage(
            session=_session, project_id=auth_context.project.id
        )
        object_store_url = upload_csv_to_object_store(
            storage=storage, csv_content=csv_content, dataset_name=dataset_name
        )
        if object_store_url:
            logger.info(
                f"Successfully uploaded CSV to object store: {object_store_url}"
            )
        else:
            logger.info(
                "Object store upload returned None, continuing without object store storage"
            )
    except Exception as e:
        logger.warning(
            f"Failed to upload CSV to object store (continuing without object store): {e}",
            exc_info=True,
        )
        object_store_url = None

    # Step 3: Upload to Langfuse
    langfuse_dataset_id = None
    try:
        # Get Langfuse credentials
        langfuse_credentials = get_provider_credential(
            session=_session,
            org_id=auth_context.organization.id,
            project_id=auth_context.project.id,
            provider="langfuse",
        )
        if not langfuse_credentials:
            raise HTTPException(
                status_code=400, detail="Langfuse credentials not configured"
            )

        langfuse, langfuse_success = configure_langfuse(langfuse_credentials)
        if not langfuse_success:
            raise HTTPException(
                status_code=500, detail="Failed to configure Langfuse client"
            )

        # Upload to Langfuse
        langfuse_dataset_id, _ = upload_dataset_to_langfuse_from_csv(
            langfuse=langfuse,
            csv_content=csv_content,
            dataset_name=dataset_name,
            duplication_factor=duplication_factor,
        )

        logger.info(
            f"Successfully uploaded dataset to Langfuse: {dataset_name} "
            f"(id={langfuse_dataset_id})"
        )

    except Exception as e:
        logger.error(f"Failed to upload dataset to Langfuse: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to upload dataset to Langfuse: {e}"
        )

    # Step 4: Store metadata in database
    metadata = {
        "original_items_count": original_items_count,
        "total_items_count": total_items_count,
        "duplication_factor": duplication_factor,
    }

    dataset = create_evaluation_dataset(
        session=_session,
        name=dataset_name,
        description=description,
        dataset_metadata=metadata,
        object_store_url=object_store_url,
        langfuse_dataset_id=langfuse_dataset_id,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
    )

    logger.info(
        f"Successfully created dataset record in database: id={dataset.id}, "
        f"name={dataset_name}"
    )

    # Return response
    return DatasetUploadResponse(
        dataset_id=dataset.id,
        dataset_name=dataset_name,
        total_items=total_items_count,
        original_items=original_items_count,
        duplication_factor=duplication_factor,
        langfuse_dataset_id=langfuse_dataset_id,
        object_store_url=object_store_url,
    )


@router.get("/evaluations/datasets/list", response_model=list[DatasetUploadResponse])
async def list_datasets_endpoint(
    _session: SessionDep,
    auth_context: AuthContextDep,
    limit: int = 50,
    offset: int = 0,
) -> list[DatasetUploadResponse]:
    """
    List all datasets for the current organization and project.

    Args:
        limit: Maximum number of datasets to return (default 50, max 100)
        offset: Number of datasets to skip for pagination (default 0)

    Returns:
        List of DatasetUploadResponse objects, ordered by most recent first
    """
    # Enforce maximum limit
    if limit > 100:
        limit = 100

    datasets = list_datasets(
        session=_session,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
        limit=limit,
        offset=offset,
    )

    # Convert to response format
    response = []
    for dataset in datasets:
        response.append(
            DatasetUploadResponse(
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                total_items=dataset.dataset_metadata.get("total_items_count", 0),
                original_items=dataset.dataset_metadata.get("original_items_count", 0),
                duplication_factor=dataset.dataset_metadata.get(
                    "duplication_factor", 1
                ),
                langfuse_dataset_id=dataset.langfuse_dataset_id,
                object_store_url=dataset.object_store_url,
            )
        )

    return response


@router.get("/evaluations/datasets/{dataset_id}", response_model=DatasetUploadResponse)
async def get_dataset(
    dataset_id: int,
    _session: SessionDep,
    auth_context: AuthContextDep,
) -> DatasetUploadResponse:
    """
    Get details of a specific dataset by ID.

    Args:
        dataset_id: ID of the dataset to retrieve

    Returns:
        DatasetUploadResponse with dataset details
    """
    logger.info(
        f"Fetching dataset: id={dataset_id}, "
        f"org_id={auth_context.organization.id}, "
        f"project_id={auth_context.project.id}"
    )

    dataset = get_dataset_by_id(
        session=_session,
        dataset_id=dataset_id,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
    )

    if not dataset:
        raise HTTPException(
            status_code=404, detail=f"Dataset {dataset_id} not found or not accessible"
        )

    return DatasetUploadResponse(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        total_items=dataset.dataset_metadata.get("total_items_count", 0),
        original_items=dataset.dataset_metadata.get("original_items_count", 0),
        duplication_factor=dataset.dataset_metadata.get("duplication_factor", 1),
        langfuse_dataset_id=dataset.langfuse_dataset_id,
        object_store_url=dataset.object_store_url,
    )


@router.delete("/evaluations/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: int,
    _session: SessionDep,
    auth_context: AuthContextDep,
) -> dict:
    """
    Delete a dataset by ID.

    This will remove the dataset record from the database. The CSV file in object store
    (if exists) will remain for audit purposes, but the dataset will no longer
    be accessible for creating new evaluations.

    Args:
        dataset_id: ID of the dataset to delete

    Returns:
        Success message with deleted dataset details
    """
    logger.info(
        f"Deleting dataset: id={dataset_id}, "
        f"org_id={auth_context.organization.id}, "
        f"project_id={auth_context.project.id}"
    )

    success, message = delete_dataset_crud(
        session=_session,
        dataset_id=dataset_id,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
    )

    if not success:
        # Check if it's a not found error or other error type
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        else:
            raise HTTPException(status_code=400, detail=message)

    logger.info(f"Successfully deleted dataset: id={dataset_id}")
    return {"message": message, "dataset_id": dataset_id}


@router.post("/evaluations", response_model=EvaluationRunPublic)
async def evaluate(
    _session: SessionDep,
    auth_context: AuthContextDep,
    dataset_id: int = Body(..., description="ID of the evaluation dataset"),
    experiment_name: str = Body(
        ..., description="Name for this evaluation experiment/run"
    ),
    config: dict = Body(default_factory=dict, description="Evaluation configuration"),
    assistant_id: str
    | None = Body(
        None, description="Optional assistant ID to fetch configuration from"
    ),
) -> EvaluationRunPublic:
    """
    Start an evaluation using OpenAI Batch API.

    This endpoint:
    1. Fetches the dataset from database and validates it has Langfuse dataset ID
    2. Creates an EvaluationRun record in the database
    3. Fetches dataset items from Langfuse
    4. Builds JSONL for batch processing (config is used as-is)
    5. Creates a batch job via the generic batch infrastructure
    6. Returns the evaluation run details with batch_job_id

    The batch will be processed asynchronously by Celery Beat (every 60s).
    Use GET /evaluations/{evaluation_id} to check progress.

    Args:
        dataset_id: ID of the evaluation dataset (from /evaluations/datasets)
        experiment_name: Name for this evaluation experiment/run
        config: Configuration dict that will be used as-is in JSONL generation.
            Can include any OpenAI Responses API parameters like:
            - model: str (e.g., "gpt-4o", "gpt-5")
            - instructions: str
            - tools: list (e.g., [{"type": "file_search", "vector_store_ids": [...]}])
            - reasoning: dict (e.g., {"effort": "low"})
            - text: dict (e.g., {"verbosity": "low"})
            - temperature: float
            - include: list (e.g., ["file_search_call.results"])
            Note: "input" will be added automatically from the dataset
        assistant_id: Optional assistant ID. If provided, configuration will be
            fetched from the assistant in the database. Config can be passed as
            empty dict {} when using assistant_id.

    Example with config:
    {
        "dataset_id": 123,
        "experiment_name": "test_run",
        "config": {
            "model": "gpt-4.1",
            "instructions": "You are a helpful FAQ assistant.",
            "tools": [
                {
                    "type": "file_search",
                    "vector_store_ids": ["vs_12345"],
                    "max_num_results": 3
                }
            ],
            "include": ["file_search_call.results"]
        }
    }

    Example with assistant_id:
    {
        "dataset_id": 123,
        "experiment_name": "test_run",
        "config": {},
        "assistant_id": "asst_xyz"
    }

    Returns:
        EvaluationRunPublic with batch details and status
    """
    logger.info(
        f"Starting evaluation: experiment_name={experiment_name}, "
        f"dataset_id={dataset_id}, "
        f"org_id={auth_context.organization.id}, "
        f"assistant_id={assistant_id}, "
        f"config_keys={list(config.keys())}"
    )

    # Step 1: Fetch dataset from database
    dataset = get_dataset_by_id(
        session=_session,
        dataset_id=dataset_id,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
    )

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {dataset_id} not found or not accessible to this "
            f"organization/project",
        )

    logger.info(
        f"Found dataset: id={dataset.id}, name={dataset.name}, "
        f"object_store_url={'present' if dataset.object_store_url else 'None'}, "
        f"langfuse_id={dataset.langfuse_dataset_id}"
    )

    dataset_name = dataset.name

    # Get credentials
    openai_credentials = get_provider_credential(
        session=_session,
        org_id=auth_context.organization.id,
        project_id=auth_context.project.id,
        provider="openai",
    )
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=auth_context.organization.id,
        project_id=auth_context.project.id,
        provider="langfuse",
    )

    if not openai_credentials or not langfuse_credentials:
        raise HTTPException(
            status_code=400, detail="OpenAI or Langfuse credentials not configured"
        )

    # Configure clients
    openai_client, openai_success = configure_openai(openai_credentials)
    langfuse, langfuse_success = configure_langfuse(langfuse_credentials)

    if not openai_success or not langfuse_success:
        raise HTTPException(status_code=500, detail="Failed to configure API clients")

    # Validate dataset has Langfuse ID (should have been set during dataset creation)
    if not dataset.langfuse_dataset_id:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset {dataset_id} does not have a Langfuse dataset ID. "
            "Please ensure Langfuse credentials were configured when the dataset was created.",
        )

    # Handle assistant_id if provided
    if assistant_id:
        # Fetch assistant details from database
        assistant = get_assistant_by_id(
            session=_session,
            assistant_id=assistant_id,
            project_id=auth_context.project.id,
        )

        if not assistant:
            raise HTTPException(
                status_code=404, detail=f"Assistant {assistant_id} not found"
            )

        logger.info(
            f"Found assistant in DB: id={assistant.id}, "
            f"model={assistant.model}, instructions="
            f"{assistant.instructions[:50] if assistant.instructions else 'None'}..."
        )

        # Build config from assistant (use provided config values to override
        # if present)
        config = {
            "model": config.get("model", assistant.model),
            "instructions": config.get("instructions", assistant.instructions),
            "temperature": config.get("temperature", assistant.temperature),
        }

        # Add tools if vector stores are available
        vector_store_ids = config.get(
            "vector_store_ids", assistant.vector_store_ids or []
        )
        if vector_store_ids and len(vector_store_ids) > 0:
            config["tools"] = [
                {
                    "type": "file_search",
                    "vector_store_ids": vector_store_ids,
                }
            ]

        logger.info("Using config from assistant")
    else:
        logger.info("Using provided config directly")
        # Validate that config has minimum required fields
        if not config.get("model"):
            raise HTTPException(
                status_code=400,
                detail="Config must include 'model' when assistant_id is not provided",
            )

    # Create EvaluationRun record
    eval_run = create_evaluation_run(
        session=_session,
        run_name=experiment_name,
        dataset_name=dataset_name,
        dataset_id=dataset_id,
        config=config,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
    )

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


@router.get("/evaluations/list", response_model=list[EvaluationRunPublic])
async def list_evaluation_runs(
    _session: SessionDep,
    auth_context: AuthContextDep,
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
        f"Listing evaluation runs for org_id={auth_context.organization.id}, "
        f"project_id={auth_context.project.id} (limit={limit}, offset={offset})"
    )

    return list_evaluation_runs_crud(
        session=_session,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
        limit=limit,
        offset=offset,
    )


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationRunPublic)
async def get_evaluation_run_status(
    evaluation_id: int,
    _session: SessionDep,
    auth_context: AuthContextDep,
) -> EvaluationRunPublic:
    """
    Get the current status of a specific evaluation run.

    Args:
        evaluation_id: ID of the evaluation run

    Returns:
        EvaluationRunPublic with current status and results if completed
    """
    logger.info(
        f"Fetching status for evaluation run {evaluation_id} "
        f"(org_id={auth_context.organization.id}, "
        f"project_id={auth_context.project.id})"
    )

    eval_run = get_evaluation_run_by_id(
        session=_session,
        evaluation_id=evaluation_id,
        organization_id=auth_context.organization.id,
        project_id=auth_context.project.id,
    )

    if not eval_run:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Evaluation run {evaluation_id} not found or not accessible "
                "to this organization"
            ),
        )

    return eval_run
