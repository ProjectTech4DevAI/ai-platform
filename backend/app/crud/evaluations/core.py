import csv
import io
import logging

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.util import now
from app.crud.credentials import get_provider_credential
from app.models import EvaluationRun, UserProjectOrg
from app.models.evaluation import DatasetUploadResponse
from app.utils import get_langfuse_client

logger = logging.getLogger(__name__)


async def upload_dataset_to_langfuse(
    csv_content: bytes,
    dataset_name: str,
    dataset_id: int,
    duplication_factor: int,
    _session: Session,
    _current_user: UserProjectOrg,
) -> tuple[bool, DatasetUploadResponse | None, str | None]:
    """
    Upload a CSV dataset to Langfuse with duplication for flakiness testing.

    Args:
        csv_content: Raw CSV file content as bytes
        dataset_name: Name for the dataset in Langfuse
        dataset_id: Database ID of the created dataset
        duplication_factor: Number of times to duplicate each item (default 5)
        _session: Database session
        _current_user: Current user organization

    Returns:
        Tuple of (success, dataset_response, error_message)
    """
    try:
        # Get Langfuse client
        try:
            langfuse = get_langfuse_client(
                session=_session,
                org_id=_current_user.organization_id,
                project_id=_current_user.project_id,
            )
        except HTTPException as http_exc:
            return False, None, http_exc.detail

        # Parse CSV content
        csv_text = csv_content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_text))

        # Validate CSV headers
        if (
            "question" not in csv_reader.fieldnames
            or "answer" not in csv_reader.fieldnames
        ):
            return (
                False,
                None,
                "CSV must contain 'question' and 'answer' columns. "
                f"Found columns: {csv_reader.fieldnames}",
            )

        # Read all rows from CSV
        original_items = []
        for row in csv_reader:
            question = row.get("question", "").strip()
            answer = row.get("answer", "").strip()

            if not question or not answer:
                logger.warning(f"Skipping row with empty question or answer: {row}")
                continue

            original_items.append({"question": question, "answer": answer})

        if not original_items:
            return False, None, "No valid items found in CSV file."

        logger.info(
            f"Parsed {len(original_items)} items from CSV. "
            f"Will duplicate {duplication_factor}x for a total of {len(original_items) * duplication_factor} items."
        )

        # Create or get dataset in Langfuse
        dataset = langfuse.create_dataset(name=dataset_name)

        # Upload items with duplication
        total_uploaded = 0
        for item in original_items:
            # Duplicate each item N times
            for duplicate_num in range(duplication_factor):
                try:
                    langfuse.create_dataset_item(
                        dataset_name=dataset_name,
                        input={"question": item["question"]},
                        expected_output={"answer": item["answer"]},
                        metadata={
                            "original_question": item["question"],
                            "duplicate_number": duplicate_num + 1,
                            "duplication_factor": duplication_factor,
                        },
                    )
                    total_uploaded += 1
                except Exception as e:
                    logger.error(
                        f"Failed to upload item (duplicate {duplicate_num + 1}): {item['question'][:50]}... Error: {e}"
                    )

        # Flush to ensure all items are uploaded
        langfuse.flush()

        logger.info(
            f"Successfully uploaded {total_uploaded} items to dataset '{dataset_name}' "
            f"({len(original_items)} original × {duplication_factor} duplicates)"
        )

        return (
            True,
            DatasetUploadResponse(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                total_items=total_uploaded,
                original_items=len(original_items),
                duplication_factor=duplication_factor,
                langfuse_dataset_id=dataset.id if hasattr(dataset, "id") else None,
            ),
            None,
        )

    except Exception as e:
        logger.error(f"Error uploading dataset: {str(e)}", exc_info=True)
        return False, None, f"Failed to upload dataset: {str(e)}"


def create_evaluation_run(
    session: Session,
    run_name: str,
    dataset_name: str,
    dataset_id: int,
    config: dict,
    organization_id: int,
    project_id: int,
) -> EvaluationRun:
    """
    Create a new evaluation run record in the database.

    Args:
        session: Database session
        run_name: Name of the evaluation run/experiment
        dataset_name: Name of the dataset being used
        dataset_id: ID of the dataset
        config: Configuration dict for the evaluation
        organization_id: Organization ID
        project_id: Project ID

    Returns:
        The created EvaluationRun instance
    """
    eval_run = EvaluationRun(
        run_name=run_name,
        dataset_name=dataset_name,
        dataset_id=dataset_id,
        config=config,
        status="pending",
        organization_id=organization_id,
        project_id=project_id,
        inserted_at=now(),
        updated_at=now(),
    )

    session.add(eval_run)
    session.commit()
    session.refresh(eval_run)

    logger.info(f"Created EvaluationRun record: id={eval_run.id}, run_name={run_name}")

    return eval_run


def list_evaluation_runs(
    session: Session,
    organization_id: int,
    project_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[EvaluationRun]:
    """
    List all evaluation runs for an organization and project.

    Args:
        session: Database session
        organization_id: Organization ID to filter by
        project_id: Project ID to filter by
        limit: Maximum number of runs to return (default 50)
        offset: Number of runs to skip (for pagination)

    Returns:
        List of EvaluationRun objects, ordered by most recent first
    """
    statement = (
        select(EvaluationRun)
        .where(EvaluationRun.organization_id == organization_id)
        .where(EvaluationRun.project_id == project_id)
        .order_by(EvaluationRun.inserted_at.desc())
        .limit(limit)
        .offset(offset)
    )

    runs = session.exec(statement).all()

    logger.info(
        f"Found {len(runs)} evaluation runs for org_id={organization_id}, "
        f"project_id={project_id}"
    )

    return list(runs)


def get_evaluation_run_by_id(
    session: Session,
    evaluation_id: int,
    organization_id: int,
    project_id: int,
) -> EvaluationRun | None:
    """
    Get a specific evaluation run by ID.

    Args:
        session: Database session
        evaluation_id: ID of the evaluation run
        organization_id: Organization ID (for access control)
        project_id: Project ID (for access control)

    Returns:
        EvaluationRun if found and accessible, None otherwise
    """
    statement = (
        select(EvaluationRun)
        .where(EvaluationRun.id == evaluation_id)
        .where(EvaluationRun.organization_id == organization_id)
        .where(EvaluationRun.project_id == project_id)
    )

    eval_run = session.exec(statement).first()

    if eval_run:
        logger.info(
            f"Found evaluation run {evaluation_id}: status={eval_run.status}, "
            f"batch_job_id={eval_run.batch_job_id}"
        )
    else:
        logger.warning(
            f"Evaluation run {evaluation_id} not found or not accessible "
            f"for org_id={organization_id}, project_id={project_id}"
        )

    return eval_run


def update_evaluation_run(
    session: Session,
    eval_run: EvaluationRun,
    status: str | None = None,
    error_message: str | None = None,
    object_store_url: str | None = None,
    score: dict | None = None,
    embedding_batch_job_id: int | None = None,
) -> EvaluationRun:
    """
    Update an evaluation run with new values and persist to database.

    This helper function ensures consistency when updating evaluation runs
    by always updating the timestamp and properly committing changes.

    Args:
        session: Database session
        eval_run: EvaluationRun instance to update
        status: New status value (optional)
        error_message: New error message (optional)
        object_store_url: New object store URL (optional)
        score: New score dict (optional)
        embedding_batch_job_id: New embedding batch job ID (optional)

    Returns:
        Updated and refreshed EvaluationRun instance
    """
    # Update provided fields
    if status is not None:
        eval_run.status = status
    if error_message is not None:
        eval_run.error_message = error_message
    if object_store_url is not None:
        eval_run.object_store_url = object_store_url
    if score is not None:
        eval_run.score = score
    if embedding_batch_job_id is not None:
        eval_run.embedding_batch_job_id = embedding_batch_job_id

    # Always update timestamp
    eval_run.updated_at = now()

    # Persist to database
    session.add(eval_run)
    session.commit()
    session.refresh(eval_run)

    return eval_run
