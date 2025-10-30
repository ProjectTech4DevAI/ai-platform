"""
CRUD operations for evaluation datasets.

This module handles database operations for evaluation datasets including:
1. Creating new datasets
2. Fetching datasets by ID or name
3. Listing datasets with pagination
4. Uploading CSV files to AWS S3
"""

import logging

from pathlib import Path
from typing import Any
from sqlmodel import Session, select
from datetime import datetime

from app.core.cloud.storage import CloudStorage, CloudStorageError
from app.core.util import now
from app.models import EvaluationDataset
from app.models import EvaluationRun


logger = logging.getLogger(__name__)


def create_evaluation_dataset(
    session: Session,
    name: str,
    dataset_metadata: dict[str, Any],
    organization_id: int,
    project_id: int,
    description: str | None = None,
    s3_url: str | None = None,
    langfuse_dataset_id: str | None = None,
) -> EvaluationDataset:
    """
    Create a new evaluation dataset record in the database.

    Args:
        session: Database session
        name: Name of the dataset
        dataset_metadata: Dataset metadata (original_items_count,
            total_items_count, duplication_factor)
        organization_id: Organization ID
        project_id: Project ID
        description: Optional dataset description
        s3_url: Optional AWS S3 URL where CSV is stored
        langfuse_dataset_id: Optional Langfuse dataset ID

    Returns:
        Created EvaluationDataset object
    """
    dataset = EvaluationDataset(
        name=name,
        description=description,
        dataset_metadata=dataset_metadata,
        s3_url=s3_url,
        langfuse_dataset_id=langfuse_dataset_id,
        organization_id=organization_id,
        project_id=project_id,
        inserted_at=now(),
        updated_at=now(),
    )

    session.add(dataset)
    session.commit()
    session.refresh(dataset)

    logger.info(
        f"Created evaluation dataset: id={dataset.id}, name={name}, "
        f"org_id={organization_id}, project_id={project_id}"
    )

    return dataset


def get_dataset_by_id(
    session: Session, dataset_id: int, organization_id: int, project_id: int
) -> EvaluationDataset | None:
    """
    Fetch an evaluation dataset by ID with organization and project validation.

    Args:
        session: Database session
        dataset_id: Dataset ID
        organization_id: Organization ID for validation
        project_id: Project ID for validation

    Returns:
        EvaluationDataset if found and belongs to the org/project, None otherwise
    """
    statement = (
        select(EvaluationDataset)
        .where(EvaluationDataset.id == dataset_id)
        .where(EvaluationDataset.organization_id == organization_id)
        .where(EvaluationDataset.project_id == project_id)
    )

    dataset = session.exec(statement).first()

    if dataset:
        logger.info(
            f"Found dataset: id={dataset_id}, name={dataset.name}, "
            f"org_id={organization_id}, project_id={project_id}"
        )
    else:
        logger.warning(
            f"Dataset not found or not accessible: id={dataset_id}, "
            f"org_id={organization_id}, project_id={project_id}"
        )

    return dataset


def get_dataset_by_name(
    session: Session, name: str, organization_id: int, project_id: int
) -> EvaluationDataset | None:
    """
    Fetch an evaluation dataset by name with organization and project validation.

    Args:
        session: Database session
        name: Dataset name
        organization_id: Organization ID for validation
        project_id: Project ID for validation

    Returns:
        EvaluationDataset if found and belongs to the org/project, None otherwise
    """
    statement = (
        select(EvaluationDataset)
        .where(EvaluationDataset.name == name)
        .where(EvaluationDataset.organization_id == organization_id)
        .where(EvaluationDataset.project_id == project_id)
    )

    dataset = session.exec(statement).first()

    if dataset:
        logger.info(
            f"Found dataset by name: name={name}, id={dataset.id}, "
            f"org_id={organization_id}, project_id={project_id}"
        )

    return dataset


def list_datasets(
    session: Session,
    organization_id: int,
    project_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[EvaluationDataset]:
    """
    List all evaluation datasets for an organization and project with pagination.

    Args:
        session: Database session
        organization_id: Organization ID
        project_id: Project ID
        limit: Maximum number of datasets to return (default 50)
        offset: Number of datasets to skip (for pagination)

    Returns:
        List of EvaluationDataset objects, ordered by most recent first
    """
    statement = (
        select(EvaluationDataset)
        .where(EvaluationDataset.organization_id == organization_id)
        .where(EvaluationDataset.project_id == project_id)
        .order_by(EvaluationDataset.inserted_at.desc())
        .limit(limit)
        .offset(offset)
    )

    datasets = session.exec(statement).all()

    logger.info(
        f"Listed {len(datasets)} datasets for org_id={organization_id}, "
        f"project_id={project_id} (limit={limit}, offset={offset})"
    )

    return list(datasets)


def upload_csv_to_s3(
    storage: CloudStorage,
    csv_content: bytes,
    dataset_name: str,
) -> str | None:
    """
    Upload CSV file to AWS S3.

    Args:
        storage: CloudStorage instance
        csv_content: Raw CSV content as bytes
        dataset_name: Name of the dataset (used for file naming)

    Returns:
        S3 URL as string if successful, None if failed

    Note:
        This function handles errors gracefully and returns None on failure.
        Callers should continue without S3 URL when this returns None.
    """
    try:
        # Create a file path for the CSV
        # Format: datasets/{dataset_name}_{timestamp}.csv
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = Path(f"datasets/{dataset_name}_{timestamp}.csv")

        # Create a mock UploadFile-like object for the storage put method
        import io

        class CSVFile:
            def __init__(self, content: bytes):
                self.file = io.BytesIO(content)
                self.content_type = "text/csv"

        csv_file = CSVFile(csv_content)

        # Upload to S3
        destination = storage.put(source=csv_file, file_path=file_path)
        s3_url = str(destination)

        logger.info(f"Successfully uploaded CSV to S3: {s3_url}")
        return s3_url

    except CloudStorageError as e:
        logger.warning(
            f"Failed to upload CSV to S3 for dataset '{dataset_name}': {e}. "
            "Continuing without S3 storage."
        )
        return None
    except Exception as e:
        logger.warning(
            f"Unexpected error uploading CSV to S3 for dataset '{dataset_name}': {e}. "
            "Continuing without S3 storage.",
            exc_info=True,
        )
        return None


def download_csv_from_s3(storage: CloudStorage, s3_url: str) -> bytes:
    """
    Download CSV file from AWS S3.

    Args:
        storage: CloudStorage instance
        s3_url: S3 URL of the CSV file

    Returns:
        CSV content as bytes

    Raises:
        CloudStorageError: If download fails
        ValueError: If s3_url is None or empty
    """
    if not s3_url:
        raise ValueError("s3_url cannot be None or empty")

    try:
        logger.info(f"Downloading CSV from S3: {s3_url}")
        body = storage.stream(s3_url)
        csv_content = body.read()
        logger.info(f"Successfully downloaded CSV from S3: {len(csv_content)} bytes")
        return csv_content
    except Exception as e:
        logger.error(f"Failed to download CSV from S3: {s3_url}: {e}", exc_info=True)
        raise


def update_dataset_langfuse_id(
    session: Session, dataset_id: int, langfuse_dataset_id: str
) -> None:
    """
    Update the langfuse_dataset_id for an existing dataset.

    Args:
        session: Database session
        dataset_id: Dataset ID
        langfuse_dataset_id: Langfuse dataset ID to store

    Returns:
        None
    """
    dataset = session.get(EvaluationDataset, dataset_id)
    if dataset:
        dataset.langfuse_dataset_id = langfuse_dataset_id
        dataset.updated_at = now()
        session.add(dataset)
        session.commit()
        logger.info(
            f"Updated langfuse_dataset_id for dataset {dataset_id}: "
            f"{langfuse_dataset_id}"
        )
    else:
        logger.warning(f"Dataset {dataset_id} not found for langfuse_id update")


def delete_dataset(
    session: Session, dataset_id: int, organization_id: int, project_id: int
) -> tuple[bool, str]:
    """
    Delete an evaluation dataset by ID.

    This performs a hard delete from the database. The CSV file in S3 (if exists)
    will remain for audit purposes.

    Args:
        session: Database session
        dataset_id: Dataset ID to delete
        organization_id: Organization ID for validation
        project_id: Project ID for validation

    Returns:
        Tuple of (success: bool, message: str)
    """
    # First, fetch the dataset to ensure it exists and belongs to the org/project
    dataset = get_dataset_by_id(
        session=session,
        dataset_id=dataset_id,
        organization_id=organization_id,
        project_id=project_id,
    )

    if not dataset:
        return (
            False,
            f"Dataset {dataset_id} not found or not accessible",
        )

    # Check if dataset is being used by any evaluation runs
    statement = select(EvaluationRun).where(EvaluationRun.dataset_id == dataset_id)
    evaluation_runs = session.exec(statement).all()

    if evaluation_runs:
        return (
            False,
            f"Cannot delete dataset {dataset_id}: it is being used by "
            f"{len(evaluation_runs)} evaluation run(s). Please delete "
            f"the evaluation runs first.",
        )

    # Delete the dataset
    try:
        session.delete(dataset)
        session.commit()

        logger.info(
            f"Deleted dataset: id={dataset_id}, name={dataset.name}, "
            f"org_id={organization_id}, project_id={project_id}"
        )

        return (
            True,
            f"Successfully deleted dataset '{dataset.name}' (id={dataset_id})",
        )

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete dataset {dataset_id}: {e}", exc_info=True)
        return (False, f"Failed to delete dataset: {e}")
